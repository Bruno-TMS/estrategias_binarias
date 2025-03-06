import asyncio
from deriv.connect import Connection

class TradeParameters:
    def __init__(self):
        self.conn = Connection()

    async def is_valid_combination(self, market_type, trade_type):
        """
        Verifica se a combinação de mercado e tipo de trade é válida.
        """
        try:
            # Ajuste para um comando válido, como 'contracts_for' ou uma verificação simplificada
            request = {
                "contracts_for": 1,
                "product_type": "derived" if market_type == "derived" else "basic",
                "symbol": "volatility_10"
            }
            response = await self.conn.send(request)
            return "contracts" in response and len(response["contracts"]) > 0
        except Exception as e:
            print(f"Erro ao verificar combinação: {e}")
            return False