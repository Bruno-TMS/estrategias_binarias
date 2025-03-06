import asyncio
from deriv.connect import Connection

class TradeParameters:
    def __init__(self):
        self.conn = Connection()

    async def is_valid_combination(self, market_type, trade_type):
        """
        Retorna True por padrão, removendo a verificação temporariamente.
        """
        print(f"Verificação de combinação para {market_type} e {trade_type} ignorada por agora.")
        return True  # Temporariamente assume que a combinação é válida