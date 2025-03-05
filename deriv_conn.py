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
        try:
            self.api = DerivAPI(app_id=self.app_id)
            auth_response = await self.api.authorize(self.api_token)
            print("Conectado à Deriv API com sucesso!", auth_response)
        except Exception as e:
            print(f"Erro ao conectar: {e}")

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
        print("Resposta completa do saldo:", balance)
        return balance['balance']['balance']

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
                "currency": "USD"
            }
        }
        if barrier:
            trade["parameters"]["barrier"] = barrier
        print("Requisição enviada:", trade)
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
        """Testa a conexão e o saldo."""
        await self.connect()
        balance = await self.get_balance()
        print(f"Saldo da conta: {balance}")
        await self.disconnect()

# Executa o teste
async def main():
    deriv = DerivConnection()
    await deriv.test()

if __name__ == "__main__":
    asyncio.run(main())