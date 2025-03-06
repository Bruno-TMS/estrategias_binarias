from deriv.analises_tecnicas import Indicador

class Estrategia:
    def __init__(self, data):
        self.indicador = Indicador(data)

    def estrategia_sma(self, period):
        sma = self.indicador.calcular_sma(period)
        return sma > self.indicador.data[-1]  # Exemplo: compra se preço > SMA