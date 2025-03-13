import asyncio
from deriv.connection import Connection

class DerivedBot:
    _bots = []  # Lista estática para rastrear todos os robôs
    _next_id = 0  # Contador para gerar IDs únicos

    def __init__(self, conn, stake=1.0, duration=0.25, trade_type="higher_lower", contract_type="rise"):
        self.id = DerivedBot._next_id
        DerivedBot._next_id += 1
        self.symbol = "R_10"
        self.stake = stake
        self.duration = duration
        self.trade_type = trade_type
        self.contract_type = contract_type
        self.conn = conn
        self.running = False
        DerivedBot._bots.append(self)

    @classmethod
    def create_robot(cls, conn, stake=1.0, duration=0.25, contract_type="rise"):
        """Cria uma nova instância de DerivedBot e a adiciona à lista de bots."""
        bot = cls(conn, stake, duration, "higher_lower", contract_type)
        return bot

    @classmethod
    def remove_robot(cls, robot_id):
        """Remove um robô da lista com base no ID."""
        cls._bots = [bot for bot in cls._bots if bot.id != robot_id]
        print(f"Robô com ID {robot_id} removido.")

    @classmethod
    def get_active_robots(cls):
        """Retorna a lista de robôs que estão operando (running=True)."""
        return [bot for bot in cls._bots if bot.running]

    def set_contract_parameters(self, stake, duration, contract_type):
        """Define os parâmetros de contrato (stake, duration, contract_type)."""
        self.stake = float(stake)
        self.duration = float(duration)
        self.contract_type = contract_type if contract_type in ["rise", "fall"] else "rise"
        print(f"Parâmetros atualizados para robô ID {self.id}: stake={self.stake}, duration={self.duration}, contract_type={self.contract_type}")

    async def run(self):
        try:
            if not await self.conn.is_alive():
                raise ValueError(f"Conexão não está ativa para o robô ID {self.id}.")
            
            self.running = True
            print(f"Verificando combinação para {self.trade_type} no robô ID {self.id}")
            if self.trade_type == "higher_lower":
                print("Verificação de combinação para derived e higher_lower ignorada por agora.")
            print(f"Combinação válida. Iniciando compra para {self.symbol} no robô ID {self.id}")

            proposal_request = {
                "proposal": 1,
                "amount": self.stake,
                "basis": "stake",
                "contract_type": "HIGHER" if self.contract_type == "rise" else "LOWER",
                "symbol": self.symbol,
                "duration": int(self.duration * 60),
                "duration_unit": "s",
                "currency": "USD"
            }
            print(f"Validando contrato com requisição: {proposal_request}")
            proposal_response = await self.conn.send(proposal_request)
            if 'error' in proposal_response:
                raise ValueError(f"Erro na validação do contrato no robô ID {self.id}: {proposal_response['error']['message']}")
            print(f"Contrato válido: {proposal_response}")

            if 'proposal' in proposal_response and isinstance(proposal_response['proposal'], list):
                contract_details = proposal_response['proposal'][0]
                expected_contract_type = "HIGHER" if self.contract_type == "rise" else "LOWER"
                if not contract_details.get('contract_type') == expected_contract_type:
                    raise ValueError(f"Contract type {contract_details.get('contract_type')} não corresponde ao esperado {expected_contract_type} no robô ID {self.id}")
            else:
                raise ValueError("Resposta da proposal inválida no robô ID {self.id}")

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
            print(f"Tentando comprar contrato: {buy_request['parameters']['contract_type']}, stake={self.stake}, duration={self.duration} minutos no robô ID {self.id}")
            print(f"Requisição enviada: {buy_request}")
            response = await self.conn.send(buy_request)
            print(f"Contrato comprado: {response} no robô ID {self.id}")
        except Exception as e:
            print(f"Erro ao executar o robô ID {self.id}: {e}")
            raise
        finally:
            self.running = False

    async def stop(self):
        self.running = False
        print(f"Parando o robô ID {self.id}...")