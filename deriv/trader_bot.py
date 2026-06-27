from app.services.deriv_service import DerivService


class DerivedBot:
    _bots = []
    _next_id = 0

    def __init__(
        self,
        service: DerivService,
        stake: float = 1.0,
        duration: float = 0.25,
        trade_type: str = "higher_lower",
        contract_type: str = "rise",
    ):
        self.id = DerivedBot._next_id
        DerivedBot._next_id += 1

        self.service = service

        self.symbol = "R_10"
        self.stake = stake
        self.duration = duration
        self.trade_type = trade_type
        self.contract_type = contract_type

        self.running = False

        DerivedBot._bots.append(self)

    # ----------------------------
    # FACTORY
    # ----------------------------
    @classmethod
    def create_robot(cls, service: DerivService, **kwargs):
        return cls(service, **kwargs)

    @classmethod
    def remove_robot(cls, robot_id: int):
        cls._bots = [bot for bot in cls._bots if bot.id != robot_id]

    @classmethod
    def get_active_robots(cls):
        return [bot for bot in cls._bots if bot.running]

    # ----------------------------
    # CONFIG
    # ----------------------------
    def set_contract_parameters(self, stake, duration, contract_type):
        self.stake = float(stake)
        self.duration = float(duration)
        self.contract_type = contract_type if contract_type in ["rise", "fall"] else "rise"

    # ----------------------------
    # EXECUÇÃO
    # ----------------------------
    async def run(self):
        try:
            if not self.service.is_alive:
                await self.service.connect()

            self.running = True

            proposal_request = {
                "proposal": 1,
                "amount": self.stake,
                "basis": "stake",
                "contract_type": "HIGHER" if self.contract_type == "rise" else "LOWER",
                "symbol": self.symbol,
                "duration": int(self.duration * 60),
                "duration_unit": "s",
                "currency": "USD",
            }

            proposal_response = await self.service.send(proposal_request)

            if "error" in proposal_response:
                raise ValueError(proposal_response["error"]["message"])

            # validação
            if "proposal" not in proposal_response:
                raise ValueError("Proposal inválida")

            # compra
            buy_request = {
                "buy": 1,
                "price": self.stake,
                "parameters": proposal_request | {
                    "amount": self.stake,
                    "basis": "stake",
                },
            }

            response = await self.service.send(buy_request)

            return response

        except Exception as e:
            raise RuntimeError(f"Erro no bot {self.id}: {e}")

        finally:
            self.running = False

    async def stop(self):
        self.running = False