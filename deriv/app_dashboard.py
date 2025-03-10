from csv import DictReader as dtr
from pathlib import Path

KV_FILE = Path('deriv/secrets.csv')
"""arquivo csv com as chaves de acesso
    app_name,app_id,token_name,token
    app_name: nome do app
    app_id: id do app
    token_name: nome do token
    token: token de acesso
"""

class AppDashboard:
    
    _instance = None
    
    def __new__(cls, app_name, token_name):
        
        if not cls._instance:
            apid = None
            tk = None
            
            with open(KV_FILE, 'r') as csv_file:
                csv_reader = dtr(csv_file)
                
                for row in csv_reader:
                    if row['app_name'] == app_name:
                        apid = row['app_id']
                    
                    if row['token_name'] == token_name:
                        tk = row['token']
                
            if not apid and tk:
                raise ValueError("App ou token inválidos.")
            
            cls._instance = super().__new__(cls)
            cls._instance._app_id = apid
            cls._instance._token = tk
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
    
    @app_name.setter
    def app_name(self, value):
        if AppDashboard._apps.get(value):
            self._app_name = value
            self._app_id = AppDashboard._apps.get(value)
        
        else:  
            raise ValueError("App inválido.")
    
    
    @property
    def token_name(self):
        return self._token_name
    
    @token_name.setter
    def token_name(self, value):
        if AppDashboard._tokens.get(value):
            self._token_name = value
            self._token = AppDashboard._tokens.get(value)
        
        else:
            raise ValueError("Token inválido.")
    
    
    @classmethod
    def get_key_names(cls):
        kns = {}
        
        with open(KV_FILE, 'r') as csv_file:
            csv_reader = dtr(csv_file)
            
            for row in csv_reader:
                kns.setdefault(row['key'], []).append(row['name'])
                
        return kns
   
   

if __name__ == '__main__':
    print(f'Path do arquivo de chaves: {KV_FILE}')
    print(f'Chaves disponíveis: {AppDashboard.get_key_names()}')
    print()