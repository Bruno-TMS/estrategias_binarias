import os
import asyncio
from deriv_api import DerivAPI

class Conexao:
    def __init__(self):
        self._app_id = os.getenv('DERIV_APP_ID')
        self._token_id = os.getenv('DERIV_TOKEN')
    
    async def conectar(self):
        api = DerivAPI(app_id=self._app_id)
        response = await api.ping({'ping': 1})
        if response:
            authorize = await api.authorize(self._token_id)
            print(authorize)

async def main():
    conn = Conexao()
    await conn.conectar()

if __name__ == '__main__':
    
    asyncio.run(main())