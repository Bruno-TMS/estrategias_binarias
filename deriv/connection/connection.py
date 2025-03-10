"""Módulo connection.py

Gerencia a conexão com a API Deriv usando DerivAPI, integrando o Singleton AppDashboard
para obter credenciais dinamicamente do CSV. Inclui teste de rede, reconexão com backoff,
manutenção de sessão via ping e gerenciamento de detalhes da conta.
"""

import asyncio
import subprocess
from datetime import datetime
from deriv_api import DerivAPI
from app_dashboard import AppDashboard  # Importa do mesmo diretório (connection/)

# Variáveis globais para gerenciar a conexão
_api = None
_is_alive = False  # Indica se a conexão está ativa
_last_connection_time = None  # Armazena data/hora da última conexão
_connection_failure_count = 0  # Contador de falhas de conexão
_MAX_RECONNECT_ATTEMPTS = 5  # Limite de tentativas de reconexão
_RECONNECT_DELAY = 2  # Delay inicial de reconexão em segundos (aumenta com backoff)
_last_disconnect_reason = None  # Motivo da última desconexão
# Variáveis públicas para informações da conta
account_type = None
currency = None
balance = None
account_id = None
# Contador para req_id
_request_id = 0

def _get_next_request_id() -> int:
    """Gera o próximo ID de requisição.

    Returns:
        Próximo ID incremental.
    """
    global _request_id
    _request_id += 1
    return _request_id

def _reset_account_details() -> None:
    """Reseta as variáveis públicas dos detalhes da conta."""
    global account_type, currency, balance, account_id
    account_type = None
    currency = None
    balance = None
    account_id = None
    print("Detalhes da conta limpos devido a falha ou desconexão.")

def test_network_connectivity() -> bool:
    """Testa a conectividade com o endpoint da API.

    Returns:
        True se a conectividade for bem-sucedida, False caso contrário.
    """
    try:
        print("Testando conectividade com ws.binaryws.com...")
        result = subprocess.run(
            ['ping', '-c', '4', 'ws.binaryws.com'],
            capture_output=True,
            text=True,
            timeout=10
        )
        print(f"Resultado do ping:\n{result.stdout}")
        if result.returncode != 0:
            print(f"Erro no ping: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("Timeout ao tentar pingar ws.binaryws.com. Verifique sua conexão de rede.")
        return False
    except Exception as e:
        print(f"Erro ao testar conectividade: {e}")
        return False

async def connect(app_name: str, token_name: str) -> None:
    """Estabelece a conexão com a API Deriv usando DerivAPI e AppDashboard.

    Args:
        app_name: Nome do aplicativo para obter o app_id.
        token_name: Nome do token para autorização.

    Raises:
        ValueError: Se a conexão ou autorização falhar.
    """
    global _api, _is_alive, _last_connection_time, _connection_failure_count, _last_disconnect_reason

    print(f"Iniciando conexão com a API usando app_name={app_name}, token_name={token_name}...")
    _reset_account_details()  # Limpa detalhes da conta ao iniciar nova conexão

    # Obtém credenciais do AppDashboard
    try:
        dashboard = AppDashboard(app_name=app_name, token_name=token_name)
        app_id = dashboard.app_id
        token = dashboard.token
        print(f"Credenciais obtidas do AppDashboard: app_id={app_id}, token={token}")
    except ValueError as e:
        raise ValueError(f"Falha ao obter credenciais do AppDashboard: {e}")

    # Testa conectividade antes de tentar a conexão
    if not test_network_connectivity():
        print("Conectividade de rede falhou. Pulando conexão com a API.")
        return

    try:
        # Cria a instância do DerivAPI
        print(f"Criando DerivAPI com app_id={app_id}, endpoint='wss://ws.binaryws.com/websockets/v3'")
        _api = DerivAPI(app_id=app_id, endpoint="w