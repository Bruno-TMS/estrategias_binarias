import csv
import os
from deriv_api import DerivAPI

class Connection:
    def __init__(self):
        self.secrets = self.load_secrets()
        required_keys = ['api_token', 'account_type']  # Removido 'app_id' da lista
        missing_keys = [key for key in required_keys if key not in self.secrets]
        if missing_keys:
            raise ValueError(f"Chaves ausentes no secrets.csv: {missing_keys}")
        self.api = DerivAPI()  # Removido app_id da inicialização
        self.is_alive = False
        self.account_type = self.secrets['account_type']

    def load_secrets(self):
        secrets_path = os.path.join(os.path.dirname(__file__), '../configs/secrets.csv')
        secrets = {}
        try:
            with open(secrets_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile, fieldnames=['key', 'value'])
                next(reader)  # Pula o cabeçalho
                for row in reader:
                    secrets[row['key']] = row['value']
        except FileNotFoundError:
            print(f"Erro: Arquivo {secrets_path} não encontrado")
        except Exception as e:
            print(f"Erro ao ler secrets.csv: {e}")
        return secrets

    async def connect(self):
        await self.api.authorize(self.secrets['api_token'])  # Autenticação com token
        self.is_alive = True
        print(f"Conexão ativa. Tipo de conta: {self.account_type.upper()}")

    async def send(self, request):  # Renomeado para send
        return await self.api.send(request)