import asyncio
from deriv_api import DerivAPI
from config import APP_ID, API_TOKEN, SYMBOL, INITIAL_STAKE

class DerivConnection:
    def __init__(self):
        """Inicializa a conexão com a Deriv API."""
        self.app_id = APP_ID
        self.api_token = API_TOKEN
        self.api = None

    async def connect(self):
        """Conecta à Deriv API."""
        try:
            self.api = DerivAPI(app_id=self.app_id)
            auth_response = await self.api.authorize(self.api_token)
            print("Conectado à Deriv API:", auth_response)
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
        print("Saldo da conta:", balance)
        return balance['balance']['balance']

    async def buy_contract(self, contract_type, symbol, duration, stake):
        """Compra um contrato e retorna o contract_id."""
        if not self.api:
            await self.connect()
        trade = {
            "buy": 1,
            "price": 1.0,  # Preço máximo suficiente para cobrir o contrato
            "parameters": {
                "contract_type": contract_type,
                "symbol": symbol,
                "duration": duration,
                "duration_unit": "m",
                "currency": "USD",
                "amount": stake,
                "basis": "stake"
            }
        }
        print("Requisição enviada:", trade)
        response = await self.api.buy(trade)
        print("Resposta da compra:", response)
        return response["buy"]["contract_id"]

    async def get_contract_details(self, contract_id):
        """Obtém detalhes de um contrato."""
        if not self.api:
            await self.connect()
        details = await self.api.contract({"contract_id": contract_id})
        return details

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

async def test_buy():
    """Testa a compra de um contrato CALL."""
    deriv = DerivConnection()
    await deriv.connect()
    balance = await deriv.get_balance()
    print(f"Saldo inicial: {balance}")
    contract_id = await deriv.buy_contract("CALL", SYMBOL, 5, INITIAL_STAKE)
    print(f"Contrato comprado, ID: {contract_id}")
    profit = await deriv.wait_contract_result(contract_id)
    print(f"Lucro/Perda do contrato: {profit}")
    final_balance = await deriv.get_balance()
    print(f"Saldo final: {final_balance}")
    await deriv.disconnect()

if __name__ == "__main__":
    asyncio.run(test_buy())