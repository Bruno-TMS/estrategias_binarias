import asyncio
import csv
import os
from deriv_api import DerivAPI

class Connection:
    def __init__(self):
        self.api = None
        self.account_type = "demo"  # Padrão, pode ser ajustado
        self.app_id = None  # Inicializa como None
        self.api_token = None  # Inicializa como None
        self._load_credentials()

    def _load_credentials(self):
        secrets_path = os.path.join(os.path.dirname(__file__), '../configs/secrets.csv')
        try:
            with open(secrets_path, 'r') as file:
                reader = csv.reader(file)
                # Pula o cabeçalho
                header = next(reader, None)
                if not header or header != ['app_id', 'api_token']:
                    raise ValueError("Cabeçalho inválido em secrets.csv. Esperado: app_id,api_token")
                # Pega a primeira linha válida
                for row in reader:
                    if row and len(row) >= 2:  # Garante que a linha tenha pelo menos 2 colunas
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
        self.api = DerivAPI(app_id=self.app_id, api_token=self.api_token)
        # Autenticação explícita
        await self.api.send({"authorize": self.api_token})
        print("Conexão ativa. Tipo de conta:", self.account_type)
        # Verifica ativos disponíveis
        await self.get_available_symbols()

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
        if not self.api:
            print("Inicializando API...")
            self.api = DerivAPI(app_id=self.app_id, api_token=self.api_token)
            # Autenticação explícita ao reinicializar
            await self.api.send({"authorize": self.api_token})
        try:
            response = await self.api.send(request)
            return response
        except Exception as e:
            print(f"Erro na requisição: {e}")
            raise