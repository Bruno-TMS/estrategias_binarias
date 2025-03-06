import yaml
import os

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '../configs/config.yaml')
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

config = load_config()
APP_ID = None  # Carregado de secrets.csv via connect.py
API_TOKEN = None  # Carregado de secrets.csv via connect.py
SYMBOL = config['symbol']
INITIAL_STAKE = config['stake']
DURATION = config['duration']