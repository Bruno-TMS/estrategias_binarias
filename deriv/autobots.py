import asyncio
from deriv.connect import Connection

class DerivedBot:
    def __init__(self, symbol="R_10", stake=1.0, duration=0.25, trade_type="higher_lower", contract_type="rise"):
        self.symbol = symbol
        self.stake = stake
        self.duration = duration
        self.trade_type = trade_type
        self.contract_type = contract_type
        self.conn = Connection()
        self.running = True

    async def run(self):
        try:
            print(f"Verificando combinação para {self.trade_type}")
            if self.trade_type == "higher_lower":
                print("Verificação de combinação para derived e higher_lower ignorada por agora.")
            print(f"Combinação válida. Iniciando compra para {self.symbol}")

            # Valida os parâmetros com uma chamada proposal
            proposal_request = {
                "proposal": 1,
                "amount": self.stake,
                "basis": "stake",
                "contract_type": "HIGHER" if self.contract_type == "rise" else "LOWER",
                "symbol": self.symbol,
                "duration": int(self.duration * 60),  # Converte minutos para segundos
                "duration_unit": "s",
                "currency": "USD"
            }
            print(f"Validando contrato com requisição: {proposal_request}")
            proposal_response = await self.conn.send(proposal_request)
            if 'error' in proposal_response:
                raise ValueError(f"Erro na validação do contrato: {proposal_response['error']['message']}")
            print(f"Contrato válido: {proposal_response}")

            # Extrai o contract_type e outros parâmetros da resposta da proposal
            if 'proposal' in proposal_response and isinstance(proposal_response['proposal'], list):
                contract_details = proposal_response['proposal'][0]
                if not contract_details.get('contract_type') == ("HIGHER" if self.contract_type == "rise" else "LOWER"):
                    raise ValueError(f"Contract type {contract_details.get('contract_type')} não corresponde ao esperado {self.contract_type}")
            else:
                raise ValueError("Resposta da proposal inválida")

            # Configura a requisição de compra usando a resposta da proposal
            buy_request = {
                "buy": 1,
                "price": self.stake,
                "parameters": {
                    "contract_type": "HIGHER" if self.contract_type == "rise" else "LOWER",
                    "symbol": self.symbol,
                    "duration": int(self.duration * 60),
                    "duration_unit": "s",
                    "currency": "USD",
                    "amount": self.stake,
                    "basis": "stake"
                }
            }
            print(f"Tentando comprar contrato: {buy_request['parameters']['contract_type']}, stake={self.stake}, duration={self.duration} minutos")
            print(f"Requisição enviada: {buy_request}")
            response = await self.conn.send(buy_request)
            print(f"Contrato comprado: {response}")
        except Exception as e:
            print(f"Erro ao executar o robô: {e}")
            raise

    async def stop(self):
        self.running = False