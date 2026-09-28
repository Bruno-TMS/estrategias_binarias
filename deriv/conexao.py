"""Cliente WebSocket assíncrono para comunicação com a Deriv API."""

import asyncio
import json
import logging
import os
from typing import Any, Callable

import websockets
from websockets.protocol import State

logger = logging.getLogger(__name__)


def _sanitize_payload(payload: dict) -> dict:
    """Oculta tokens sensíveis de logs para auditoria de segurança."""
    if "authorize" in payload:
        safe = payload.copy()
        safe["authorize"] = "***"
        return safe
    return payload


def _is_valid_token(token: str | None) -> bool:
    """Valida se o token não é nulo, vazio ou um placeholder de exemplo."""
    if not token:
        return False
    token_clean = token.strip()
    invalid_tokens = {"", "seu_token_aqui", "your_token_here", "none", "null"}
    return token_clean.lower() not in invalid_tokens


async def _connect_ws(url: str, timeout: float = 15.0) -> Any:
    """Conexão WebSocket direta e limpa usando apenas websockets nativo com timeout resiliente."""
    return await websockets.connect(
        url,
        open_timeout=timeout,
        ping_interval=20,
        ping_timeout=20,
    )


class DerivWebSocketClient:
    """Singleton assíncrono para transporte via WebSocket com a Deriv API."""

    _instance: "DerivWebSocketClient | None" = None

    def __new__(cls, *args, **kwargs) -> "DerivWebSocketClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        app_id: str | None = None,
        token: str | None = None,
        ws_url: str | None = None,
    ) -> None:
        if getattr(self, "_initialized", False):
            return

        # Busca configurações dos parâmetros ou do ambiente/core.config
        try:
            from core.config import settings

            default_app_id = settings.deriv_app_id
            default_token = settings.deriv_api_token
            default_ws_url = settings.deriv_ws_url
        except ImportError:
            default_app_id = os.getenv("DERIV_APP_ID", "1089")
            default_token = os.getenv("DERIV_API_TOKEN", os.getenv("DERIV_TOKEN", ""))
            default_ws_url = os.getenv(
                "DERIV_WS_URL",
                "wss://api.derivws.com/trading/v1/options/ws/public",
            )

        self.app_id: str = str(app_id if app_id is not None else default_app_id)
        self.token: str = token if token is not None else default_token
        self.ws_url: str = ws_url or default_ws_url

        self._ws: Any = None
        self._listen_task: asyncio.Task | None = None
        self._req_id: int = 0
        self._send_lock: asyncio.Lock = asyncio.Lock()
        self._pending_requests: dict[int, asyncio.Future[dict]] = {}
        self._subscribers: set[Callable[[dict], Any]] = set()
        self._auth_response: dict | None = None
        self._active_url: str | None = None

        self._initialized = True

    @property
    def is_alive(self) -> bool:
        """Indica se a conexão WebSocket está ativa e aberta."""
        if self._ws is None:
            return False
        if hasattr(self._ws, "state"):
            return self._ws.state == State.OPEN
        if hasattr(self._ws, "closed"):
            return not self._ws.closed
        return True

    @property
    def is_public_mode(self) -> bool:
        """Indica se o endpoint ativo opera em modo de dados públicos."""
        active = self._active_url or self.ws_url
        return "/public" in active

    def _get_candidate_endpoints(self) -> list[str]:
        """Retorna lista de URLs candidatas, priorizando a URL configurada sem parâmetros que causem HTTP 520."""
        endpoints: list[str] = []

        if self.ws_url:
            endpoints.append(self.ws_url.strip())

        # Fallbacks canônicos da Deriv
        canonical_v3 = (
            f"wss://ws.derivws.com/websockets/v3?app_id={self.app_id}&l=EN&brand=deriv"
        )
        fallback_v3 = f"wss://ws.binaryws.com/websockets/v3?app_id={self.app_id}"

        for u in [canonical_v3, fallback_v3]:
            if u not in endpoints:
                endpoints.append(u)

        return endpoints

    async def connect(self) -> dict | None:
        """Estabelece a conexão WebSocket priorizando endpoint público sem exigir autorização prévia."""
        if self.is_alive:
            return self._auth_response

        candidate_urls = self._get_candidate_endpoints()
        last_exc: Exception | None = None

        for url in candidate_urls:
            try:
                logger.info(f"Tentando conectar ao WebSocket da Deriv em: {url}")
                self._ws = await _connect_ws(url, timeout=15.0)
                self._active_url = url
                logger.info(f"Conexão WebSocket estabelecida com sucesso com: {url}")
                break
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    f"Falha ao conectar no endpoint {url}: {exc}. Tentando próximo endpoint..."
                )

        if self._ws is None:
            raise ConnectionError(
                f"Não foi possível conectar a nenhum endpoint da Deriv. Último erro: {last_exc}"
            )

        self._listen_task = asyncio.create_task(self._listen_loop())

        # Em modo de dados públicos, não exige nem dispara autorização automática
        if self.is_public_mode:
            logger.info(
                f"Conectado ao endpoint de dados públicos ({self._active_url}) sem autorização."
            )
            return None

        # Em outros endpoints privados, autoriza somente se houver token válido configurado
        if _is_valid_token(self.token):
            auth_response = await self.send_request({"authorize": self.token})
            if "error" in auth_response:
                error_msg = auth_response["error"].get("message", "Falha de autenticação")
                # Garante que o token nunca seja exposto na mensagem de erro
                await self.disconnect()
                raise PermissionError(f"Falha de autenticação na Deriv API: {error_msg}")
            self._auth_response = auth_response
            return auth_response
        else:
            logger.info(
                "Nenhum token válido configurado; conexão mantida sem autenticação."
            )
            return None

    async def disconnect(self) -> None:
        """Encerra a conexão WebSocket e finaliza o loop de escuta em background."""
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        self._auth_response = None
        self._active_url = None

        # Notifica e rejeita requisições pendentes se houverem
        for fut in list(self._pending_requests.values()):
            if not fut.done():
                fut.set_exception(ConnectionError("Conexão WebSocket finalizada."))
        self._pending_requests.clear()

    async def send_request(self, payload: dict, timeout: float = 10.0) -> dict:
        """Envia requisição com req_id incremental e aguarda resposta de forma thread-safe."""
        if not self.is_alive:
            raise RuntimeError("WebSocket não está conectado.")

        request_data = payload.copy()

        async with self._send_lock:
            self._req_id += 1
            req_id = request_data.setdefault("req_id", self._req_id)
            future: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
            self._pending_requests[req_id] = future

            try:
                raw_message = json.dumps(request_data)
                await self._ws.send(raw_message)
            except Exception as exc:
                self._pending_requests.pop(req_id, None)
                safe_payload = _sanitize_payload(request_data)
                logger.error(f"Erro ao enviar requisição {safe_payload}: {exc}")
                raise RuntimeError(f"Falha ao enviar mensagem via WebSocket: {exc}")

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(req_id, None)
            raise TimeoutError(f"Tempo limite ({timeout}s) esgotado aguardando req_id={req_id}")

    def subscribe(self, callback: Callable[[dict], Any]) -> None:
        """Registra um callback para receber mensagens de streams do WebSocket."""
        self._subscribers.add(callback)

    def unsubscribe(self, callback: Callable[[dict], Any]) -> None:
        """Remove o registro de um callback de stream."""
        self._subscribers.discard(callback)

    async def _listen_loop(self) -> None:
        """Loop em background para receber mensagens e despachar respostas e streams."""
        try:
            async for message in self._ws:
                try:
                    data = json.loads(message)
                except Exception:
                    continue

                req_id = data.get("req_id")
                if req_id is not None and req_id in self._pending_requests:
                    fut = self._pending_requests.pop(req_id)
                    if not fut.done():
                        fut.set_result(data)

                # Notifica assinantes de streams
                for subscriber in list(self._subscribers):
                    try:
                        res = subscriber(data)
                        if asyncio.iscoroutine(res):
                            asyncio.create_task(res)
                    except Exception as err:
                        logger.warning(f"Erro ao processar callback de stream: {err}")

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning(f"Exceção no loop de escuta WebSocket: {exc}")
        finally:
            for fut in list(self._pending_requests.values()):
                if not fut.done():
                    fut.set_exception(
                        ConnectionError("Conexão WebSocket perdida durante escuta.")
                    )
            self._pending_requests.clear()


# Alias para manter compatibilidade com códigos legados
Conexao = DerivWebSocketClient
