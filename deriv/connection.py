import asyncio
import websockets
from deriv_api import DerivAPI, APIError
from csv import DictReader
from pathlib import Path
from datetime import datetime

KNV_FILE = Path(Path(__file__).parent, "knv.csv")

class AppDashboard:
    _instance = None

    def __new__(cls, *, app_name: str, token_name: str):
        if cls._instance and (
            cls._instance._app_name != app_name or 
            cls._instance._token_name != token_name
        ):
            cls._instance = None

        if not cls._instance:
            app_id = None
            token = None
           
            if not KNV_FILE.exists():
               raise FileNotFoundError(f"Arquivo CSV '{KNV_FILE}' não encontrado.")
           
            with open(KNV_FILE, "r", encoding="utf-8") as csv_file:
                csv_reader = DictReader(csv_file)
                for row in csv_reader:
                    if row["key"] == "app" and row["name"] == app_name:
                        app_id = row["value"]
                    if row["key"] == "token" and row["name"] == token_name:
                        token = row["value"]
            if not (app_id and token):
                raise ValueError(f"App '{app_name}' ou token '{token_name}' não encontrados no CSV.")
            cls._instance = super().__new__(cls)
            cls._instance._app_id = app_id
            cls._instance._token = token
            cls._instance._app_name = app_name
            cls._instance._token_name = token_name
        return cls._instance

    @property
    def app_id(self):
        return self._app_id

    @property
    def token(self):
        return self._token

    @property
    def app_name(self):
        return self._app_name

    @property
    def token_name(self):
        return self._token_name

    @classmethod
    def get_key_names(cls):
        key_names = {}
        
        if not KNV_FILE.exists():
               raise FileNotFoundError(f"Arquivo CSV '{KNV_FILE}' não encontrado.")
        
        with open(KNV_FILE, "r", encoding="utf-8") as csv_file:
            csv_reader = DictReader(csv_file)
            for row in csv_reader:
                key_names.setdefault(row["key"], []).append(row["name"])
        return key_names

class UserAccount:
    _instance = None

    def __new__(cls, balance, currency, currency_type, is_virtual, loginid, scopes):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._balance = balance
            cls._instance._currency = currency
            cls._instance._currency_type = currency_type
            cls._instance._is_virtual = is_virtual
            cls._instance._loginid = loginid
            cls._instance._scopes = scopes
        return cls._instance

    @property
    def balance(self):
        return self._balance

    @property
    def currency(self):
        return self._currency

    @property
    def currency_type(self):
        return self._currency_type

    @property
    def is_virtual(self):
        return self._is_virtual

    @property
    def loginid(self):
        return self._loginid

    @property
    def scopes(self):
        return self._scopes

class Connector:
    _instance = None
    _api = None
    _connection = None
    _connection_open = None
    _connection_close = None
    _disconnect_status = None

    def __new__(cls, app_id, token):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self, app_id, token):
        if self.is_alive:
            print("Já conectado ao servidor.")
            return await self._api.authorize(token)
        response = None
        try:
            self._connection = await websockets.connect(f"wss://ws.binaryws.com/websockets/v3?app_id={app_id}")
            self._api = DerivAPI(connection=self._connection)
            response = await asyncio.wait_for(self._api.authorize(token), timeout=5.0)
            self._connection_open = datetime.now()
            self._connection_close = None
            self._disconnect_status = None
        except APIError as e:
            print(f"Falha ao conectar à API Deriv (APIError): {e}")
            if self._connection and self._connection.closed:
                self._connection_close = datetime.now()
                self._disconnect_status = "falha"
            self._connection = None
            self._api = None
        except Exception as e:
            print(f"Falha ao conectar à API Deriv (Outro erro): {e}")
            if self._connection and self._connection.closed:
                self._connection_close = datetime.now()
                self._disconnect_status = "falha"
            self._connection = None
            self._api = None
        return response

    async def disconnect(self):
        if not self.is_alive:
            print("Conexão já está fechada.")
            return
        await self._connection.close()
        self._connection_close = datetime.now()
        self._disconnect_status = "normal"
        self._connection = None
        self._api = None

    async def send_request(self, msg):
        if not self.is_alive:
            print("Não conectado ao servidor.")
            return None
        response = None
        try:
            response = await self._api.send(msg)
        except APIError as e:
            print(f"Erro na requisição à API Deriv (APIError): {e}")
            if self._connection and self._connection.closed:
                self._connection_close = datetime.now()
                self._disconnect_status = "falha"
                self._connection = None
                self._api = None
        except Exception as e:
            print(f"Erro na requisição (Outro erro): {e}")
            if self._connection and self._connection.closed:
                self._connection_close = datetime.now()
                self._disconnect_status = "falha"
                self._connection = None
                self._api = None
        return response

    @property
    def is_alive(self):
        return self._connection is not None and not self._connection.closed

    @property
    def connection_open(self):
        return self._connection_open

    @property
    def connection_close(self):
        return self._connection_close

    @property
    def disconnect_status(self):
        return self._disconnect_status

class ConnManager:
    _instance = None
    _dashboard = None
    _connector = None
    _user_account = None

    def __new__(cls, app_name, token_name):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._dashboard = AppDashboard(app_name=app_name, token_name=token_name)
            cls._instance._connector = Connector(cls._instance._dashboard.app_id, cls._instance._dashboard.token)
        return cls._instance

    async def connect(self):
        if not self._connector.is_alive:
            response = await self._connector.connect(self._dashboard.app_id, self._dashboard.token)
            if response:
                self._user_account = UserAccount(
                    balance=response['authorize']['balance'],
                    currency=response['authorize']['currency'],
                    currency_type=response['authorize']['account_list'][0]['currency_type'],
                    is_virtual=response['authorize']['is_virtual'],
                    loginid=response['authorize']['loginid'],
                    scopes=response['authorize']['scopes']
                )
                print(f"Usuário logado com sucesso: LoginID={self._user_account.loginid}, Balance={self._user_account.balance} {self._user_account.currency}, Currency Type={self._user_account.currency_type}, Is Virtual={self._user_account.is_virtual}, Scopes={self._user_account.scopes}")
        else:
            print("Conexão já está ativa.")

    async def disconnect(self):
        await self._connector.disconnect()
        if not self._connector.is_alive:
            print("Usuário deslogado")
            self._user_account = None
        print(f"Conexão desconectada: Status={self._connector.disconnect_status}, Fechada em={self._connector.connection_close}")

    async def send_request(self, msg):
        return await self._connector.send_request(msg)

    async def update_balance(self):
        if not self._connector.is_alive:
            print("Não conectado ao servidor para atualizar saldo.")
            return
        if self._user_account is None:
            print("Nenhum usuário logado para atualizar saldo.")
            return
        response = await self._connector.send_request({"balance": 1})
        if response:
            self._user_account._balance = response['balance']['balance']

    @property
    def user_account(self):
        return self._user_account

if __name__ == "__main__":
    async def test_connection():
        key_names = AppDashboard.get_key_names()
        print(f"Chaves disponíveis no CSV: {key_names}")
        app_names = key_names.get("app", [])
        token_names = key_names.get("token", [])
        if not app_names or not token_names:
            print("Nenhum app ou token disponível no CSV.")
            return
        app_name = app_names[0]
        token_name = token_names[0]
        print(f"Tentando conectar com app_name={app_name}, token_name={token_name}...")
        manager = ConnManager(app_name, token_name)
        await manager.connect()
        await asyncio.sleep(2)  # Simula espera para testar estado
        print(f"Estado da conexão após espera: {manager._connector.is_alive}")
        await manager.disconnect()

    asyncio.run(test_connection())   
        