"""Camada de serviço para operações da Deriv API."""

import asyncio
import inspect
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from core.config import settings
from deriv.conexao import DerivWebSocketClient
from deriv.symbol import (
    ActiveSymbol,
    get_active_synthetic_symbols,
    sync_symbols_cache,
)

logger = logging.getLogger(__name__)


def _dispatch_callback(callback: Callable, tick_dict: dict) -> Any:
    """Despacha o tick para o callback adaptando à assinatura fornecida."""
    try:
        sig = inspect.signature(callback)
        params = list(sig.parameters.values())
        if len(params) == 1:
            param_name = params[0].name.lower()
            if param_name in ("quote", "price", "preco", "valor"):
                return callback(tick_dict.get("quote"))
            return callback(tick_dict)
        elif len(params) == 3:
            return callback(
                tick_dict.get("quote"),
                tick_dict.get("epoch"),
                tick_dict.get("symbol"),
            )
    except (ValueError, TypeError):
        pass
    return callback(tick_dict)


CONTRACT_TYPE_DISPLAY: dict[str, str] = {
    # Call / Put
    "CALL": "Higher / Rise",
    "PUT": "Lower / Fall",
    "CALLE": "Rise Equal",
    "PUTE": "Fall Equal",
    "HIGHER": "Higher",
    "LOWER": "Lower",
    # Touch / No Touch
    "ONETOUCH": "Touch",
    "NOTOUCH": "No Touch",
    # Digits
    "DIGITMATCH": "Matches",
    "DIGITDIFF": "Differs",
    "DIGITEVEN": "Even",
    "DIGITODD": "Odd",
    "DIGITOVER": "Over",
    "DIGITUNDER": "Under",
    # Asian
    "ASIANU": "Asian Up",
    "ASIAND": "Asian Down",
    # In / Out
    "EXPIRYMISS": "Ends Outside",
    "EXPIRYMISSE": "Ends Outside",
    "EXPIRYRANGE": "Ends Between",
    "EXPIRYRANGEE": "Ends Between",
    "RANGE": "Stays Between",
    "UPORDOWN": "Goes Outside",
    # Reset
    "RESETCALL": "Reset Call",
    "RESETPUT": "Reset Put",
    # High / Low Ticks
    "TICKHIGH": "High Tick",
    "TICKLOW": "Low Tick",
    # Runs
    "RUNHIGH": "Only Ups",
    "RUNLOW": "Only Downs",
    # Accumulators & Multipliers
    "ACCU": "Accumulator",
    "MULTUP": "Multiplier Up",
    "MULTDOWN": "Multiplier Down",
    # Turbos
    "TURBOSLONG": "Turbos Long",
    "TURBOSSHORT": "Turbos Short",
    # Vanillas
    "VANILLALONGCALL": "Vanilla Call",
    "VANILLALONGPUT": "Vanilla Put",
}


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
        self._latest_ticks: dict[str, dict] = {}
        self._active_subscriptions: dict[str, dict[str, Any]] = {}

        # Registra listener global para manter o cache do último tick atualizado
        self.client.subscribe(self._on_stream_message)

    @property
    def is_alive(self) -> bool:
        """Verifica se a conexão WebSocket está ativa."""
        return self.client.is_alive

    def _on_stream_message(self, data: dict) -> None:
        """Atualiza o cache do tick mais recente a partir de qualquer mensagem de tick recebida."""
        if data.get("msg_type") == "tick" and "tick" in data:
            tick = data["tick"]
            sym = tick.get("symbol")
            if sym:
                self._latest_ticks[sym] = tick

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
        """Encerra a conexão com a Deriv API e limpa subscrições ativas."""
        try:
            await self.unsubscribe_all_ticks()
            await self.client.disconnect()
        finally:
            self._reset()
            try:
                from services.time_operations import time_operations

                time_operations.reset_login()
            except Exception:
                pass

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

    async def get_server_time(self) -> int:
        """Consulta o relógio oficial do servidor Deriv via WebSocket ('{"time": 1}').

        Retorna o timestamp Epoch (int) retornado pela Deriv API.
        """
        if not self.is_alive:
            try:
                await self.connect()
            except Exception as exc:
                raise RuntimeError(
                    f"Serviço Deriv desconectado. Não foi possível conectar para obter o tempo: {exc}"
                )

        response = await self.send({"time": 1})
        if "error" in response:
            err_msg = response["error"].get("message", "Erro desconhecido ao consultar tempo")
            raise RuntimeError(f"Erro ao consultar tempo na Deriv API: {err_msg}")

        epoch = response.get("time")
        if epoch is None:
            raise RuntimeError(f"Resposta inválida de tempo recebida da Deriv API: {response}")

        return int(epoch)

    async def get_balance(self) -> dict:
        """Consulta o saldo da conta na Deriv API, garantindo autorização prévia para evitar erro 'Please log in'."""
        if not self.is_alive or not getattr(self.client, "_auth_response", None):
            if self.token:
                try:
                    auth_res = await self.authorize()
                    return {
                        "loginid": auth_res.get("loginid", ""),
                        "balance": auth_res.get("balance", 0.0),
                        "currency": auth_res.get("currency", "USD"),
                    }
                except Exception as exc:
                    logger.warning(f"Tentativa de autorização prévia em get_balance falhou: {exc}")
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
            if "log in" in error_msg.lower() or "authorization" in error_msg.lower():
                auth_res = await self.authorize()
                return {
                    "loginid": auth_res.get("loginid", ""),
                    "balance": auth_res.get("balance", 0.0),
                    "currency": auth_res.get("currency", "USD"),
                }
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

    async def authorize(self, token: str | None = None) -> dict[str, Any]:
        """Executa a autorização da conta na Deriv API usando o token informado ou das configurações."""
        auth_token = token or self.token
        if not auth_token or not auth_token.strip():
            raise PermissionError("Autenticação necessária: token não configurado ou vazio.")

        # Se for um token PAT (pat_...), assegura conexão no canal OTP autenticado
        if auth_token.strip().startswith("pat_"):
            try:
                import httpx

                headers = {
                    "Authorization": f"Bearer {auth_token.strip()}",
                    "Deriv-App-ID": str(self.app_id).strip(),
                }
                async with httpx.AsyncClient(timeout=8.0) as http_client:
                    resp_acc = await http_client.get(
                        "https://api.derivws.com/trading/v1/options/accounts",
                        headers=headers,
                    )
                    if resp_acc.status_code == 200:
                        accounts_data = resp_acc.json().get("data", [])
                        if accounts_data:
                            target_acc = next(
                                (a for a in accounts_data if a.get("account_type") == "demo"),
                                accounts_data[0],
                            )
                            acc_id = target_acc.get("account_id")
                            resp_otp = await http_client.post(
                                f"https://api.derivws.com/trading/v1/options/accounts/{acc_id}/otp",
                                headers=headers,
                            )
                            if resp_otp.status_code == 200:
                                ws_otp_url = resp_otp.json().get("data", {}).get("url")
                                if ws_otp_url:
                                    if self.client.is_alive:
                                        await self.client.disconnect()
                                    self.client.ws_url = ws_otp_url
                                    await self.client.connect()
            except Exception as exc:
                logger.warning(f"Tentativa de handshake PAT via OTP em DerivService falhou: {exc}")

        if not self.is_alive:
            await self.connect()

        response = await self.send({"authorize": auth_token.strip()})

        if "error" in response:
            err = response["error"]
            err_msg = err.get("message", "Falha de autenticação na Deriv API.")
            raise PermissionError(f"Falha de autenticação na Deriv API: {err_msg}")

        auth_data = response.get("authorize", {})
        loginid = auth_data.get("loginid", "")
        fullname = (
            auth_data.get("fullname")
            or f"{auth_data.get('first_name', '')} {auth_data.get('last_name', '')}".strip()
            or f"Titular da Conta {loginid}"
        )
        is_virtual = bool(auth_data.get("is_virtual", 0))
        balance = float(auth_data.get("balance", 0.0))
        currency = str(auth_data.get("currency", "USD"))
        email = auth_data.get("email")
        scopes = auth_data.get("scopes", [])

        # Salva resposta de autorização no client para manter a sessão autenticada
        self.client._auth_response = response

        # Registra timestamp UTC da sessão autenticada
        try:
            from services.time_operations import time_operations

            time_operations.register_login()
        except Exception as exc:
            logger.debug(f"Não foi possível registrar login em time_operations: {exc}")

        return {
            "loginid": loginid,
            "fullname": fullname,
            "is_virtual": is_virtual,
            "account_type": "Demo (Virtual)" if is_virtual else "Real",
            "balance": balance,
            "currency": currency,
            "email": email,
            "scopes": scopes,
        }

    async def get_symbols(self, synthetic_only: bool = True) -> list[dict[str, Any]]:
        """Retorna lista de ativos negociáveis utilizando o cache de deriv/symbol.py.

        Caso o cache em memória esteja vazio, executa a sincronização assíncrona.
        Por padrão, retorna os índices sintéticos abertos para negociação.
        """
        if not ActiveSymbol.get_all():
            if not self.is_alive:
                await self.connect()
            await sync_symbols_cache(self)

        if synthetic_only:
            return get_active_synthetic_symbols()

        return [
            {
                "symbol": inst.symbol,
                "display_name": inst.display_name,
                "market": inst.market,
                "market_display_name": inst.market_display_name,
                "sub_market": inst.sub_market,
                "submarket_display_name": inst.submarket_display_name,
            }
            for inst in ActiveSymbol.get_available_symbols()
        ]

    async def sync_symbols(self) -> int:
        """Força a sincronização do cache de símbolos da Deriv API."""
        if not self.is_alive:
            await self.connect()
        return await sync_symbols_cache(self)

    async def get_contracts_for(self, symbol: str) -> list[dict[str, Any]]:
        """Consulta os tipos de contratos e durações permitidas para o ativo informado.

        Dispara requisição {'contracts_for': symbol} na Deriv API e retorna lista
        estruturada contendo:
        - contract_category
        - contract_type
        - contract_display
        - min_contract_duration
        - max_contract_duration

        Valida previamente a existência do ativo no catálogo e trata
        cenários de mercado fechado para determinados contratos.
        """
        cleaned_symbol = symbol.strip() if symbol else ""
        if not cleaned_symbol:
            raise ValueError("O símbolo do ativo não pode ser vazio.")

        # Garante que o catálogo de símbolos esteja carregado
        if not ActiveSymbol.get_all():
            if not self.is_alive:
                await self.connect()
            await sync_symbols_cache(self)

        # Valida se o símbolo existe no catálogo de símbolos
        existing = ActiveSymbol.find(symbol=cleaned_symbol)
        if not existing:
            # Tenta sincronizar uma vez caso seja um ativo recém-adicionado
            await sync_symbols_cache(self)
            existing = ActiveSymbol.find(symbol=cleaned_symbol)
            if not existing:
                raise ValueError(
                    f"Ativo '{cleaned_symbol}' não encontrado ou inválido."
                )

        if not self.is_alive:
            try:
                await self.connect()
            except Exception as exc:
                raise RuntimeError(
                    f"Serviço Deriv desconectado. Não foi possível restabelecer conexão: {exc}"
                )

        response = await self.send({"contracts_for": cleaned_symbol})

        if "error" in response:
            error_data = response["error"]
            error_code = error_data.get("code")
            error_msg = error_data.get("message", "Erro desconhecido")

            # Trata retornos em que o mercado está fechado ou sem contratos ofertados no momento
            if error_code in ("MarketClosed", "TradingSuspended") or "closed" in error_msg.lower():
                logger.info(
                    f"Mercado fechado para contratos do ativo '{cleaned_symbol}': {error_msg}"
                )
                return []

            if error_code == "OfferingsInvalidSymbol":
                logger.info(
                    f"Nenhum contrato disponível no momento para '{cleaned_symbol}' (mercado fechado ou sem ofertas): {error_msg}"
                )
                return []

            if error_code == "InvalidSymbol":
                raise ValueError(
                    f"Ativo '{cleaned_symbol}' não encontrado ou inválido na Deriv API."
                )

            raise RuntimeError(
                f"Erro ao consultar contratos para '{cleaned_symbol}': {error_msg}"
            )

        cf_data = response.get("contracts_for", {})
        available_contracts = cf_data.get("available", [])

        if not available_contracts:
            logger.info(
                f"Nenhum contrato disponível para o ativo '{cleaned_symbol}' no momento."
            )
            return []

        formatted_contracts: list[dict[str, Any]] = []
        for c in available_contracts:
            contract_type = c.get("contract_type", "")
            contract_category = c.get("contract_category", "")
            contract_display = (
                c.get("contract_display")
                or c.get("contract_display_name")
                or CONTRACT_TYPE_DISPLAY.get(contract_type)
                or contract_type
            )
            min_duration = c.get("min_contract_duration")
            max_duration = c.get("max_contract_duration")

            formatted_contracts.append({
                "contract_category": contract_category,
                "contract_type": contract_type,
                "contract_display": contract_display,
                "min_contract_duration": min_duration,
                "max_contract_duration": max_duration,
            })

        return formatted_contracts

    async def get_latest_tick(self, symbol: str) -> dict[str, Any]:
        """Consulta a cotação mais recente disparando {'ticks': symbol}.

        Retorna dicionário contendo quote, epoch e symbol.
        Lança ValueError caso o ativo informado não exista.
        """
        cleaned_symbol = symbol.strip() if symbol else ""
        if not cleaned_symbol:
            raise ValueError("O símbolo do ativo não pode ser vazio.")

        if not self.is_alive:
            try:
                await self.connect()
            except Exception as exc:
                raise RuntimeError(
                    f"Serviço Deriv desconectado. Não foi possível restabelecer conexão: {exc}"
                )

        response = await self.send({"ticks": cleaned_symbol})

        if "error" in response:
            error_data = response["error"]
            error_code = error_data.get("code")
            error_msg = error_data.get("message", "Erro desconhecido")

            # Se já estiver inscrito na stream do ativo, usa a cotação mais recente recebida
            if error_code == "AlreadySubscribed" and cleaned_symbol in self._latest_ticks:
                cached_tick = self._latest_ticks[cleaned_symbol]
                return {
                    "symbol": cached_tick.get("symbol", cleaned_symbol),
                    "quote": float(cached_tick.get("quote", 0.0)),
                    "epoch": int(cached_tick.get("epoch", 0)),
                }

            if error_code == "InvalidSymbol":
                raise ValueError(
                    f"Ativo '{cleaned_symbol}' não encontrado ou inválido na Deriv API."
                )
            raise RuntimeError(
                f"Erro ao consultar cotação para '{cleaned_symbol}': {error_msg}"
            )

        tick = response.get("tick")
        if not tick or not isinstance(tick, dict):
            raise RuntimeError(
                f"Resposta de tick não continha dados para '{cleaned_symbol}': {response}"
            )

        self._latest_ticks[cleaned_symbol] = tick

        # Se não houver assinaturas ativas para este símbolo, encerra o stream temporário
        sub_id = response.get("subscription", {}).get("id")
        if sub_id and cleaned_symbol not in self._active_subscriptions:
            try:
                await self.send({"forget": sub_id})
            except Exception as exc:
                logger.debug(f"Erro ao esquecer subscrição temporária {sub_id}: {exc}")

        return {
            "symbol": tick.get("symbol", cleaned_symbol),
            "quote": float(tick.get("quote", 0.0)),
            "epoch": int(tick.get("epoch", 0)),
        }

    async def get_ticks_history(
        self,
        symbol: str,
        count: int = 1000,
        end: str = "latest",
    ) -> dict[str, Any]:
        """Obtém o histórico de ticks para um ativo específico.

        Dispara o payload {'ticks_history': symbol, 'count': count, 'end': end, 'style': 'ticks'}
        na Deriv API. Extrai e retorna uma lista ordenada de preços (quotes) e timestamps (epochs).

        Retorna dicionário contendo:
        - symbol: símbolo do ativo
        - prices: lista de preços em formato float
        - times: lista de timestamps em formato int (epoch)

        Valida se o símbolo existe no catálogo em cache antes de disparar a requisição
        e trata cenários de ativo suspenso ou histórico indisponível.
        """
        cleaned_symbol = symbol.strip() if symbol else ""
        if not cleaned_symbol:
            raise ValueError("O símbolo do ativo não pode ser vazio.")

        if count <= 0:
            raise ValueError("A quantidade de ticks (count) deve ser maior que zero.")

        # 1. Valida se o símbolo existe no catálogo em cache
        if not ActiveSymbol.get_all():
            if not self.is_alive:
                await self.connect()
            await sync_symbols_cache(self)

        existing = ActiveSymbol.find(symbol=cleaned_symbol)
        if not existing:
            # Tenta sincronizar novamente caso seja um ativo recém-adicionado
            await sync_symbols_cache(self)
            existing = ActiveSymbol.find(symbol=cleaned_symbol)
            if not existing:
                raise ValueError(
                    f"Ativo '{cleaned_symbol}' não encontrado ou inválido no catálogo de símbolos."
                )

        inst = existing[0]
        if inst.is_trading_suspended:
            logger.warning(
                f"O ativo '{cleaned_symbol}' está marcado como suspenso para negociação."
            )

        if not self.is_alive:
            try:
                await self.connect()
            except Exception as exc:
                raise RuntimeError(
                    f"Serviço Deriv desconectado. Não foi possível restabelecer conexão: {exc}"
                )

        payload = {
            "ticks_history": cleaned_symbol,
            "count": int(count),
            "end": str(end),
            "style": "ticks",
        }

        response = await self.send(payload)

        if "error" in response:
            error_data = response["error"]
            error_code = error_data.get("code")
            error_msg = error_data.get("message", "Erro desconhecido")

            if error_code in ("InvalidSymbol", "OfferingsInvalidSymbol"):
                raise ValueError(
                    f"Ativo '{cleaned_symbol}' não encontrado ou inválido na Deriv API: {error_msg}"
                )
            if error_code in ("MarketClosed", "TradingSuspended"):
                raise RuntimeError(
                    f"Histórico indisponível: mercado suspenso ou fechado para '{cleaned_symbol}': {error_msg}"
                )

            raise RuntimeError(
                f"Erro ao consultar histórico de ticks para '{cleaned_symbol}': {error_msg}"
            )

        history = response.get("history")
        if not history or not isinstance(history, dict):
            raise RuntimeError(
                f"Resposta inválida de histórico recebida para '{cleaned_symbol}': {response}"
            )

        raw_prices = history.get("prices", [])
        raw_times = history.get("times", [])

        # Garante a formatação e ordenação cronológica dos preços e epochs
        formatted_prices = [float(p) for p in raw_prices]
        formatted_times = [int(t) for t in raw_times]

        return {
            "symbol": cleaned_symbol,
            "prices": formatted_prices,
            "times": formatted_times,
        }

    async def subscribe_ticks(
        self, symbol: str, callback: Callable[[Any], Any]
    ) -> Callable[[], Any]:
        """Subscreve ao stream de ticks em tempo real para o ativo especificado.

        Registra o listener de ticks no Singleton DerivWebSocketClient e envia
        a requisição {'ticks': symbol, 'subscribe': 1}.
        Lança ValueError caso o ativo informado não exista.
        Retorna uma função assíncrona para cancelar a subscrição (unsubscribe).
        """
        cleaned_symbol = symbol.strip() if symbol else ""
        if not cleaned_symbol:
            raise ValueError("O símbolo do ativo não pode ser vazio.")

        if not self.is_alive:
            await self.connect()

        def _tick_listener(data: dict) -> None:
            # Trata mensagens canônicas da stream de ticks da Deriv API
            tick_info = data.get("tick")
            if isinstance(tick_info, dict) and tick_info.get("symbol") == cleaned_symbol:
                # Atualiza subscription_id se recebido na mensagem
                sub_id = data.get("subscription", {}).get("id") or tick_info.get("id")
                if sub_id and not sub_info.get("sub_id"):
                    sub_info["sub_id"] = sub_id

                # Extração de alta eficiência dos campos essenciais
                quote_val = float(tick_info.get("quote", 0.0))
                epoch_val = int(tick_info.get("epoch", 0))
                payload = {
                    "symbol": cleaned_symbol,
                    "quote": quote_val,
                    "epoch": epoch_val,
                    "ask": float(tick_info["ask"]) if "ask" in tick_info else None,
                    "bid": float(tick_info["bid"]) if "bid" in tick_info else None,
                    "pip_size": tick_info.get("pip_size"),
                    "subscription_id": sub_info.get("sub_id"),
                }
                payload["tick"] = payload
                payload["msg_type"] = "tick"

                # Atualiza cache em memória do serviço
                self._latest_ticks[cleaned_symbol] = tick_info

                try:
                    res = _dispatch_callback(callback, payload)
                    if asyncio.iscoroutine(res):
                        asyncio.create_task(res)
                except Exception as err:
                    logger.warning(
                        f"Erro no callback de tick para '{cleaned_symbol}': {err}"
                    )

        self.client.subscribe(_tick_listener)

        sub_info = self._active_subscriptions.setdefault(
            cleaned_symbol, {"subscribers": set(), "sub_id": None}
        )
        sub_info["subscribers"].add(_tick_listener)

        # Se ainda não possui sub_id ativo, requisita a subscrição à Deriv
        if sub_info["sub_id"] is None:
            try:
                response = await self.send({"ticks": cleaned_symbol, "subscribe": 1})
                if "error" in response:
                    error_data = response["error"]
                    error_code = error_data.get("code")
                    error_msg = error_data.get("message", "Erro desconhecido")

                    if error_code == "AlreadySubscribed":
                        logger.debug(
                            f"Ativo '{cleaned_symbol}' já estava subscrito; mantendo listener registrado."
                        )
                    else:
                        self.client.unsubscribe(_tick_listener)
                        sub_info["subscribers"].discard(_tick_listener)
                        if not sub_info["subscribers"]:
                            self._active_subscriptions.pop(cleaned_symbol, None)

                        if error_code == "InvalidSymbol":
                            raise ValueError(
                                f"Ativo '{cleaned_symbol}' não encontrado ou inválido na Deriv API."
                            )
                        raise RuntimeError(
                            f"Erro ao subscrever ticks para '{cleaned_symbol}': {error_msg}"
                        )
                else:
                    sub_id = response.get("subscription", {}).get("id") or response.get("tick", {}).get("id")
                    if sub_id:
                        sub_info["sub_id"] = sub_id
                    if "tick" in response and isinstance(response["tick"], dict):
                        initial_tick = response["tick"]
                        self._latest_ticks[cleaned_symbol] = initial_tick
                        init_payload = {
                            "symbol": cleaned_symbol,
                            "quote": float(initial_tick.get("quote", 0.0)),
                            "epoch": int(initial_tick.get("epoch", 0)),
                            "ask": float(initial_tick["ask"]) if "ask" in initial_tick else None,
                            "bid": float(initial_tick["bid"]) if "bid" in initial_tick else None,
                            "pip_size": initial_tick.get("pip_size"),
                            "subscription_id": sub_id,
                        }
                        init_payload["tick"] = init_payload
                        init_payload["msg_type"] = "tick"
                        try:
                            res = _dispatch_callback(callback, init_payload)
                            if asyncio.iscoroutine(res):
                                asyncio.create_task(res)
                        except Exception as err:
                            logger.debug(f"Erro no despacho inicial de tick para '{cleaned_symbol}': {err}")
            except Exception:
                self.client.unsubscribe(_tick_listener)
                sub_info["subscribers"].discard(_tick_listener)
                if not sub_info["subscribers"]:
                    self._active_subscriptions.pop(cleaned_symbol, None)
                raise

        async def unsubscribe() -> None:
            """Função de cancelamento seguro da subscrição via forget."""
            self.client.unsubscribe(_tick_listener)
            current_sub = self._active_subscriptions.get(cleaned_symbol)
            if current_sub:
                current_sub["subscribers"].discard(_tick_listener)
                if not current_sub["subscribers"]:
                    sub_id_to_forget = current_sub.get("sub_id")
                    self._active_subscriptions.pop(cleaned_symbol, None)
                    if self.is_alive:
                        try:
                            if sub_id_to_forget:
                                await self.send({"forget": sub_id_to_forget})
                            else:
                                await self.send({"forget_all": "ticks"})
                            logger.info(
                                f"Subscrição cancelada com sucesso para '{cleaned_symbol}' (forget: {sub_id_to_forget})."
                            )
                        except Exception as exc:
                            logger.debug(
                                f"Erro ao cancelar subscrição {sub_id_to_forget}: {exc}"
                            )

        return unsubscribe

    async def unsubscribe_ticks(self, symbol: str) -> bool:
        """Cancela a subscrição de ticks para o símbolo especificado via {'forget': sub_id}."""
        cleaned_symbol = symbol.strip() if symbol else ""
        if not cleaned_symbol:
            return False
        sub_info = self._active_subscriptions.pop(cleaned_symbol, None)
        if not sub_info:
            return False
        for listener in list(sub_info.get("subscribers", [])):
            self.client.unsubscribe(listener)
        sub_id = sub_info.get("sub_id")
        if self.is_alive:
            try:
                if sub_id:
                    await self.send({"forget": sub_id})
                else:
                    await self.send({"forget_all": "ticks"})
                logger.info(f"Subscrição de ticks cancelada para '{cleaned_symbol}' (ID: {sub_id}).")
                return True
            except Exception as exc:
                logger.debug(f"Erro ao cancelar subscrição de '{cleaned_symbol}': {exc}")
        return False

    async def unsubscribe_all_ticks(self) -> int:
        """Cancela com segurança todas as subscrições ativas de ticks."""
        count = 0
        symbols = list(self._active_subscriptions.keys())
        for sym in symbols:
            if await self.unsubscribe_ticks(sym):
                count += 1
        return count

    def get_active_subscriptions(self) -> list[str]:
        """Retorna a lista de símbolos com subscrições ativas."""
        return list(self._active_subscriptions.keys())

    def _reset(self) -> None:
        """Limpa estados internos ao desconectar."""
        self.connected_at = None
        self._active_subscriptions.clear()
