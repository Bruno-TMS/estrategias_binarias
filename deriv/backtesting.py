"""Módulo de simulação e backtesting quantitativo para contratos de opções digitais (Rise/Fall)."""

import logging
from typing import Any
import numpy as np

from deriv.analises_tecnicas import IchimokuIndicator

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Motor de backtesting quantitativo para contratos de opções digitais (Rise/Fall).

    Simula a execução de estratégias baseadas em indicadores técnicos, registrando métricas
    de desempenho sem look-ahead bias e permitindo o ranqueamento de hiperparâmetros.
    """

    def __init__(
        self,
        prices: list[float] | np.ndarray,
        stake: float = 1.0,
        payout_rate: float = 0.95,
    ) -> None:
        """Inicializa o motor de backtest.

        :param prices: Série temporal de preços ou ticks históricos.
        :param stake: Valor fixo apostado por operação (ex: 1.0 USD).
        :param payout_rate: Taxa de retorno em caso de vitória (ex: 0.95 = 95%).
        """
        if stake <= 0:
            raise ValueError("O stake deve ser maior que zero.")
        if payout_rate <= 0:
            raise ValueError("A taxa de payout deve ser maior que zero.")

        self.prices: np.ndarray = np.asarray(prices, dtype=np.float64)
        self.stake: float = float(stake)
        self.payout_rate: float = float(payout_rate)

    def _extract_signals(self, indicator_instance: Any) -> np.ndarray:
        """Extrai a série de sinais para cada ponto t sem look-ahead bias.

        Para IchimokuIndicator, emprega cálculo vetorizado com garantia matemática
        de que cada instante t utiliza estritamente informações históricas prices[:t+1].
        Para outros indicadores genéricos, realiza iteração segura sobre cada fatia.
        """
        n = len(self.prices)
        if n == 0:
            return np.empty(0, dtype=object)

        if isinstance(indicator_instance, IchimokuIndicator):
            data = indicator_instance.calculate(self.prices)
            tenkan = data["tenkan"]
            kijun = data["kijun"]

            # Antes de (senkou_b_period + displacement - 1), utiliza a nuvem crua como fallback
            threshold = indicator_instance.senkou_b_period + indicator_instance.displacement - 1
            kumo_a = np.where(
                np.arange(n) < threshold,
                data["senkou_a_raw"],
                data["senkou_span_a"],
            )
            kumo_b = np.where(
                np.arange(n) < threshold,
                data["senkou_b_raw"],
                data["senkou_span_b"],
            )

            top = np.maximum(kumo_a, kumo_b)
            bot = np.minimum(kumo_a, kumo_b)

            valid = (
                (np.arange(n) >= indicator_instance.senkou_b_period - 1)
                & ~np.isnan(top)
                & ~np.isnan(bot)
                & ~np.isnan(tenkan)
                & ~np.isnan(kijun)
            )

            signals = np.full(n, "NEUTRO", dtype=object)
            signals[valid & (self.prices > top) & (tenkan > kijun)] = "CALL"
            signals[valid & (self.prices < bot) & (tenkan < kijun)] = "PUT"
            return signals

        if hasattr(indicator_instance, "get_signals_series"):
            raw_signals = indicator_instance.get_signals_series(self.prices)
            return np.asarray(raw_signals, dtype=object)

        # Fallback para indicador genérico que implementa get_signal(slice)
        signals = np.full(n, "NEUTRO", dtype=object)
        for t in range(n):
            res = indicator_instance.get_signal(self.prices[: t + 1])
            if isinstance(res, dict):
                signals[t] = res.get("signal", "NEUTRO")
            else:
                signals[t] = str(res)
        return signals

    def _extract_parameters(self, indicator_instance: Any, duration_ticks: int, allow_overlap: bool) -> dict[str, Any]:
        """Extrai os parâmetros do indicador e da simulação."""
        params: dict[str, Any] = {
            "duration_ticks": duration_ticks,
            "stake": self.stake,
            "payout_rate": self.payout_rate,
            "allow_overlap": allow_overlap,
        }
        for attr in ("tenkan_period", "kijun_period", "senkou_b_period", "displacement"):
            if hasattr(indicator_instance, attr):
                params[attr] = getattr(indicator_instance, attr)
        return params

    def run_strategy(
        self,
        indicator_instance: Any,
        duration_ticks: int = 5,
        allow_overlap: bool = False,
    ) -> dict[str, Any]:
        """Simula a execução de sinais ao longo da série temporal.

        :param indicator_instance: Instância do indicador (ex: IchimokuIndicator).
        :param duration_ticks: Duração de cada contrato em ticks.
        :param allow_overlap: Se False, aguarda o contrato atual expirar antes de abrir outro.
        :return: Dicionário estruturado com as métricas de performance e trades executados.
        """
        if duration_ticks <= 0:
            raise ValueError("duration_ticks deve ser maior que zero.")

        n = len(self.prices)
        parameters = self._extract_parameters(indicator_instance, duration_ticks, allow_overlap)

        # Tratamento seguro para séries curtas
        if n <= duration_ticks:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_profit": 0.0,
                "max_drawdown": 0.0,
                "max_consecutive_losses": 0,
                "parameters": parameters,
                "trades": [],
            }

        signals = self._extract_signals(indicator_instance)
        trades: list[dict[str, Any]] = []
        wins = 0
        losses = 0

        t = 0
        max_entry_idx = n - duration_ticks

        while t < max_entry_idx:
            sig = signals[t]
            if sig in ("CALL", "PUT"):
                entry_idx = t
                entry_price = float(self.prices[entry_idx])
                exit_idx = t + duration_ticks
                exit_price = float(self.prices[exit_idx])

                if sig == "CALL":
                    won = exit_price > entry_price
                else:  # "PUT"
                    won = exit_price < entry_price

                if won:
                    wins += 1
                    result = "WIN"
                    profit = round(self.stake * self.payout_rate, 4)
                else:
                    losses += 1
                    result = "LOSS"
                    profit = -round(self.stake, 4)

                trades.append({
                    "trade_id": len(trades) + 1,
                    "signal": sig,
                    "entry_index": entry_idx,
                    "entry_price": entry_price,
                    "exit_index": exit_idx,
                    "exit_price": exit_price,
                    "result": result,
                    "profit": profit,
                })

                if not allow_overlap:
                    t += duration_ticks
                else:
                    t += 1
            else:
                t += 1

        total_trades = len(trades)
        win_rate = round((wins / total_trades) * 100.0, 2) if total_trades > 0 else 0.0
        total_profit = round(sum(trade["profit"] for trade in trades), 2)

        # Cálculo de Max Drawdown e perdas consecutivas máximas
        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        max_consecutive_losses = 0
        current_consecutive_losses = 0

        for trade in trades:
            equity += trade["profit"]
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown

            if trade["result"] == "LOSS":
                current_consecutive_losses += 1
                if current_consecutive_losses > max_consecutive_losses:
                    max_consecutive_losses = current_consecutive_losses
            else:
                current_consecutive_losses = 0

        return {
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_profit": total_profit,
            "max_drawdown": round(max_drawdown, 2),
            "max_consecutive_losses": max_consecutive_losses,
            "parameters": parameters,
            "trades": trades,
        }

    def rank_strategies(
        self,
        parameter_combinations: list[dict[str, Any]],
        duration_ticks: int = 5,
        indicator_cls: type = IchimokuIndicator,
        allow_overlap: bool = False,
    ) -> list[dict[str, Any]]:
        """Executa múltiplas variações de parâmetros e retorna a lista classificada.

        A ordenação prioriza:
          1. Maior taxa de acerto ('win_rate' decrescente)
          2. Menor rebaixamento máximo ('max_drawdown' crescente)
          3. Maior lucro acumulado ('total_profit' decrescente)

        :param parameter_combinations: Lista de dicionários com parâmetros do indicador.
        :param duration_ticks: Duração do contrato em ticks.
        :param indicator_cls: Classe do indicador a ser instanciada (padrão: IchimokuIndicator).
        :param allow_overlap: Se False, contratos não se sobrepõem no tempo.
        :return: Lista de resultados ranqueados.
        """
        results: list[dict[str, Any]] = []

        for params in parameter_combinations:
            try:
                indicator = indicator_cls(**params)
                result = self.run_strategy(
                    indicator_instance=indicator,
                    duration_ticks=duration_ticks,
                    allow_overlap=allow_overlap,
                )
                results.append(result)
            except Exception as e:
                logger.warning("Falha ao simular estratégia com parâmetros %s: %s", params, e)

        # Ordenação: -win_rate (descendente), max_drawdown (ascendente), -total_profit (descendente)
        ranked = sorted(
            results,
            key=lambda r: (-r["win_rate"], r["max_drawdown"], -r["total_profit"]),
        )
        return ranked
