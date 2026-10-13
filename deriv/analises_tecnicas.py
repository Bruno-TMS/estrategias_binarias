from typing import Any
import numpy as np


def _rolling_midpoint(arr: np.ndarray, period: int) -> np.ndarray:
    """Calcula a média entre o ponto máximo e mínimo (max + min) / 2 em janela móvel."""
    n = len(arr)
    result = np.full(n, np.nan, dtype=np.float64)
    if n < period or period <= 0:
        return result

    windows = np.lib.stride_tricks.sliding_window_view(arr, window_shape=period)
    maxs = np.max(windows, axis=-1)
    mins = np.min(windows, axis=-1)
    result[period - 1 :] = (maxs + mins) / 2.0
    return result


def calculate_sma(prices: list[float] | np.ndarray, period: int = 14) -> np.ndarray:
    """Calcula a Média Móvel Simples (SMA) usando NumPy puro.

    Retorna um array com o mesmo comprimento de `prices`, com np.nan nos índices iniciais.
    """
    arr = np.asarray(prices, dtype=np.float64)
    n = len(arr)
    result = np.full(n, np.nan, dtype=np.float64)
    if n < period or period <= 0:
        return result

    windows = np.lib.stride_tricks.sliding_window_view(arr, window_shape=period)
    result[period - 1 :] = np.mean(windows, axis=-1)
    return result


def calculate_rsi(prices: list[float] | np.ndarray, period: int = 14) -> np.ndarray:
    """Calcula o Índice de Força Relativa (RSI de Wilder) usando NumPy puro.

    Retorna um array com o mesmo comprimento de `prices`, com valores entre 0 e 100.
    """
    arr = np.asarray(prices, dtype=np.float64)
    n = len(arr)
    result = np.full(n, np.nan, dtype=np.float64)
    if n <= period or period <= 0:
        return result

    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))

    if avg_loss == 0.0:
        result[period] = 100.0 if avg_gain > 0 else 50.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        idx = i + 1
        if avg_loss == 0.0:
            result[idx] = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            result[idx] = 100.0 - (100.0 / (1.0 + rs))

    return result


class IchimokuIndicator:
    """Indicador Ichimoku Kinko Hyo em Python puro e vetorizado com NumPy.

    Desacoplado de bibliotecas compiladas C (zero TA-Lib), configurável para calibração manual
    ou via algoritmos de otimização/IA.
    """

    def __init__(
        self,
        tenkan_period: int = 9,
        kijun_period: int = 26,
        senkou_b_period: int = 52,
        displacement: int = 26,
    ) -> None:
        if tenkan_period <= 0 or kijun_period <= 0 or senkou_b_period <= 0 or displacement <= 0:
            raise ValueError("Todos os períodos do IchimokuIndicator devem ser inteiros positivos.")

        self.tenkan_period = tenkan_period
        self.kijun_period = kijun_period
        self.senkou_b_period = senkou_b_period
        self.displacement = displacement

    def calculate(self, prices: list[float] | np.ndarray) -> dict[str, np.ndarray]:
        """Calcula os componentes do Ichimoku para a série de preços informada.

        Retorna dicionário contendo arrays NumPy para:
          - tenkan: Linha de conversão
          - kijun: Linha de base
          - senkou_span_a: Primeira fronteira da nuvem (deslocada no tempo)
          - senkou_span_b: Segunda fronteira da nuvem (deslocada no tempo)
          - chikou: Linha de atraso
          - senkou_a_raw: Fronteira A não deslocada (projeção futura)
          - senkou_b_raw: Fronteira B não deslocada (projeção futura)
        """
        arr = np.asarray(prices, dtype=np.float64)
        n = len(arr)

        tenkan = _rolling_midpoint(arr, self.tenkan_period)
        kijun = _rolling_midpoint(arr, self.kijun_period)
        senkou_b_raw = _rolling_midpoint(arr, self.senkou_b_period)
        senkou_a_raw = np.where(
            np.isnan(tenkan) | np.isnan(kijun),
            np.nan,
            (tenkan + kijun) / 2.0,
        )

        # Deslocamento histórico da Nuvem (Kumo):
        # A nuvem que interage com o preço no instante t foi projetada em (t - displacement).
        senkou_span_a = np.full(n, np.nan, dtype=np.float64)
        senkou_span_b = np.full(n, np.nan, dtype=np.float64)
        if n > self.displacement:
            senkou_span_a[self.displacement :] = senkou_a_raw[: -self.displacement]
            senkou_span_b[self.displacement :] = senkou_b_raw[: -self.displacement]

        # Chikou Span: Preço atual plotado 'displacement' períodos atrás
        chikou = np.full(n, np.nan, dtype=np.float64)
        if n > self.displacement:
            chikou[: n - self.displacement] = arr[self.displacement :]

        return {
            "tenkan": tenkan,
            "kijun": kijun,
            "senkou_span_a": senkou_span_a,
            "senkou_span_b": senkou_span_b,
            "chikou": chikou,
            # Aliases e valores projetados (para visualização/backtests avançados)
            "tenkan_sen": tenkan,
            "kijun_sen": kijun,
            "senkou_a": senkou_span_a,
            "senkou_b": senkou_span_b,
            "chikou_span": chikou,
            "senkou_a_raw": senkou_a_raw,
            "senkou_b_raw": senkou_b_raw,
        }

    def get_signal(self, prices: list[float] | np.ndarray) -> dict[str, Any]:
        """Avalia a posição do último preço relativo à Nuvem (Kumo) e cruzamento Tenkan/Kijun.

        Retorna:
          {
              "signal": "CALL" | "PUT" | "NEUTRO",
              "metrics": dict,
              "parameters": dict
          }
        """
        arr = np.asarray(prices, dtype=np.float64)
        n = len(arr)

        parameters = {
            "tenkan_period": self.tenkan_period,
            "kijun_period": self.kijun_period,
            "senkou_b_period": self.senkou_b_period,
            "displacement": self.displacement,
        }

        # Trata adequadamente históricos menores que o período máximo
        if n < self.senkou_b_period:
            return {
                "signal": "NEUTRO",
                "metrics": {
                    "reason": f"Histórico insuficiente ({n} < {self.senkou_b_period})",
                    "current_price": float(arr[-1]) if n > 0 else 0.0,
                    "tenkan": None,
                    "kijun": None,
                    "kumo_top": None,
                    "kumo_bottom": None,
                },
                "parameters": parameters,
            }

        data = self.calculate(arr)
        current_price = float(arr[-1])
        tenkan_val = float(data["tenkan"][-1])
        kijun_val = float(data["kijun"][-1])

        # Nuvem correspondente à barra atual:
        # Se a nuvem deslocada estiver disponível no índice atual (-1), usa-a.
        # Caso contrário (ex: entre senkou_b_period e senkou_b_period + displacement), usa o valor bruto mais recente.
        kumo_a = data["senkou_span_a"][-1]
        kumo_b = data["senkou_span_b"][-1]

        if np.isnan(kumo_a) or np.isnan(kumo_b):
            kumo_a = data["senkou_a_raw"][-1]
            kumo_b = data["senkou_b_raw"][-1]

        if np.isnan(kumo_a) or np.isnan(kumo_b) or np.isnan(tenkan_val) or np.isnan(kijun_val):
            return {
                "signal": "NEUTRO",
                "metrics": {
                    "reason": "Valores de Kumo ou Tenkan/Kijun contêm NaN",
                    "current_price": current_price,
                    "tenkan": tenkan_val if not np.isnan(tenkan_val) else None,
                    "kijun": kijun_val if not np.isnan(kijun_val) else None,
                    "kumo_top": None,
                    "kumo_bottom": None,
                },
                "parameters": parameters,
            }

        kumo_a = float(kumo_a)
        kumo_b = float(kumo_b)
        kumo_top = max(kumo_a, kumo_b)
        kumo_bottom = min(kumo_a, kumo_b)

        # Avaliação de sinal
        # CALL: Preço acima da Nuvem e Tenkan acima da Kijun (tendência altista)
        # PUT: Preço abaixo da Nuvem e Tenkan abaixo da Kijun (tendência baixista)
        # NEUTRO: Preço dentro da Nuvem ou indefinição/divergência
        if current_price > kumo_top and tenkan_val > kijun_val:
            signal = "CALL"
        elif current_price < kumo_bottom and tenkan_val < kijun_val:
            signal = "PUT"
        else:
            signal = "NEUTRO"

        price_pos = (
            "ABOVE"
            if current_price > kumo_top
            else ("BELOW" if current_price < kumo_bottom else "INSIDE")
        )
        tk_cross = (
            "BULLISH"
            if tenkan_val > kijun_val
            else ("BEARISH" if tenkan_val < kijun_val else "EQUAL")
        )

        return {
            "signal": signal,
            "metrics": {
                "current_price": current_price,
                "tenkan": tenkan_val,
                "kijun": kijun_val,
                "senkou_span_a": kumo_a,
                "senkou_span_b": kumo_b,
                "kumo_top": kumo_top,
                "kumo_bottom": kumo_bottom,
                "price_vs_kumo": price_pos,
                "tk_cross": tk_cross,
            },
            "parameters": parameters,
        }


class Indicador:
    """Classe de compatibilidade para código legado (ex: deriv/estrategias.py).

    Calcula indicadores utilizando funções puras em NumPy, sem dependência de TA-Lib.
    """

    def __init__(self, data: list[float] | np.ndarray) -> None:
        self.data = np.asarray(data, dtype=np.float64)

    def calcular_sma(self, period: int = 14) -> float:
        sma = calculate_sma(self.data, period=period)
        return float(sma[-1]) if len(sma) > 0 and not np.isnan(sma[-1]) else 0.0

    def calcular_rsi(self, period: int = 14) -> float:
        rsi = calculate_rsi(self.data, period=period)
        return float(rsi[-1]) if len(rsi) > 0 and not np.isnan(rsi[-1]) else 50.0

    def calcular_ichimoku(self, high=None, low=None, close=None) -> float:
        prices = close if close is not None else self.data
        indicator = IchimokuIndicator()
        res = indicator.calculate(prices)
        tenkan = res["tenkan"]
        return float(tenkan[-1]) if len(tenkan) > 0 and not np.isnan(tenkan[-1]) else 0.0