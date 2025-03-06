import talib
import numpy as np

class Indicador:
    def __init__(self, data):
        self.data = np.array(data)

    def calcular_sma(self, period):
        return talib.SMA(self.data, timeperiod=period)[-1]

    def calcular_rsi(self, period):
        return talib.RSI(self.data, timeperiod=period)[-1]

    def calcular_ichimoku(self, high, low, close):
        # Implementação básica do Ichimoku (a ser detalhada)
        return talib.ICHIMOKU(high, low)[0][-1]  # Tenkan-sen como exemplo