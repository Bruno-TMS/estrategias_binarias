import asyncio
from deriv_api import DerivAPI
from config import APP_ID, API_TOKEN

class DerivConnection:
    def __init__(self):
        """Inicializa a conexão com a Deriv API usando valores do config."""
        self.app_id = APP_ID
        self.api_token = API_TOKEN
        self.api = None

    async def connect(self):
        """Conecta à Deriv API."""
        self.api = DerivAPI(app_id=self.app_id)
        await self.api.authorize(self.api_token)
        print("Conectado à Deriv API com sucesso!")

    async def disconnect(self):
        """Desconecta da API."""
        if self.api:
            await self.api.disconnect()
            print("Desconectado da Deriv API.")

    async def get_balance(self):
        """Retorna o saldo da conta."""
        if not self.api:
            await self.connect()
        balance = await self.api.balance()
        print("Resposta completa do saldo:", balance)  # Depuração
        # Ajuste com base na estrutura real da resposta
        return balance.get('total', {}).get('amount', 0)  # Ajustado para estrutura comum

    async def buy_contract(self, contract_type, symbol, duration, stake, barrier=None):
        """Compra um contrato e retorna o contract_id."""
        if not self.api:
            await self.connect()
        trade = {
            "buy": 1,
            "price": stake,
            "parameters": {
                "contract_type": contract_type,
                "symbol": symbol,
                "duration": duration,
                "duration_unit": "s",
            }
        }
        if barrier:
            trade["parameters"]["barrier"] = barrier
        response = await self.api.buy(trade)
        return response["buy"]["contract_id"]

    async def get_contract_details(self, contract_id):
        """Obtém detalhes de um contrato."""
        if not self.api:
            await self.connect()
        details = await self.api.contract({"contract_id": contract_id})
        return details

    async def subscribe_ticks(self, symbol, callback):
        """Subscreve a um stream de ticks."""
        if not self.api:
            await self.connect()
        subscription = await self.api.subscribe({
            "ticks": symbol,
            "subscribe": 1
        })
        async for tick in subscription:
            await callback(tick["tick"]["quote"])

    async def tick_callback(self, price):
        """Callback para ticks."""
        print(f"Preço atual: {price}")

    async def wait_contract_result(self, contract_id):
        """Espera o contrato terminar e retorna o lucro/perda."""
        if not self.api:
            await self.connect()
        while True:
            details = await self.get_contract_details(contract_id)
            if details.get("is_sold", 0) == 1:
                profit = details.get("profit", 0)
                return profit
            await asyncio.sleep(1)

    async def test(self):
        """Teste básico da conexão."""
        await self.connect()
        balance = await self.get_balance()
        print(f"Saldo inicial: {balance}")
        contract_id = await self.buy_contract("CALL", "R_10", 300, 0.35, "+0.1")
        print(f"Contrato ID: {contract_id}")
        profit = await self.wait_contract_result(contract_id)
        print(f"Resultado do contrato: {profit}")
        await self.subscribe_ticks("R_10", self.tick_callback)
        await asyncio.sleep(10)
        await self.disconnect()

if __name__ == "__main__":
    conn = DerivConnection()
    asyncio.run(conn.test())