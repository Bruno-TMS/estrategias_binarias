import asyncio
import websockets
from deriv_api import DerivAPI, APIError
from csv import DictReader
from pathlib import Path

KNV_FILE =Path(Path(__file__).parent,"knv.csv")

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
            print(f"Usuário logado com sucesso: LoginID={cls._instance._loginid}, Balance={cls._instance._balance} {cls._instance._currency}, Currency Type={cls._instance._currency_type}, Is Virtual={cls._instance._is_virtual}, Scopes={cls._instance._scopes}")
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

    def __new__(cls, app_id, token):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self, app_id, token):
        response = None
        try:
            self._connection = await websockets.connect(f"wss://ws.binaryws.com/websockets/v3?app_id={app_id}")
            self._api = DerivAPI(connection=self._connection)
            response = await asyncio.wait_for(self._api.authorize(token), timeout=5.0)
        except APIError as e:
            print(f"Falha ao conectar à API Deriv (APIError): {e}")
        except Exception as e:
            print(f"Falha ao conectar à API Deriv (Outro erro): {e}")
        return response

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
        response = await self._connector.connect(self._dashboard.app_id, self._dashboard.token)
        if response and 'authorize' in response:
            self._user_account = UserAccount(
                balance=response['authorize']['balance'],
                currency=response['authorize']['currency'],
                currency_type=response['authorize']['account_list'][0]['currency_type'],
                is_virtual=response['authorize']['is_virtual'],
                loginid=response['authorize']['loginid'],
                scopes=response['authorize']['scopes']
            )
        print(f"Resposta do servidor: {response}")

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

    asyncio.run(test_connection())