"""Módulo de automação e execução de ordens com o TraderBot da Deriv."""

import logging
from typing import Any

from services.deriv_service import DerivService

logger = logging.getLogger(__name__)

CONTRACT_TYPE_ALIASES: dict[str, str] = {
    "rise": "CALL",
    "fall": "PUT",
    "call": "CALL",
    "put": "PUT",
    "higher": "HIGHER",
    "lower": "LOWER",
    "touch": "ONETOUCH",
    "notouch": "NOTOUCH",
    "matches": "DIGITMATCH",
    "differs": "DIGITDIFF",
    "even": "DIGITEVEN",
    "odd": "DIGITODD",
    "over": "DIGITOVER",
    "under": "DIGITUNDER",
}


class DerivedBot:
    """Robô de trading para execução assíncrona de ordens e gestão de risco na Deriv API."""

    _bots: list["DerivedBot"] = []
    _next_id: int = 0

    def __init__(
        self,
        service: DerivService,
        stake: float = 1.0,
        duration: int = 5,
        duration_unit: str = "t",
        symbol: str = "1HZ100V",
        contract_type: str = "CALL",
        currency: str = "USD",
        stop_loss: float = 0.0,
        stop_win: float = 0.0,
    ) -> None:
        self.id: int = DerivedBot._next_id
        DerivedBot._next_id += 1

        self.service: DerivService = service
        self.stake: float = float(stake)
        self.duration: int = int(duration)
        self.duration_unit: str = duration_unit
        self.symbol: str = symbol
        self.contract_type: str = contract_type
        self.currency: str = currency

        # Limites de risco e métricas da instância
        self.stop_loss: float = float(stop_loss)
        self.stop_win: float = float(stop_win)
        self.total_profit: float = 0.0
        self.win_count: int = 0
        self.loss_count: int = 0

        self.running: bool = False
        DerivedBot._bots.append(self)

    # ----------------------------
    # FACTORY E GERENCIAMENTO
    # ----------------------------
    @classmethod
    def create_robot(cls, service: DerivService, **kwargs) -> "DerivedBot":
        """Cria e registra uma nova instância do robô."""
        return cls(service, **kwargs)

    @classmethod
    def remove_robot(cls, robot_id: int) -> None:
        """Remove um robô do registro da classe."""
        cls._bots = [bot for bot in cls._bots if bot.id != robot_id]

    @classmethod
    def get_active_robots(cls) -> list["DerivedBot"]:
        """Retorna lista de robôs atualmente em execução."""
        return [bot for bot in cls._bots if bot.running]

    # ----------------------------
    # CONFIGURAÇÃO E RISCO
    # ----------------------------
    def set_contract_parameters(
        self,
        stake: float | None = None,
        duration: int | None = None,
        contract_type: str | None = None,
        duration_unit: str | None = None,
        symbol: str | None = None,
    ) -> None:
        """Atualiza os parâmetros de contrato configurados na instância."""
        if stake is not None:
            self.stake = float(stake)
        if duration is not None:
            self.duration = int(duration)
        if contract_type is not None:
            self.contract_type = contract_type
        if duration_unit is not None:
            self.duration_unit = duration_unit
        if symbol is not None:
            self.symbol = symbol

    def set_risk_limits(
        self, stop_loss: float | None = None, stop_win: float | None = None
    ) -> None:
        """Define os limites de Stop Loss e Stop Win da instância."""
        if stop_loss is not None:
            self.stop_loss = float(stop_loss)
        if stop_win is not None:
            self.stop_win = float(stop_win)

    def check_risk_limits(self) -> None:
        """Verifica se os limites de Stop Loss ou Stop Win foram atingidos.

        Lança RuntimeError se a operação violar a política de risco.
        """
        if self.stop_loss > 0 and self.total_profit <= -abs(self.stop_loss):
            raise RuntimeError(
                f"Limite de Stop Loss atingido (-{abs(self.total_profit):.2f} {self.currency}). Operação bloqueada."
            )
        if self.stop_win > 0 and self.total_profit >= abs(self.stop_win):
            raise RuntimeError(
                f"Meta de Stop Win atingida (+{self.total_profit:.2f} {self.currency}). Operação bloqueada."
            )

    def record_trade_result(self, profit: float) -> None:
        """Registra o resultado financeiro de uma operação concluída e atualiza métricas."""
        self.total_profit += float(profit)
        if profit > 0:
            self.win_count += 1
        elif profit < 0:
            self.loss_count += 1

    @property
    def total_trades(self) -> int:
        """Total de operações contabilizadas com resultado."""
        return self.win_count + self.loss_count

    @property
    def win_rate(self) -> float:
        """Taxa de acerto em porcentagem."""
        return (self.win_count / self.total_trades * 100.0) if self.total_trades > 0 else 0.0

    # ----------------------------
    # FLUXO CANÔNICO DE TRADING
    # ----------------------------
    async def get_proposal(
        self,
        symbol: str,
        contract_type: str,
        duration: int,
        duration_unit: str,
        stake: float,
        currency: str = "USD",
        barrier: str | None = None,
    ) -> dict[str, Any]:
        """Solicita cotação de proposta para um contrato na Deriv API.

        Retorna dicionário contendo:
        - proposal_id: ID único da proposta para compra
        - ask_price: preço/custo de compra da proposta
        - payout: valor a ser recebido em caso de vitória
        - spot: cotação atual de referência da proposta
        """
        if stake <= 0:
            raise ValueError("O valor de stake deve ser maior que zero.")
        if duration <= 0:
            raise ValueError("A duração do contrato deve ser maior que zero.")

        cleaned_symbol = symbol.strip() if symbol else ""
        if not cleaned_symbol:
            raise ValueError("O símbolo do ativo não pode ser vazio.")

        normalized_type = CONTRACT_TYPE_ALIASES.get(
            contract_type.lower(), contract_type.upper()
        )

        proposal_payload: dict[str, Any] = {
            "proposal": 1,
            "amount": float(stake),
            "basis": "stake",
            "contract_type": normalized_type,
            "currency": currency,
            "duration": int(duration),
            "duration_unit": duration_unit,
        }
        if barrier:
            proposal_payload["barrier"] = str(barrier)

        # Trata compatibilidade entre endpoints modernos (underlying_symbol) e clássicos (symbol)
        is_options = (
            "/options" in (self.service.client.ws_url or "")
            or self.service.client.is_public_mode
        )
        if is_options:
            proposal_payload["underlying_symbol"] = cleaned_symbol
        else:
            proposal_payload["symbol"] = cleaned_symbol

        if not self.service.is_alive:
            await self.service.connect()

        response = await self.service.send(proposal_payload)

        # Fallback resiliente caso o gateway exija alternância de chave do símbolo
        if "error" in response:
            err_msg = response["error"].get("message", "")
            if "Properties not allowed: symbol" in err_msg:
                proposal_payload.pop("symbol", None)
                proposal_payload["underlying_symbol"] = cleaned_symbol
                response = await self.service.send(proposal_payload)
            elif "Properties not allowed: underlying_symbol" in err_msg:
                proposal_payload.pop("underlying_symbol", None)
                proposal_payload["symbol"] = cleaned_symbol
                response = await self.service.send(proposal_payload)

        if "error" in response:
            error_data = response["error"]
            error_code = error_data.get("code")
            error_msg = error_data.get("message", "Erro desconhecido")

            if error_code in ("MarketClosed", "TradingSuspended"):
                raise RuntimeError(
                    f"Mercado fechado ou suspenso para '{cleaned_symbol}': {error_msg}"
                )
            if error_code in ("InvalidSymbol", "OfferingsInvalidSymbol"):
                raise ValueError(
                    f"Ativo '{cleaned_symbol}' não encontrado ou sem contratos disponíveis: {error_msg}"
                )
            raise RuntimeError(
                f"Erro ao obter proposta para '{cleaned_symbol}': {error_msg}"
            )

        proposal = response.get("proposal")
        if not proposal or not isinstance(proposal, dict):
            raise RuntimeError(
                f"Resposta inválida de proposta recebida para '{cleaned_symbol}': {response}"
            )

        proposal_id = proposal.get("id")
        ask_price = float(proposal.get("ask_price", 0.0))
        payout = float(proposal.get("payout", 0.0))
        spot = float(proposal.get("spot", 0.0))

        return {
            "proposal_id": proposal_id,
            "ask_price": ask_price,
            "payout": payout,
            "spot": spot,
        }

    async def buy_contract(self, proposal_id: str, price: float) -> dict[str, Any]:
        """Executa a compra do contrato a partir da proposta aprovada.

        Retorna recibo contendo:
        - contract_id
        - buy_price
        - payout
        - balance_after
        - transaction_id
        """
        cleaned_prop_id = str(proposal_id).strip() if proposal_id else ""
        if not cleaned_prop_id:
            raise ValueError("O proposal_id não pode ser vazio.")
        if price <= 0:
            raise ValueError("O preço de compra deve ser maior que zero.")

        if not self.service.is_alive:
            await self.service.connect()

        buy_payload = {
            "buy": cleaned_prop_id,
            "price": float(price),
        }

        response = await self.service.send(buy_payload)

        if "error" in response:
            error_data = response["error"]
            error_code = error_data.get("code")
            error_msg = error_data.get("message", "Erro desconhecido")

            if error_code == "AuthorizationRequired":
                raise PermissionError(
                    "Autenticação necessária na Deriv API para comprar contratos (token inválido ou ausente)."
                )
            if error_code == "InsufficientBalance":
                raise RuntimeError(
                    f"Saldo insuficiente na conta para comprar o contrato: {error_msg}"
                )
            if error_code in ("MarketClosed", "TradingSuspended"):
                raise RuntimeError(
                    f"Mercado fechado ou suspenso no momento da compra: {error_msg}"
                )
            raise RuntimeError(f"Erro ao comprar contrato Deriv: {error_msg}")

        buy_data = response.get("buy")
        if not buy_data or not isinstance(buy_data, dict):
            raise RuntimeError(f"Resposta inválida de compra recebida: {response}")

        contract_id = buy_data.get("contract_id")
        buy_price = float(buy_data.get("buy_price", price))
        payout = float(buy_data.get("payout", 0.0))
        balance_after = float(buy_data.get("balance_after", 0.0))
        transaction_id = buy_data.get("transaction_id")

        return {
            "contract_id": contract_id,
            "buy_price": buy_price,
            "payout": payout,
            "balance_after": balance_after,
            "transaction_id": transaction_id,
        }

    async def execute_trade(
        self,
        symbol: str | None = None,
        contract_type: str | None = None,
        duration: int | None = None,
        duration_unit: str | None = None,
        stake: float | None = None,
        currency: str | None = None,
        barrier: str | None = None,
    ) -> dict[str, Any]:
        """Método de conveniência: verifica limites de risco, obtém proposta e executa a compra."""
        # Aplica valores padrão da instância caso não informados
        trade_symbol = symbol or self.symbol
        trade_contract_type = contract_type or self.contract_type
        trade_duration = duration if duration is not None else self.duration
        trade_duration_unit = duration_unit or self.duration_unit
        trade_stake = stake if stake is not None else self.stake
        trade_currency = currency or self.currency

        # 1. Verifica limites de risco
        self.check_risk_limits()

        # 2. Solicita a proposta
        proposal = await self.get_proposal(
            symbol=trade_symbol,
            contract_type=trade_contract_type,
            duration=trade_duration,
            duration_unit=trade_duration_unit,
            stake=trade_stake,
            currency=trade_currency,
            barrier=barrier,
        )

        # 3. Executa a compra do contrato
        receipt = await self.buy_contract(
            proposal_id=proposal["proposal_id"],
            price=proposal["ask_price"],
        )

        return {
            "status": "success",
            "contract_id": receipt["contract_id"],
            "buy_price": receipt["buy_price"],
            "payout": receipt["payout"],
            "balance_after": receipt["balance_after"],
            "transaction_id": receipt["transaction_id"],
            "spot": proposal.get("spot"),
            "proposal_id": proposal["proposal_id"],
        }

    async def run(self) -> dict[str, Any]:
        """Executa uma operação utilizando os parâmetros configurados na instância."""
        try:
            self.running = True
            return await self.execute_trade()
        finally:
            self.running = False

    async def stop(self) -> None:
        """Sinaliza parada de execução para a instância."""
        self.running = False


# Aliases para manter compatibilidade
DerivBot = DerivedBot
TraderBot = DerivedBot