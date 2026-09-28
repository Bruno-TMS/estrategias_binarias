"""Camada de serviço para operações da Deriv API."""

import logging
from datetime import datetime, timezone

from core.config import settings
from deriv.conexao import DerivWebSocketClient

logger = logging.getLogger(__name__)


class DerivService:
    """Serviço de alto nível que consome o Singleton DerivWebSocketClient."""

    def __init__(self, client: DerivWebSocketClient | None = None) -> None:
        self.app_id: str = settings.deriv_app_id
        self.token: str = settings.deriv_api_token
        self.client: DerivWebSocketClient = client or DerivWebSocketClient(
            app_id=self.app_id,
            token=self.token,
            ws_url=settings.deriv_ws_url,
        )
        self.connected_at: datetime | None = None

    @property
    def is_alive(self) -> bool:
        """Verifica se a conexão WebSocket está ativa."""
        return self.client.is_alive

    async def connect(self) -> dict | None:
        """Estabelece a conexão e autorização com a Deriv API."""
        if self.is_alive:
            return self.client._auth_response

        try:
            response = await self.client.connect()
            self.connected_at = datetime.now(timezone.utc)
            return response
        except Exception as exc:
            self._reset()
            logger.error(f"Erro ao conectar o serviço Deriv: {exc}")
            raise RuntimeError(f"Erro ao conectar com a Deriv API: {exc}")

    async def disconnect(self) -> None:
        """Encerra a conexão com a Deriv API."""
        try:
            await self.client.disconnect()
        finally:
            self._reset()

    async def send(self, payload: dict) -> dict:
        """Envia requisição genérica para a Deriv API via WebSocket."""
        if not self.is_alive:
            raise RuntimeError(
                "Serviço Deriv desconectado. Estabeleça a conexão antes de enviar requisições."
            )

        try:
            return await self.client.send_request(payload)
        except Exception as exc:
            logger.error(f"Erro na requisição para Deriv API: {exc}")
            raise RuntimeError(f"Erro ao comunicar com a Deriv API: {exc}")

    async def get_balance(self) -> dict:
        """Consulta o saldo da conta na Deriv API, retornando loginid, balance e currency."""
        if not self.is_alive:
            try:
                await self.connect()
            except Exception as exc:
                raise RuntimeError(
                    f"Serviço Deriv desconectado. Não foi possível restabelecer conexão: {exc}"
                )

        response = await self.send({"balance": 1})

        if "error" in response:
            error_msg = response["error"].get("message", "Erro desconhecido retornado pela API")
            raise RuntimeError(f"Erro ao consultar saldo na Deriv API: {error_msg}")

        balance_data = response.get("balance", {})
        if isinstance(balance_data, dict):
            loginid = balance_data.get("loginid") or balance_data.get("id") or ""
            balance = balance_data.get("balance", 0.0)
            currency = balance_data.get("currency", "USD")
        else:
            loginid = response.get("loginid", "")
            balance = balance_data
            currency = response.get("currency", "USD")

        return {
            "loginid": loginid,
            "balance": balance,
            "currency": currency,
        }

    def _reset(self) -> None:
        """Limpa estados internos ao desconectar."""
        self.connected_at = None
