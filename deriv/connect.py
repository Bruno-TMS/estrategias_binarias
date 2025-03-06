import csv
import os
from deriv_api import DerivAPI

class Connection:
    def __init__(self):
        self.secrets = self.load_secrets()
        self.api = DerivAPI(app_id=self.secrets['app_id'])
        self.is_alive = False
        self.account_type = self.secrets['account_type']

    def load_secrets(self):
        secrets_path = os.path.join(os.path.dirname(__file__), '../configs/secrets.csv')
        secrets = {}
        with open(secrets_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=['key', 'value'])
            next(reader)  # Pula o cabeçalho se houver
            for row in reader:
                secrets[row['key']] = row['value']
        return secrets

    async def connect(self):
        await self.api.authorize(self.secrets['api_token'])
        self.is_alive = True
        print(f"Conexão ativa. Tipo de conta: {self.account_type.upper()}")

    async def send_request(self, request):
        return await self.api.send_request(request)