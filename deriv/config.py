import csv

# Lê os dados sensíveis do secrets.csv
with open('secrets.csv', mode='r') as file:
    reader = csv.DictReader(file)
    secrets = next(reader)  # Pega a primeira (e única) linha de dados

# Configurações gerais
APP_ID = "12345"  # Substitua pelo seu app_id واقعی
DEMO_ACCOUNT_ID = secrets['demoaccountid']  # Ex.: "VRTC1234567"
API_TOKEN = secrets['demoaccounttoken']     # Ex.: "a1-xyz123abc456def789"
SYMBOL = "R_10"                             # Índice sintético para trades
INITIAL_STAKE = 0.35                        # Stake inicial em USD
MAX_STAKE = 10.0                            # Stake máximo para martingale
DURATION = 300                              # Duração do contrato em segundos (5 min)
MAX_MARTINGALE_STEPS = 4                    # Máximo de etapas de martingale
PROFIT_GOAL = 20.0                          # Meta de lucro diário em USD
LOSS_LIMIT = -10.0                          # Limite de perdas diário em USD
