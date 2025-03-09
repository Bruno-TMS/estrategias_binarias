"""Módulo para gerenciar a conexão com a API Deriv de forma confiável usando DerivAPI.

Este módulo utiliza a biblioteca DerivAPI para gerenciar a conexão, autenticar com token,
manter a sessão ativa, fornecer detalhes da conta e atualizar o saldo, com suporte a
reconexão automática, rastreio de falhas e limpeza de dados em caso de desconexão ou falha.
Inclui timeout para expect_response e tentativa de uso de req_id.
"""

import asyncio
from datetime import datetime
from deriv_api import DerivAPI
from deriv.app_dashboard import get_dashboard_list, update_dashboard, get_app_id, get_token

# Variáveis globais para gerenciar a conexão e credenciais
_api = None
_app_id = None
_token = None
_is_alive = False  # Indica se a conexão está ativa
_last_connection_time = None  # Armazena data/hora da última conexão
_connection_failure_count = 0  # Contador de falhas de conexão
_MAX_RECONNECT_ATTEMPTS = 5  # Limite de tentativas de reconexão
_RECONNECT_DELAY = 2  # Delay inicial de reconexão em segundos (aumenta com backoff)
_last_disconnect_reason = None  # Motivo da última desconexão ('normal' ou 'failure')
# Variáveis públicas para informações da conta
account_type = None  # Tipo de conta (ex.: 'binary')
currency = None  # Moeda da conta (ex.: 'USD', 'GBP', etc.)
balance = None  # Saldo da conta (valor numérico)
account_id = None  # ID da conta

# Contador para req_id
_request_id = 0

def _reset_account_details():
    """Reseta as variáveis públicas dos detalhes da conta."""
    global account_type, currency, balance, account_id
    account_type = None
    currency = None
    balance = None
    account_id = None
    print("Detalhes da conta limpos devido a falha ou desconexão.")


def _get_next_request_id():
    """Gera o próximo ID de requisição."""
    global _request_id
    _request_id += 1
    return _request_id


def load_credentials():
    """Carrega as credenciais do app_dashboard e atualiza as variáveis globais.

    Raises:
        ValueError: Se houver falha ao carregar ou atualizar credenciais.
        RuntimeError: Se a conexão estiver ativa (is_alive=True).
    """
    global _app_id, _token, _is_alive, _connection_failure_count

    if _is_alive:
        raise RuntimeError("Conexão ativa. Desconecte antes de atualizar credenciais.")

    dashboard = get_dashboard_list()
    
    app_name = dashboard.get('apps', [])[0] if dashboard.get('apps', []) else None
    token_name = dashboard.get('tokens', [])[0] if dashboard.get('tokens', []) else None

    if not app_name or not token_name:
        raise ValueError("Nenhum app ou token disponível no app_dashboard.")

    success = update_dashboard(app_name, token_name)
    if not success:
        raise ValueError("Falha ao atualizar credenciais do app_dashboard.")

    _app_id = get_app_id()
    _token = get_token()

    if not _app_id or not _token:
        raise ValueError("Credenciais inválidas: app_id ou token não podem ser vazios.")

    _connection_failure_count = 0  # Reseta o contador ao carregar novas credenciais
    print(f"Credenciais carregadas: app_id={_app_id}, token={_token[:5]}...")


async def connect():
    """Estabelece a conexão com a API Deriv usando DerivAPI.

    Usa expect_response com timeout para aguardar a autorização.

    Raises:
        ValueError: Se a conexão ou autenticação falhar.
    """
    global _api, _is_alive, _last_connection_time, _connection_failure_count, _last_disconnect_reason
    print("Iniciando conexão com a API...")
    _reset_account_details()  # Limpa detalhes da conta ao iniciar nova conexão
    try:
        _api = DerivAPI(app_id=_app_id)
        # Inicia a autenticação com req_id
        req_id = _get_next_request_id()
        asyncio.create_task(_api.authorize(_token))
        authorize_response = await asyncio.wait_for(_api.expect_response('authorize'), timeout=10.0)
        print(f"Autorização bem-sucedida (req_id={req_id}):", authorize_response)
        _is_alive = True
        _last_connection_time = datetime.now()
        _connection_failure_count = 0  # Reseta o contador após conexão bem-sucedida
        _last_disconnect_reason = None  # Reseta o motivo ao conectar
        # Monitora erros da API
        _api.sanity_errors.subscribe(lambda err: print(f"Erro detectado: {err}"))
        print("Conexão ativa.")
        print(f"Última conexão: {_last_connection_time.strftime('%y/%m/%d %H:%M')}")
        # Inicia o keep_alive em uma tarefa separada
        asyncio.create_task(keep_alive())
    except asyncio.TimeoutError:
        _is_alive = False
        _connection_failure_count += 1
        _last_disconnect_reason = 'failure'
        print(f"Timeout na autorização (tentativa {_connection_failure_count})")
        raise ValueError("Timeout ao aguardar autorização.")
    except Exception as e:
        _is_alive = False
        _connection_failure_count += 1
        _last_disconnect_reason = 'failure'
        print(f"Falha na conexão (tentativa {_connection_failure_count}): {e}")
        raise ValueError(f"Falha ao conectar: {e}")


async def reconnect():
    """Tenta reconectar à API Deriv em caso de falha, com limite de tentativas.

    Returns:
        bool: True se reconexão for bem-sucedida, False caso contrário.
    """
    global _is_alive, _connection_failure_count, _last_disconnect_reason
    if _connection_failure_count >= _MAX_RECONNECT_ATTEMPTS:
        print(f"Limite de {_MAX_RECONNECT_ATTEMPTS} tentativas de reconexão atingido.")
        _is_alive = False
        _reset_account_details()  # Limpa detalhes em caso de falha máxima
        _last_disconnect_reason = 'failure'
        return False

    delay = _RECONNECT_DELAY * (2 ** (_connection_failure_count - 1))
    print(f"Tentando reconectar em {delay} segundos (tentativa {_connection_failure_count + 1}/{_MAX_RECONNECT_ATTEMPTS})...")
    await asyncio.sleep(delay)
    await disconnect()  # Garante que a conexão anterior seja fechada
    try:
        await connect()
        return True
    except Exception as e:
        _connection_failure_count += 1
        _is_alive = False
        _reset_account_details()  # Limpa detalhes em caso de falha
        _last_disconnect_reason = 'failure'
        print(f"Falha ao reconectar (tentativa {_connection_failure_count}): {e}")
        return False


async def keep_alive():
    """Mantém a sessão ativa enviando pings periódicos a cada 60 segundos."""
    global _is_alive
    while _is_alive:
        try:
            await asyncio.sleep(60)  # Ping a cada 60 segundos
            if _is_alive:
                response = await _api.ping({'ping': 1})
                print(f"Ping enviado: {response}")
        except Exception as e:
            print(f"Erro ao enviar ping: {e}")
            if not await reconnect():
                break


async def load_account_details():
    """Carrega e retorna os detalhes da conta acessada via requisições à API.

    Usa expect_response com timeout para aguardar as respostas específicas.

    Returns:
        dict: Detalhes da conta (account_type, currency, balance, account_id).
    """
    global account_type, currency, balance, account_id
    if not _is_alive:
        _reset_account_details()
        raise ValueError("Conexão não está ativa para carregar detalhes da conta.")
    try:
        # Carrega o tipo de conta, ID e moeda
        req_id = _get_next_request_id()
        asyncio.create_task(_api.send({"account_list": 1, "req_id": req_id}))
        response_account = await asyncio.wait_for(_api.expect_response("account_list"), timeout=10.0)
        accounts = response_account.get("account_list", [])
        if accounts:
            account_type = accounts[0].get("account_type")
            account_id = accounts[0].get("loginid")
            currency = accounts[0].get("currency")  # Obtém a moeda da conta

        # Carrega o saldo
        req_id = _get_next_request_id()
        asyncio.create_task(_api.balance())
        response_balance = await asyncio.wait_for(_api.expect_response("balance"), timeout=10.0)
        balance = response_balance.get("balance", {}).get("balance")

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
        _reset_account_details()  # Limpa em caso de timeout
        raise ValueError("Timeout ao aguardar detalhes da conta.")
    except Exception as e:
        _reset_account_details()  # Limpa em caso de erro na requisição
        raise ValueError(f"Erro ao carregar detalhes da conta: {e}")


async def update_balance():
    """Atualiza o saldo e a moeda da conta acessada via requisição à API.

    Retorna o saldo atualizado, útil após tentativas de contrato.

    Returns:
        float: Novo valor do saldo.
    """
    global balance, currency
    if not _is_alive:
        _reset_account_details()
        raise ValueError("Conexão não está ativa para atualizar o saldo.")
    try:
        # Carrega o saldo atualizado
        req_id = _get_next_request_id()
        asyncio.create_task(_api.balance())
        response_balance = await asyncio.wait_for(_api.expect_response("balance"), timeout=10.0)
        balance = response_balance.get("balance", {}).get("balance")
        currency = response_balance.get("balance", {}).get("currency")

        if balance is None:
            raise ValueError("Saldo não retornado pela API.")
        
        print(f"Saldo atualizado (req_id={req_id}): moeda={currency}, saldo={balance}")
        return balance
    except asyncio.TimeoutError:
        _reset_account_details()  # Limpa em caso de timeout
        raise ValueError("Timeout ao atualizar saldo.")
    except Exception as e:
        _reset_account_details()  # Limpa em caso de erro
        raise ValueError(f"Erro ao atualizar saldo: {e}")


async def send(request):
    """Envia uma requisição genérica para a API Deriv.

    Args:
        request (dict): Requisição a ser enviada.

    Returns:
        dict: Resposta da API.

    Raises:
        Exception: Se a requisição falhar.
    """
    global _api, _is_alive, _last_disconnect_reason
    if not _is_alive:
        await connect()
    try:
        response = await _api.send(request)
        return response
    except Exception as e:
        print(f"Erro na requisição: {e}")
        _is_alive = False  # Marca como desconectado
        _reset_account_details()  # Limpa detalhes em caso de falha
        _last_disconnect_reason = 'failure'
        if not await reconnect():
            raise
        raise


async def disconnect():
    """Fecha a conexão com a API Deriv e limpa os detalhes da conta."""
    global _api, _is_alive, _last_connection_time, _last_disconnect_reason
    if _api:
        print("Desconectando da API...")
        await _api.clear()  # Usa clear() para desconectar e cancelar tarefas
        _api = None
        _is_alive = False
        _last_connection_time = datetime.now()
        _last_disconnect_reason = 'normal'
        _reset_account_details()  # Limpa detalhes da conta
        print(f"Última desconexão: {_last_connection_time.strftime('%y/%m/%d %H:%M')}, Motivo: {_last_disconnect_reason}")


# Carrega credenciais ao iniciar o módulo
load_credentials()


if __name__ == "__main__":
    async def test_connection():
        """Testa o carregamento de credenciais, conexão e detalhes da conta."""
        global _is_alive  # Garante acesso à variável global
        start_time = datetime.now().strftime("%y/%m/%d %H:%M")
        print(f"Iniciando teste de conexão {start_time}")
        status = "Sucesso"
        try:
            await connect()
            print(f"Estado da conexão (is_alive): {_is_alive}")
            print(f"Contador de falhas: {_connection_failure_count}")
            print(f"Motivo da última desconexão: {_last_disconnect_reason}")
            details = await load_account_details()
            print(f"Detalhes da conta: {details}")
            new_balance = await update_balance()
            print(f"Saldo atualizado: {new_balance}")
            await asyncio.sleep(5)  # Testa por 5 segundos
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
            print("Finalizando teste de conexão")
            print(f"Status: {status} {end_time}")

    asyncio.run(test_connection())