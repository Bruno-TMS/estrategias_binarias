"""Módulo connection.py

Gerencia a conexão com a API Deriv usando DerivAPI, integrando o Singleton AppDashboard
para obter credenciais dinamicamente do CSV. Inclui teste de rede, reconexão com backoff,
manutenção de sessão via ping e gerenciamento de detalhes da conta.
"""

import asyncio
import subprocess
from datetime import datetime
from deriv_api import DerivAPI
from app_dashboard import AppDashboard  # Importa o Singleton do app_dashboard.py

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
        _api = DerivAPI(app_id=app_id, endpoint="wss://ws.binaryws.com/websockets/v3")
        # Armazena a instância do AppDashboard para reconexão
        _api._app_dashboard = dashboard

        # Autorização usando o método nativo do DerivAPI
        print(f"Autorizando com token={token}...")
        authorize_response = await asyncio.wait_for(_api.authorize(token), timeout=5.0)
        print(f"Autorização bem-sucedida: {authorize_response}")

        _is_alive = True
        _last_connection_time = datetime.now()
        _connection_failure_count = 0
        _last_disconnect_reason = None

        # Assina erros de sanidade
        _api.sanity_errors.subscribe(lambda err: print(f"Erro detectado: {err}"))
        print("Conexão ativa.")
        print(f"Última conexão: {_last_connection_time.strftime('%y/%m/%d %H:%M')}")
        asyncio.create_task(keep_alive())
    except asyncio.TimeoutError:
        _is_alive = False
        _connection_failure_count += 1
        _last_disconnect_reason = "timeout"
        print(f"Timeout na autorização (tentativa {_connection_failure_count}) após 5 segundos")
        raise ValueError("Timeout ao aguardar autorização.")
    except Exception as e:
        _is_alive = False
        _connection_failure_count += 1
        _last_disconnect_reason = "failure"
        print(f"Falha na conexão (tentativa {_connection_failure_count}): {e}")
        raise ValueError(f"Falha ao conectar: {e}")

async def reconnect() -> bool:
    """Tenta reconectar à API Deriv em caso de falha, com limite de tentativas.

    Returns:
        True se a reconexão for bem-sucedida, False caso contrário.
    """
    global _is_alive, _connection_failure_count, _last_disconnect_reason
    if _connection_failure_count >= _MAX_RECONNECT_ATTEMPTS:
        print(f"Limite de {_MAX_RECONNECT_ATTEMPTS} tentativas de reconexão atingido.")
        _is_alive = False
        _reset_account_details()
        _last_disconnect_reason = "failure"
        return False

    delay = _RECONNECT_DELAY * (2 ** (_connection_failure_count - 1))
    print(f"Tentando reconectar em {delay} segundos (tentativa {_connection_failure_count + 1}/{_MAX_RECONNECT_ATTEMPTS})...")
    await asyncio.sleep(delay)
    await disconnect()
    try:
        print("Tentativa de reconexão iniciada...")
        await connect(_api._app_dashboard._app_name, _api._app_dashboard._token_name)
        print("Reconexão bem-sucedida.")
        return True
    except Exception as e:
        _connection_failure_count += 1
        _is_alive = False
        _reset_account_details()
        print(f"Falha ao reconectar (tentativa {_connection_failure_count}): {e}")
        return False

async def keep_alive() -> None:
    """Mantém a sessão ativa enviando pings periódicos a cada 60 segundos."""
    global _is_alive
    while _is_alive:
        try:
            print("Enviando ping para manter a sessão ativa...")
            await asyncio.sleep(60)
            if _is_alive:
                response = await _api.ping()
                print(f"Ping enviado: {response}")
        except Exception as e:
            print(f"Erro ao enviar ping: {e}")
            if not await reconnect():
                break

async def load_account_details() -> dict:
    """Carrega e retorna os detalhes da conta acessada via requisições à API.

    Returns:
        Dicionário com detalhes da conta: account_type, currency, balance, account_id.

    Raises:
        ValueError: Se a conexão não estiver ativa ou os dados forem incompletos.
    """
    global account_type, currency, balance, account_id
    if not _is_alive:
        _reset_account_details()
        raise ValueError("Conexão não está ativa para carregar detalhes da conta.")

    try:
        req_id = _get_next_request_id()
        print(f"Carregando detalhes da conta (req_id={req_id})...")

        # Usa métodos nativos do DerivAPI (ajuste conforme documentação oficial)
        account_response = await asyncio.wait_for(_api.active_symbols("brief"), timeout=10.0)
        balance_response = await asyncio.wait_for(_api.balance(), timeout=10.0)

        # Extrai informações (pode precisar de ajustes conforme a API real)
        account_type = account_response.get("active_symbols", [{}])[0].get("market", "unknown")
        account_id = balance_response.get("balance", {}).get("account_id", "unknown")
        currency = balance_response.get("balance", {}).get("currency")
        balance = balance_response.get("balance", {}).get("balance")

        if not all([account_type, account_id, currency, balance]):
            raise ValueError("Dados da conta incompletos.")

        print(f"Detalhes da conta carregados (req_id={req_id}): tipo={account_type}, moeda={currency}, saldo={balance}, ID={account_id}")
        return {
            "account_type": account_type,
            "currency": currency,
            "balance": balance,
            "account_id": account_id
        }
    except asyncio.TimeoutError:
        _reset_account_details()
        raise ValueError("Timeout ao aguardar detalhes da conta.")
    except Exception as e:
        _reset_account_details()
        raise ValueError(f"Erro ao carregar detalhes da conta: {e}")

async def update_balance() -> float:
    """Atualiza o saldo e a moeda da conta acessada via requisição à API.

    Returns:
        O saldo atualizado.

    Raises:
        ValueError: Se a conexão não estiver ativa ou o saldo não for retornado.
    """
    global balance, currency
    if not _is_alive:
        _reset_account_details()
        raise ValueError("Conexão não está ativa para atualizar o saldo.")

    try:
        req_id = _get_next_request_id()
        print(f"Atualizando saldo (req_id={req_id})...")
        response = await asyncio.wait_for(_api.balance(), timeout=10.0)
        balance = response.get("balance", {}).get("balance")
        currency = response.get("balance", {}).get("currency")

        if balance is None:
            raise ValueError("Saldo não retornado pela API.")

        print(f"Saldo atualizado (req_id={req_id}): moeda={currency}, saldo={balance}")
        return balance
    except asyncio.TimeoutError:
        _reset_account_details()
        raise ValueError("Timeout ao atualizar saldo.")
    except Exception as e:
        _reset_account_details()
        raise ValueError(f"Erro ao atualizar saldo: {e}")

async def send(request: dict) -> dict:
    """Envia uma requisição genérica para a API Deriv usando DerivAPI.

    Args:
        request: Dicionário com a requisição a ser enviada.

    Returns:
        Resposta da API.

    Raises:
        ValueError: Se a conexão falhar e a reconexão não for bem-sucedida.
    """
    global _api, _is_alive, _last_disconnect_reason
    if not _is_alive:
        print("Conexão não ativa, iniciando nova conexão...")
        await connect(_api._app_dashboard._app_name, _api._app_dashboard._token_name)

    try:
        print(f"Enviando requisição: {request}")
        response = await _api.send(request)
        print(f"Resposta recebida: {response}")
        return response
    except Exception as e:
        print(f"Erro na requisição: {e}")
        _is_alive = False
        _reset_account_details()
        _last_disconnect_reason = "failure"
        if not await reconnect():
            raise ValueError(f"Falha ao enviar requisição após reconexão: {e}")

async def disconnect() -> None:
    """Fecha a conexão com a API Deriv e limpa os detalhes da conta."""
    global _api, _is_alive, _last_connection_time, _last_disconnect_reason
    if _api:
        print("Desconectando da API...")
        await _api.clear()
        _api = None
        _is_alive = False
        _last_connection_time = datetime.now()
        _last_disconnect_reason = "normal"
        _reset_account_details()
        print(f"Última desconexão: {_last_connection_time.strftime('%y/%m/%d %H:%M')}, Motivo: {_last_disconnect_reason}")

if __name__ == "__main__":
    async def test_connection():
        """Testa o carregamento de credenciais, conexão e detalhes da conta."""
        global _is_alive
        start_time = datetime.now().strftime("%y/%m/%d %H:%M")
        print(f"Iniciando teste de conexão {start_time}")
        status = "Sucesso"
        try:
            # Obtém chaves disponíveis do AppDashboard
            key_names = AppDashboard.get_key_names()
            print(f"Chaves disponíveis no CSV: {key_names}")

            # Seleciona o primeiro app e token disponíveis
            app_names = key_names.get("app", [])
            token_names = key_names.get("token", [])
            if not app_names or not token_names:
                raise ValueError("Nenhum app ou token disponível no CSV.")

            app_name = app_names[0]
            token_name = token_names[0]
            print(f"Usando app_name={app_name}, token_name={token_name} para o teste...")

            # Conecta usando AppDashboard
            print("Iniciando conexão...")
            await connect(app_name=app_name, token_name=token_name)
            print(f"Estado da conexão (is_alive): {_is_alive}")
            print(f"Contador de falhas: {_connection_failure_count}")
            print(f"Motivo da última desconexão: {_last_disconnect_reason}")

            # Carrega detalhes da conta
            details = await load_account_details()
            print(f"Detalhes da conta: {details}")

            # Atualiza saldo
            new_balance = await update_balance()
            print(f"Saldo atualizado: {new_balance}")

            await asyncio.sleep(5)
            print("Desconectando após teste...")
            await disconnect()
            print(f"Estado da conexão (is_alive): {_is_alive}")
            print(f"Contador de falhas: {_connection_failure_count}")
            print(f"Motivo da última desconexão: {_last_disconnect_reason}")
            print(f"Detalhes da conta após desconexão: account_type={account_type}, currency={currency}, balance={balance}, account_id={account_id}")
        except Exception as e:
            print(f"Erro durante o teste: {e}")
            status = "Falha"
            _is_alive = False
            _reset_account_details()
        finally:
            end_time = datetime.now().strftime("%y/%m/%d %H:%M")
            print(f"Finalizando teste de conexão - Status: {status} {end_time}")

    asyncio.run(test_connection())