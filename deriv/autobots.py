from deriv.trade_parameters import TradeParameters
from deriv.connect import Connection
from deriv.journal import Journal

class DerivedBot:
    def __init__(self, symbol, stake, duration, trade_type, contract_type):
        self.conn = Connection()
        self.journal = Journal(self.conn.account_type)
        self.symbol = symbol
        self.stake = stake
        self.duration = duration
        self.trade_type = trade_type
        self.contract_type = contract_type
        self.params = TradeParameters()

    async def run(self):
        if await self.params.is_valid_combination("derived", self.trade_type):
            print(f"Robô iniciado para {self.symbol} com {self.trade_type}")
            contract_id = await self.buy_contract()
            await self.monitor_contract(contract_id)
        else:
            print("Combinação inválida!")

    async def buy_contract(self):
        trade = {
            "buy": 1,
            "price": self.stake,
            "parameters": {
                "contract_type": self.contract_type,
                "symbol": self.symbol,
                "duration": self.duration,
                "duration_unit": "m",
                "currency": "USD",
                "amount": self.stake,
                "basis": "stake"
            }
        }
        response = await self.conn.send_request(trade)
        contract_id = response["buy"]["contract_id"]
        print(f"Contrato comprado, ID: {contract_id}")
        return contract_id

    async def monitor_contract(self, contract_id):
        while True:
            details = await self.conn.send_request({"proposal_open_contract": 1, "contract_id": contract_id})
            if details.get("is_sold", 0) == 1:
                profit = details.get("profit", 0)
                status = details.get("status", "unknown")
                self.journal.log_trade(contract_id, profit, status)
                print(f"Lucro/Perda: ${profit:.2f}, Status: {status}")
                break
            await asyncio.sleep(1)