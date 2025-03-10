import asyncio
import subprocess
from datetime import datetime
from deriv_api import DerivAPI
from deriv.app_dashboard import get_dashboard_list, update_dashboard, get_app_id, get_token

# Carregar credenciais no início (síncrono)
dashboard_list = get_dashboard_list()  # Síncrona
app_name = dashboard_list.get('apps', [])[0] if dashboard_list.get('apps') else None
token_name = dashboard_list.get('tokens', [])[0] if dashboard_list.get('tokens') else None

if not app_name or not token_name:
    raise ValueError("Nenhum app ou token disponível em get_dashboard_list(). Verifique _APPS e _TOKENS em app_dashboard.py.")

success = update_dashboard(app_name, token_name)  # Síncrona
if not success:
    raise ValueError(f"Falha ao atualizar dashboard com app_name={app_name}, token_name={token_name}.")

_app_id = get_app_id()  # Síncrona
_token = get_token()    # Síncrona

if _app_id is None or _token is None:
    raise ValueError("Credenciais inválidas após atualização. Verifique app_dashboard.py.")

print(f"Credenciais carregadas no início: app_id={_app_id}, token={_token}")  # Mostrar token completo

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

def _get_next_request_id():
    """Gera o próximo ID de requisição."""
    global _request_id
    _request_id += 1
    return _request_id

def _reset_account_details():
    """Reseta as variáveis públicas dos detalhes da conta."""
    global account_type, currency, balance, account_id
    account_type = None
    currency = None
    balance = None
    account_id = None
    print("Detalhes da conta limpos devido a falha ou desconexão.")

def test_network_connectivity():
    """Testa a conectividade com o endpoint da API."""
    try:
        print("Testando conectividade com ws.binaryws.com...")
        result = subprocess.run(['ping', '-c', '4', 'ws.binaryws.com'], capture_output=True, text=True, timeout=10)
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

async def connect():
    """Estabelece a conexão com a API Deriv usando DerivAPI."""
    global _api, _is_alive, _last_connection_time, _connection_failure_count, _last_disconnect_reason
    print("Iniciando conexão com a API...")
    _reset_account_details()  # Limpa detalhes da conta ao iniciar nova conexão

    # Testar conectividade antes de tentar a conexão
    if not test_network_connectivity():
        print("Conectividade de rede falhou. Pulando conexão com a API para depuração.")
        return  # Pular a conexão se a rede falhar

    try:
        print(f"Creating DerivAPI with app_id={_app_id}, endpoint='wss://ws.binaryws.com/websockets/v3'")
        _api = DerivAPI(app_id=_app_id, endpoint='wss://ws.binaryws.com/websockets/v3')
        print("DerivAPI instance created, authorizing with token...")
        req_id = _get_next_request_id()
        print(f"Sending authorize request with token={_token}... (req_id={req_id})")  # Mostrar token completo
        authorize_request = {"authorize": _token, "req_id": req_id}
        print(f"Enviando requisição manual de autorização: {authorize_request}")
        response = await asyncio.wait_for(_api.send(authorize_request), timeout=5.0)
        print(f"Resposta recebida da requisição manual: {response}")
        print(f"Authorization request sent (req_id={req_id}), waiting for response...")
        authorize_response = await asyncio.wait_for(_api.expect_response('authorize'), timeout=5.0)
        print(f"Authorization response received (req_id={req_id}):", authorize_response)
        print(f"Autorização bem-sucedida (req_id={req_id}):", authorize_response)
        _is_alive = True
        _last_connection_time = datetime.now()
        _connection_failure_count = 0
        _last_disconnect_reason = None
        _api.sanity_errors.subscribe(lambda err: print(f"Erro detectado: {err}"))
        print("Conexão ativa.")
        print(f"Última conexão: {_last_connection_time.strftime('%y/%m/%d %H:%M')}")
        asyncio.create_task(keep_alive())
    except asyncio.TimeoutError:
        _is_alive = False
        _connection_failure_count += 1
        _last_disconnect_reason = 'timeout'
        print(f"Timeout na autorização (tentativa {_connection_failure_count}) após {5.0} segundos")
        raise ValueError("Timeout ao aguardar autorização.")
    except Exception as e:
        _is_alive = False
        _connection_failure_count += 1
        _last_disconnect_reason = 'failure'
        print(f"Falha na conexão (tentativa {_connection_failure_count}): {e}")
        raise ValueError(f"Falha ao conectar: {e}")

async def reconnect():
    """Tenta reconectar à API Deriv em caso de falha, com limite de tentativas."""
    global _is_alive, _connection_failure_count, _last_disconnect_reason
    if _connection_failure_count >= _MAX_RECONNECT_ATTEMPTS:
        print(f"Limite de {_MAX_RECONNECT_ATTEMPTS} tentativas de reconexão atingido.")
        _is_alive = False
        _reset_account_details()
        _last_disconnect_reason = 'failure'
        return False
    delay = _RECONNECT_DELAY * (2 ** (_connection_failure_count - 1))
    print(f"Tentando reconectar em {delay} segundos (tentativa {_connection_failure_count + 1}/{_MAX_RECONNECT_ATTEMPTS})...")
    await asyncio.sleep(delay)
    await disconnect()
    try:
        print("Tentativa de reconexão iniciada...")
        await connect()
        print("Reconexão bem-sucedida.")
        return True
    except Exception as e:
        _connection_failure_count += 1
        _is_alive = False
        _reset_account_details()
        print(f"Falha ao reconectar (tentativa {_connection_failure_count}): {e}")
        return False

async def keep_alive():
    """Mantém a sessão ativa enviando pings periódicos a cada 60 segundos."""
    global _is_alive
    while _is_alive:
        try:
            print("Enviando ping para manter a sessão ativa...")
            await asyncio.sleep(60)
            if _is_alive:
                response = await _api.ping({'ping': 1})
                print(f"Ping enviado: {response}")
        except Exception as e:
            print(f"Erro ao enviar ping: {e}")
            if not await reconnect():
                break

async def load_account_details():
    """Carrega e retorna os detalhes da conta acessada via requisições à API."""
    global account_type, currency, balance, account_id
    if not _is_alive:
        _reset_account_details()
        raise ValueError("Conexão não está ativa para carregar detalhes da conta.")
    try:
        req_id = _get_next_request_id()
        print(f"Carregando detalhes da conta (req_id={req_id})...")
        response_account = await asyncio.wait_for(_api.account_list(), timeout=10.0)
        print(f"Resposta account_list recebida: {response_account}")
        accounts = response_account.get("account_list", [])
        if accounts:
            account_type = accounts[0].get("account_type")
            account_id = accounts[0].get("loginid")
            currency = accounts[0].get("currency")

        response_balance = await asyncio.wait_for(_api.balance(), timeout=10.0)
        print(f"Resposta balance recebida: {response_balance}")
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
        _reset_account_details()
        raise ValueError("Timeout ao aguardar detalhes da conta.")
    except Exception as e:
        _reset_account_details()
        raise ValueError(f"Erro ao carregar detalhes da conta: {e}")

async def update_balance():
    """Atualiza o saldo e a moeda da conta acessada via requisição à API."""
    global balance, currency
    if not _is_alive:
        _reset_account_details()
        raise ValueError("Conexão não está ativa para atualizar o saldo.")
    try:
        req_id = _get_next_request_id()
        print(f"Atualizando saldo (req_id={req_id})...")
        response_balance = await asyncio.wait_for(_api.balance(), timeout=10.0)
        print(f"Resposta balance recebida: {response_balance}")
        balance = response_balance.get("balance", {}).get("balance")
        currency = response_balance.get("balance", {}).get("currency")

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

async def send(request):
    """Envia uma requisição genérica para a API Deriv usando DerivAPI."""
    global _api, _is_alive, _last_disconnect_reason
    if not _is_alive:
        print("Conexão não ativa, iniciando nova conexão...")
        await connect()
    try:
        print(f"Enviando requisição: {request}")
        response = await _api.send(request)
        print(f"Resposta recebida: {response}")
        return response
    except Exception as e:
        print(f"Erro na requisição: {e}")
        _is_alive = False
        _reset_account_details()
        _last_disconnect_reason = 'failure'
        if not await reconnect():
            raise

async def disconnect():
    """Fecha a conexão com a API Deriv e limpa os detalhes da conta."""
    global _api, _is_alive, _last_connection_time, _last_disconnect_reason
    if _api:
        print("Desconectando da API...")
        await _api.clear()
        _api = None
        _is_alive = False
        _last_connection_time = datetime.now()
        _last_disconnect_reason = 'normal'
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
            print("Iniciando conexão...")
            await connect()
            print(f"Estado da conexão (is_alive): {_is_alive}")
            print(f"Contador de falhas: {_connection_failure_count}")
            print(f"Motivo da última desconexão: {_last_disconnect_reason}")
            details = await load_account_details()
            print(f"Detalhes da conta: {details}")
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