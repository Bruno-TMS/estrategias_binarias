import yaml
import os

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '../configs/config.yaml')
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

config = load_config()
API_TOKEN = "5lQ6GcWHV5cuHLc"  # Usando o token do secrets.csv
SYMBOL = config['symbol']
INITIAL_STAKE = config['stake']
DURATION = 0.25  # Ajustado para 15 segundos (0.25 minutos)