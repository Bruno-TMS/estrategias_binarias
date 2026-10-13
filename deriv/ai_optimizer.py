"""Módulo central de inteligência analítica e otimização hiperparamétrica para Ichimoku."""

import logging
from typing import Any, Literal, TypedDict
import numpy as np

logger = logging.getLogger(__name__)


class IchimokuParams(TypedDict):
    """Hiperparâmetros estruturados para configuração do indicador Ichimoku."""

    tenkan_period: int
    kijun_period: int
    senkou_b_period: int
    displacement: int


class MarketRegimeDiagnosis(TypedDict):
    """Diagnóstico contextual do regime de mercado inferido pelos backtests."""

    regime: str
    directional_bias: str
    recommended_profile: str
    confidence_score: float
    description: str


class StrategyRecommendation(TypedDict):
    """Resultado da recomendação multivariável da melhor calibração de estratégia."""

    strategy: dict[str, Any] | None
    score: float
    regime_diagnosis: MarketRegimeDiagnosis
    metrics_summary: dict[str, Any]


class PostTradeDiagnosis(TypedDict):
    """Diagnóstico de pós-operação com desvio realizado e sugestões de adaptação."""

    trade_id: Any
    result: str
    expected_direction: str
    price_delta: float
    efficiency_score: float
    recommendation: str
    action_code: str
    details: dict[str, Any]


class AIOptimizer:
    """Otimizador analítico para geração de hiperparâmetros, avaliação multivariável

    e diagnóstico adaptativo pós-trade para estratégias de opções digitais (Rise/Fall).
    """

    @staticmethod
    def generate_grid(max_combinations: int = 100) -> list[dict[str, int]]:
        """Gera combinações válidas respeitando rigorosamente a hierarquia matemática do Ichimoku.

        Restrições físicas do Ichimoku:
          - tenkan_period: valores entre 4 e 16
          - kijun_period: valores entre 12 e 36 (com tenkan < kijun)
          - senkou_b_period: valores entre 24 e 72 (com kijun < senkou_b)
          - displacement: proporcional ao kijun (displacement = kijun)

        Retorna uma lista determinística de até `max_combinations` variações ordenadas
        pelos perfis:
          1. Scalping agressivo (períodos rápidos, reação ágil)
          2. Intermediário (equilíbrio entre suavização e volatilidade)
          3. Conservador (filtros maiores para consolidação de tendência)
        """
        if max_combinations <= 0:
            return []

        scalping: list[dict[str, int]] = []
        intermediario: list[dict[str, int]] = []
        conservador: list[dict[str, int]] = []

        # Configuração clássica de referência de Goichi Hosoda
        classic = {
            "tenkan_period": 9,
            "kijun_period": 26,
            "senkou_b_period": 52,
            "displacement": 26,
        }

        # Varredura do espaço amostral com proporções harmônicas do Ichimoku
        for t in range(4, 17):
            for k in range(12, 37):
                if t >= k:
                    continue
                for b in range(24, 73):
                    if k >= b:
                        continue

                    # Relações de proporção entre médias temporais
                    ratio_tk = k / t
                    ratio_bk = b / k
                    if not (1.8 <= ratio_tk <= 3.5 and 1.8 <= ratio_bk <= 2.5):
                        continue

                    item: dict[str, int] = {
                        "tenkan_period": t,
                        "kijun_period": k,
                        "senkou_b_period": b,
                        "displacement": k,
                    }

                    # Segmentação por perfis de volatilidade/tempo
                    if k <= 18 and b <= 38:
                        scalping.append(item)
                    elif k <= 27 and b <= 56:
                        intermediario.append(item)
                    else:
                        conservador.append(item)

        # Garante que o clássico (9, 26, 52, 26) esteja na vanguarda do perfil intermediário
        if classic in intermediario:
            intermediario.remove(classic)
        intermediario.insert(0, classic)

        # Particionamento balanceado dos perfis
        n_scalp = max_combinations // 3 + (1 if max_combinations % 3 > 0 else 0)
        n_inter = max_combinations // 3 + (1 if max_combinations % 3 > 1 else 0)
        n_cons = max_combinations - (n_scalp + n_inter)

        def _sample(lst: list[dict[str, int]], count: int) -> list[dict[str, int]]:
            if not lst or count <= 0:
                return []
            if count >= len(lst):
                return list(lst)
            indices = [int(i * len(lst) / count) for i in range(count)]
            return [lst[idx] for idx in indices]

        grid = (
            _sample(scalping, n_scalp)
            + _sample(intermediario, n_inter)
            + _sample(conservador, n_cons)
        )
        return grid[:max_combinations]

    @staticmethod
    def evaluate_and_recommend(
        backtest_results: list[dict[str, Any]],
        min_trades: int = 20,
    ) -> StrategyRecommendation:
        """Avalia os resultados do backtest através de função objetivo multivariável.

        Filtra estratégias com significância estatística (total_trades >= min_trades).
        Combina:
          - Vantagem percentual da taxa de acerto acima do breakeven
          - Relação Retorno / Drawdown (Calmar simplificado)
          - Índice Sharpe aproximado da distribuição de resultados
        """
        if not backtest_results:
            empty_diagnosis: MarketRegimeDiagnosis = {
                "regime": "INDEFINIDO",
                "directional_bias": "NEUTRO",
                "recommended_profile": "nenhum",
                "confidence_score": 0.0,
                "description": "Nenhum resultado de backtest foi fornecido para avaliação.",
            }
            return {
                "strategy": None,
                "score": 0.0,
                "regime_diagnosis": empty_diagnosis,
                "metrics_summary": {},
            }

        # Filtra candidatos com volume mínimo de operações
        eligible = [
            r for r in backtest_results if r.get("total_trades", 0) >= min_trades
        ]
        fallback_used = False
        if not eligible:
            fallback_used = True
            eligible = [r for r in backtest_results if r.get("total_trades", 0) > 0]
            if not eligible:
                eligible = backtest_results

        scored_candidates: list[tuple[float, dict[str, Any]]] = []

        for candidate in eligible:
            total_trades = candidate.get("total_trades", 0)
            win_rate = float(candidate.get("win_rate", 0.0))
            total_profit = float(candidate.get("total_profit", 0.0))
            max_drawdown = float(candidate.get("max_drawdown", 0.0))
            trades = candidate.get("trades", [])

            # 1. Edge sobre o breakeven teórico (51.28% para payout de 95%)
            win_rate_edge = win_rate - 52.0

            # 2. Relação Retorno x Drawdown
            calmar_ratio = total_profit / max(1.0, max_drawdown)

            # 3. Sharpe Ratio simplificado das operações
            if trades:
                profits = [float(t.get("profit", 0.0)) for t in trades]
                arr_p = np.array(profits, dtype=np.float64)
                std_p = float(np.std(arr_p))
                sharpe = float(np.mean(arr_p) / std_p) if std_p > 0 else 0.0
            else:
                wins = candidate.get("wins", 0)
                losses = candidate.get("losses", 0)
                mean_p = total_profit / total_trades if total_trades > 0 else 0.0
                var_p = (
                    (wins * (0.95 - mean_p) ** 2 + losses * (-1.0 - mean_p) ** 2)
                    / total_trades
                    if total_trades > 0
                    else 1.0
                )
                std_p = np.sqrt(var_p) if var_p > 0 else 1.0
                sharpe = float(mean_p / std_p) if std_p > 0 else 0.0

            # Função objetivo multivariável
            composite_score = round(
                (win_rate_edge * 1.5) + (calmar_ratio * 2.0) + (sharpe * 5.0),
                4,
            )
            scored_candidates.append((composite_score, candidate))

        # Ordena pelo maior composite_score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_strategy = scored_candidates[0]

        # Diagnóstico contextual de regime de mercado
        params = best_strategy.get("parameters", {})
        kijun = params.get("kijun_period", 26)
        wr = best_strategy.get("win_rate", 0.0)
        trades = best_strategy.get("trades", [])

        if kijun <= 18:
            profile = "scalping"
        elif kijun <= 27:
            profile = "intermediario"
        else:
            profile = "conservador"

        # Identificação de viés direcional (CALL vs PUT)
        call_trades = sum(1 for t in trades if t.get("signal") == "CALL")
        put_trades = sum(1 for t in trades if t.get("signal") == "PUT")

        if call_trades > put_trades * 1.4:
            bias = "CALL_DOMINANTE"
        elif put_trades > call_trades * 1.4:
            bias = "PUT_DOMINANTE"
        else:
            bias = "EQUILIBRADO"

        # Caracterização de regime
        if wr >= 58.0:
            regime = "TENDENCIA_CONSOLIDADA"
            desc = "Mercado com direcionalidade nítida e alta aderência à Nuvem."
            confidence = 88.0 if not fallback_used else 65.0
        elif wr >= 52.5:
            regime = "ALTA_VOLATILIDADE_SCALPING"
            desc = "Mercado veloz favorável a oscilações rápidas com filtros ágeis."
            confidence = 75.0 if not fallback_used else 55.0
        else:
            regime = "LATERALIZACAO_ERRATICA"
            desc = "Mercado sem tendência clara; risco elevado de falsos rompimentos."
            confidence = 45.0

        diagnosis: MarketRegimeDiagnosis = {
            "regime": regime,
            "directional_bias": bias,
            "recommended_profile": profile,
            "confidence_score": confidence,
            "description": desc,
        }

        return {
            "strategy": best_strategy,
            "score": best_score,
            "regime_diagnosis": diagnosis,
            "metrics_summary": {
                "win_rate": wr,
                "total_profit": best_strategy.get("total_profit", 0.0),
                "max_drawdown": best_strategy.get("max_drawdown", 0.0),
                "total_trades": best_strategy.get("total_trades", 0),
                "sample_warning": fallback_used,
            },
        }

    @staticmethod
    def post_trade_analysis(
        trade_record: dict[str, Any],
        current_market_state: dict[str, Any],
    ) -> PostTradeDiagnosis:
        """Analisa o resultado após o encerramento da ordem (WIN ou LOSS).

        Calcula o desvio entre o comportamento esperado e o realizado, emitindo
        recomendações adaptativas para o gerenciador de risco e filtros técnicos.
        """
        trade_id = trade_record.get("trade_id", "N/A")
        result = str(trade_record.get("result", "UNKNOWN")).upper()
        signal = str(trade_record.get("signal", "CALL")).upper()
        entry_price = float(trade_record.get("entry_price", 0.0))
        exit_price = float(trade_record.get("exit_price", entry_price))

        # Cálculo do deslocamento realizado
        if signal == "CALL":
            expected_direction = "ALTA (Preço de saída > Entrada)"
            price_delta = round(exit_price - entry_price, 4)
        else:
            expected_direction = "BAIXA (Preço de saída < Entrada)"
            price_delta = round(entry_price - exit_price, 4)

        # Mapeamento do estado atual da Nuvem de Ichimoku
        price_vs_kumo = current_market_state.get("price_vs_kumo", "INSIDE")
        tk_cross = current_market_state.get("tk_cross", "EQUAL")

        # Análise diagnóstica e tomada de decisão
        if result == "LOSS":
            efficiency_score = 0.0
            if price_vs_kumo == "INSIDE":
                recommendation = (
                    "O preço regrediu para o interior da Nuvem (Kumo), caracterizando falso rompimento. "
                    "Recomenda-se aumentar o período senkou_b_period para maior filtragem de ruído."
                )
                action_code = "EXPAND_CLOUD"
            elif (signal == "CALL" and tk_cross == "BEARISH") or (
                signal == "PUT" and tk_cross == "BULLISH"
            ):
                recommendation = (
                    "Ocorreu reversão de momentum adversa entre Tenkan e Kijun logo após o disparo. "
                    "Recomenda-se acionar freio derivativo temporário até alinhamento direcional."
                )
                action_code = "DERIVATIVE_BRAKE"
            else:
                recommendation = (
                    "Perda pontual decorrente de volatilidade adversa. Manter calibração se a taxa de "
                    "acerto global permanecer acima do limiar estatístico."
                )
                action_code = "MAINTAIN"
        else:  # "WIN"
            # Avalia se a vitória foi expressiva ou marginal
            price_movement_ratio = abs(price_delta) / entry_price if entry_price > 0 else 0.0
            if price_movement_ratio < 0.0001:
                efficiency_score = 65.0
                recommendation = (
                    "Vitória marginal por variação mínima de preço. Recomenda-se avaliar redução do "
                    "duration_ticks para capturar o impulso inicial da formação."
                )
                action_code = "TIGHTEN_DURATION"
            else:
                efficiency_score = 95.0
                recommendation = (
                    "Vitória sólida confirmando alinhamento pleno de Tenkan/Kijun e afastamento da Nuvem. "
                    "Manter calibração vencedora inalterada."
                )
                action_code = "MAINTAIN"

        return {
            "trade_id": trade_id,
            "result": result,
            "expected_direction": expected_direction,
            "price_delta": price_delta,
            "efficiency_score": efficiency_score,
            "recommendation": recommendation,
            "action_code": action_code,
            "details": {
                "signal": signal,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "price_vs_kumo": price_vs_kumo,
                "tk_cross": tk_cross,
            },
        }
