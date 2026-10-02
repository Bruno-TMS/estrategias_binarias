#!/usr/bin/env python3
"""Script de teste de conexão e autenticação com a Deriv API.

Lê as credenciais (DERIV_API_TOKEN e DERIV_APP_ID) do arquivo .env,
estabelece conexão WebSocket assíncrona com a Deriv API, executa a
chamada {"authorize": token} e imprime de forma limpa e segura o status
do login, se a conta é Virtual/Demo ou Real e o saldo formatado.

Regras de Segurança:
- O token da API NUNCA é exibido em texto puro em logs, prints ou mensagens de erro.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any

import websockets

# Garante acesso aos módulos da raiz do projeto (core, deriv, services)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configuração de logging seguro
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_login")


def mask_token(token: str | None) -> str:
    """Mascara o token para exibição segura sem vazamento de credenciais."""
    if not token:
        return "[NÃO CONFIGURADO]"
    token_clean = token.strip()
    if len(token_clean) <= 8:
        return "***"
    return f"{token_clean[:4]}...{token_clean[-4:]}"


def mask_email(email: str | None) -> str:
    """Mascara o e-mail retornado pela API para privacidade."""
    if not email or "@" not in email:
        return email or "--"
    user, domain = email.split("@", 1)
    if len(user) <= 2:
        masked_user = user[0] + "*"
    else:
        masked_user = user[:2] + "***" + user[-1]
    return f"{masked_user}@{domain}"


def get_candidate_endpoints(app_id: str, ws_url: str | None = None) -> list[str]:
    """Retorna lista de URLs candidatas para conexão WebSocket."""
    endpoints: list[str] = []

    if ws_url and ws_url.strip():
        url_clean = ws_url.strip()
        endpoints.append(url_clean)
        # Se for endpoint public, tenta também com app_id explícito na query
        if "?" not in url_clean:
            endpoints.append(f"{url_clean}?app_id={app_id}")

    # Endpoints canônicos da Deriv API
    public_default = f"wss://api.derivws.com/trading/v1/options/ws/public?app_id={app_id}"
    v3_canonical = f"wss://ws.derivws.com/websockets/v3?app_id={app_id}"
    v3_fallback = f"wss://ws.binaryws.com/websockets/v3?app_id={app_id}"

    for ep in [public_default, v3_canonical, v3_fallback]:
        if ep not in endpoints:
            endpoints.append(ep)

    return endpoints


async def authenticate_deriv(
    token: str,
    app_id: str = "1089",
    ws_url: str | None = None,
    timeout: float = 12.0,
    mock: bool = False,
) -> dict[str, Any]:
    """Executa a conexão assíncrona WebSocket e autorização na Deriv API.

    Retorna um dicionário com os dados da autorização ou detalhes do erro.
    """
    if mock:
        # Modo simulado para testes automatizados
        return {
            "success": True,
            "loginid": "VRTC9876543",
            "fullname": "Trader Demonstrativo",
            "is_virtual": True,
            "account_type": "Demo (Virtual)",
            "balance": 10000.0,
            "currency": "USD",
            "balance_formatted": "USD 10,000.00",
            "email": mask_email("investidor@exemplo.com"),
            "scopes": ["read", "trade", "payments"],
            "endpoint": "wss://mock.derivws.com/v3",
            "app_id": app_id,
            "masked_token": mask_token(token),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    if not token or not token.strip():
        raise ValueError("DERIV_API_TOKEN não foi configurado ou é vazio.")

    # Fluxo Especial para Personal Access Token (PAT da Deriv Options API)
    if token.strip().startswith("pat_"):
        logger.info("Detectado Personal Access Token (PAT). Consultando contas e gerando sessão WebSocket Deriv...")
        try:
            import httpx

            headers = {
                "Authorization": f"Bearer {token.strip()}",
                "Deriv-App-ID": str(app_id).strip(),
            }
            async with httpx.AsyncClient(timeout=timeout) as http_client:
                resp_acc = await http_client.get(
                    "https://api.derivws.com/trading/v1/options/accounts",
                    headers=headers,
                )
                if resp_acc.status_code == 200:
                    accounts_data = resp_acc.json().get("data", [])
                    if accounts_data:
                        # Prioriza a conta demo para segurança operacional
                        target_acc = next(
                            (a for a in accounts_data if a.get("account_type") == "demo"),
                            accounts_data[0],
                        )
                        acc_id = target_acc.get("account_id")

                        # Solicita token OTP temporário para o WebSocket autenticado
                        resp_otp = await http_client.post(
                            f"https://api.derivws.com/trading/v1/options/accounts/{acc_id}/otp",
                            headers=headers,
                        )
                        if resp_otp.status_code == 200:
                            ws_otp_url = resp_otp.json().get("data", {}).get("url")
                            if ws_otp_url:
                                safe_ws_url = ws_otp_url.split("?")[0] + "?otp=***"
                                logger.info(f"Conectando ao WebSocket autenticado: {safe_ws_url}")
                                async with websockets.connect(
                                    ws_otp_url,
                                    open_timeout=timeout,
                                    ping_interval=20,
                                    ping_timeout=20,
                                ) as ws:
                                    logger.info("Conexão WebSocket autorizada com sucesso. Validando autorização...")
                                    auth_payload = {"authorize": token.strip(), "req_id": 1}
                                    await ws.send(json.dumps(auth_payload))
                                    raw_resp = await asyncio.wait_for(ws.recv(), timeout=timeout)
                                    ws_resp = json.loads(raw_resp)

                                    auth_info = ws_resp.get("authorize", {})
                                    loginid = auth_info.get("loginid") or acc_id
                                    is_virtual = (
                                        target_acc.get("account_type") == "demo"
                                        or bool(auth_info.get("is_virtual", 0))
                                    )
                                    balance = float(
                                        auth_info.get("balance") or target_acc.get("balance", 0.0)
                                    )
                                    currency = str(
                                        auth_info.get("currency") or target_acc.get("currency", "USD")
                                    )

                                    linked = [
                                        f"{a.get('account_id')} ({a.get('account_type', '').capitalize()}: {a.get('currency')} {float(a.get('balance', 0)):,.2f})"
                                        for a in accounts_data
                                    ]

                                    return {
                                        "success": True,
                                        "loginid": loginid,
                                        "fullname": f"Titular da Conta {loginid}",
                                        "is_virtual": is_virtual,
                                        "account_type": "Conta Demo (Virtual)" if is_virtual else "Conta Real",
                                        "balance": balance,
                                        "currency": currency,
                                        "balance_formatted": f"{currency} {balance:,.2f}",
                                        "scopes": ["read", "trade", "options_trading"],
                                        "linked_accounts": linked,
                                        "endpoint": safe_ws_url,
                                        "app_id": app_id,
                                        "masked_token": mask_token(token),
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                    }
                elif resp_acc.status_code == 401:
                    err_text = resp_acc.text
                    return {
                        "success": False,
                        "error_code": "Unauthorized",
                        "error_message": f"Credencial rejeitada pela Deriv: {err_text}",
                        "endpoint": "https://api.derivws.com/trading/v1/options/accounts",
                        "app_id": app_id,
                        "masked_token": mask_token(token),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
        except Exception as exc:
            logger.warning(f"Tentativa de autenticação PAT via OTP falhou: {exc}. Tentando fluxo padrão...")

    candidate_endpoints = get_candidate_endpoints(app_id=app_id, ws_url=ws_url)
    last_error: Exception | None = None

    for endpoint in candidate_endpoints:
        logger.info(f"Conectando ao WebSocket da Deriv em: {endpoint}")
        try:
            async with websockets.connect(
                endpoint,
                open_timeout=timeout,
                ping_interval=20,
                ping_timeout=20,
            ) as ws:
                logger.info("Conexão WebSocket aberta. Enviando requisição de autorização...")

                # Envio da chamada de autorização canônica da Deriv API
                auth_payload = {"authorize": token.strip(), "req_id": 1}
                await ws.send(json.dumps(auth_payload))

                raw_resp = await asyncio.wait_for(ws.recv(), timeout=timeout)
                response = json.loads(raw_resp)

                if "error" in response:
                    err = response["error"]
                    err_code = err.get("code", "AuthError")
                    err_msg = err.get("message", "Falha desconhecida na autorização")
                    return {
                        "success": False,
                        "error_code": err_code,
                        "error_message": err_msg,
                        "endpoint": endpoint,
                        "app_id": app_id,
                        "masked_token": mask_token(token),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                auth_data = response.get("authorize", {})
                loginid = auth_data.get("loginid", "--")
                fullname = (
                    auth_data.get("fullname")
                    or f"{auth_data.get('first_name', '')} {auth_data.get('last_name', '')}".strip()
                    or str(auth_data.get("user_id", "--"))
                )
                is_virtual_raw = auth_data.get("is_virtual", 0)
                is_virtual = bool(is_virtual_raw)
                balance = float(auth_data.get("balance", 0.0))
                currency = str(auth_data.get("currency", "USD"))
                email = auth_data.get("email")
                scopes = auth_data.get("scopes", [])

                return {
                    "success": True,
                    "loginid": loginid,
                    "fullname": fullname,
                    "is_virtual": is_virtual,
                    "account_type": "Demo (Virtual)" if is_virtual else "Real",
                    "balance": balance,
                    "currency": currency,
                    "balance_formatted": f"{currency} {balance:,.2f}",
                    "email": mask_email(email),
                    "scopes": scopes,
                    "endpoint": endpoint,
                    "app_id": app_id,
                    "masked_token": mask_token(token),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        except (websockets.exceptions.WebSocketException, OSError, asyncio.TimeoutError) as exc:
            last_error = exc
            logger.warning(f"Falha de conexão com {endpoint}: {exc}. Tentando próximo...")
            continue

    return {
        "success": False,
        "error_code": "ConnectionFailed",
        "error_message": f"Não foi possível conectar a nenhum dos endpoints testados. Último erro: {last_error}",
        "endpoint": candidate_endpoints[0] if candidate_endpoints else "--",
        "app_id": app_id,
        "masked_token": mask_token(token),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def print_results(result: dict[str, Any]) -> None:
    """Imprime no console o relatório formatado da execução."""
    sep = "=" * 62
    subsep = "-" * 62

    print("\n" + sep)
    if result.get("success"):
        print("          RELATÓRIO DE AUTENTICAÇÃO - DERIV API (SUCESSO)")
        print(sep)
        print(f" Status da Conexão : CONECTADO E AUTORIZADO")
        print(f" Endpoint Deriv    : {result.get('endpoint')}")
        print(f" Deriv App ID      : {result.get('app_id')}")
        print(f" Token Utilizado   : {result.get('masked_token')} (Protegido)")
        print(subsep)
        print(f" ID da Conta       : {result.get('loginid')}")
        if result.get("fullname") and result.get("fullname") != "--":
            print(f" Titular da Conta  : {result.get('fullname')}")
        print(f" Tipo de Conta     : {result.get('account_type')} [is_virtual={result.get('is_virtual')}]")
        print(f" Saldo da Conta    : {result.get('balance_formatted')}")
        print(f" Moeda Operacional : {result.get('currency')}")
        if result.get("email"):
            print(f" E-mail Associado  : {result.get('email')}")
        if result.get("scopes"):
            print(f" Permissões Scopes : {', '.join(result.get('scopes', []))}")
        if result.get("linked_accounts"):
            print(f" Contas Vinculadas : {', '.join(result.get('linked_accounts'))}")
        print(sep)
        print(" [OK] Autenticação válida. O robô está pronto para operar.\n")
    else:
        print("          RELATÓRIO DE AUTENTICAÇÃO - DERIV API (FALHA)")
        print(sep)
        print(f" Status da Conexão : FALHA NA AUTENTICAÇÃO")
        print(f" Endpoint Deriv    : {result.get('endpoint')}")
        print(f" Deriv App ID      : {result.get('app_id')}")
        print(f" Token Utilizado   : {result.get('masked_token')} (Protegido)")
        print(subsep)
        print(f" Código do Erro    : {result.get('error_code')}")
        print(f" Detalhe do Erro   : {result.get('error_message')}")
        print(sep)
        print(" [DICA DE CORREÇÃO]")
        print(" 1. Acesse https://app.deriv.com/")
        print(" 2. Navegue até: Configurações da Conta -> Tokens de API (API Tokens)")
        print(" 3. Crie um token com os escopos: 'Read' e 'Trade'")
        print(" 4. Insira o novo token no seu arquivo .env em:")
        print("    DERIV_API_TOKEN=seu_novo_token_aqui")
        print(sep + "\n")


def parse_arguments() -> argparse.Namespace:
    """Interpreta os argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Script de verificação de autenticação e saldo na Deriv API.",
    )
    parser.add_argument(
        "--token",
        "-t",
        default=None,
        help="Token de autenticação da Deriv (se omitido, lê do .env).",
    )
    parser.add_argument(
        "--app-id",
        "-a",
        default=None,
        help="ID do aplicativo Deriv (padrão: 1089 ou do .env).",
    )
    parser.add_argument(
        "--url",
        "-u",
        default=None,
        help="URL customizada do WebSocket da Deriv API.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Executa em modo simulado/mock para testes.",
    )
    return parser.parse_args()


async def main_async() -> int:
    """Função assíncrona principal."""
    args = parse_arguments()

    # Carrega configurações do core.config ou os.environ/.env
    try:
        from core.config import settings

        env_token = settings.deriv_api_token
        env_app_id = settings.deriv_app_id
        env_ws_url = settings.deriv_ws_url
    except ImportError:
        env_token = os.getenv("DERIV_API_TOKEN", os.getenv("DERIV_TOKEN", ""))
        env_app_id = os.getenv("DERIV_APP_ID", "1089")
        env_ws_url = os.getenv(
            "DERIV_WS_URL",
            "wss://api.derivws.com/trading/v1/options/ws/public",
        )

    token = args.token or env_token
    app_id = str(args.app_id or env_app_id or "1089")
    ws_url = args.url or env_ws_url

    if not token and not args.mock:
        print("\n" + "=" * 62)
        print(" [ERRO] DERIV_API_TOKEN não foi encontrado!")
        print(" Configure a variável DERIV_API_TOKEN no arquivo .env ou passe via --token <token>.")
        print("=" * 62 + "\n")
        return 1

    result = await authenticate_deriv(
        token=token,
        app_id=app_id,
        ws_url=ws_url,
        mock=args.mock,
    )

    print_results(result)
    return 0 if result.get("success") else 1


def main() -> None:
    """Ponto de entrada síncrono para execução via terminal."""
    try:
        exit_code = asyncio.run(main_async())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nOperação interrompida pelo usuário.")
        sys.exit(130)


if __name__ == "__main__":
    main()
