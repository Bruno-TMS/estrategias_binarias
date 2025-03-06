import asyncio
import csv
import os
from deriv_api import DerivAPI

class Connection:
    def __init__(self):
        self._api = None
        self.account_type = "demo"
        self.app_id = None
        self.api_token = None
        self._load_credentials()

    def _load_credentials(self):
        secrets_path = os.path.join(os.path.dirname(__file__), '../configs/secrets.csv')
        try:
            with open(secrets_path, 'r') as file:
                reader = csv.reader(file)
                header = next(reader, None)
                if not header or header != ['app_id', 'api_token']:
                    raise ValueError("Cabeçalho inválido em secrets.csv. Esperado: app_id,api_token")
                for row in reader:
                    if row and len(row) >= 2:
                        self.app_id, self.api_token = row[0].strip(), row[1].strip()
                        break
                if self.app_id is None or self.api_token is None:
                    raise ValueError("Nenhuma credencial válida encontrada em secrets.csv")
        except FileNotFoundError:
            raise FileNotFoundError(f"Arquivo {secrets_path} não encontrado")
        except Exception as e:
            raise ValueError(f"Erro ao carregar credenciais de secrets.csv: {e}")
        print(f"Credenciais carregadas: app_id={self.app_id}, api_token={self.api_token[:5]}...")

    async def connect(self):
        print("Iniciando conexão com a API...")
        self._api = DerivAPI(app_id=self.app_id, api_token=self.api_token)
        await self._api.send({"authorize": self.api_token})
        print("Conexão ativa. Tipo de conta:", self.account_type)
        await self.get_available_symbols()

    async def is_alive(self):
        if not self._api:
            return False
        try:
            await self._api.send({"ping": 1})
            return True
        except Exception as e:
            print(f"Conexão não está ativa: {e}")
            return False

    async def get_available_symbols(self):
        try:
            response = await self.send({"active_symbols": "brief"})
            symbols = response.get("active_symbols", [])
            print("Ativos disponíveis:")
            for symbol in symbols:
                print(f"Symbol: {symbol['symbol']}, Display Name: {symbol['display_name']}, Trading Available: {symbol['is_trading_suspended'] == 0}")
            return symbols
        except Exception as e:
            print(f"Erro ao obter ativos disponíveis: {e}")
            raise

    async def send(self, request):
        if not self._api:
            print("Inicializando API...")
            self._api = DerivAPI(app_id=self.app_id, api_token=self.api_token)
            await self._api.send({"authorize": self.api_token})
        try:
            response = await self._api.send(request)
            return response
        except Exception as e:
            print(f"Erro na requisição: {e}")
            raise