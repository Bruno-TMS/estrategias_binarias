import asyncio
import tkinter as tk
from deriv.connect import Connection
from deriv.autobots import DerivedBot

class GraficoGUI:
    def __init__(self, root):
        print("Iniciando a interface gráfica...")
        self.root = root
        self.root.title("Robô Deriv")
        self.conn = Connection()
        self.account_type = self.conn.account_type
        self.bot = DerivedBot(symbol="volatility_10", stake=1.0, duration=5, trade_type="higher_lower", contract_type="rise")
        self.running = True

        # Label para tipo de conta
        self.account_label = tk.Label(root, text=f"Conta: {self.account_type.upper()}", font=("Arial", 12))
        self.account_label.pack(pady=5)

        # Label para saldo
        self.balance_label = tk.Label(root, text="Saldo: $0.00", font=("Arial", 14))
        self.balance_label.pack(pady=10)

        # Label para lucro/perda
        self.profit_label = tk.Label(root, text="Lucro/Perda: $0.00", font=("Arial", 14))
        self.profit_label.pack(pady=10)

        # Botão de compra
        self.buy_button = tk.Button(root, text="Comprar CALL", command=self.start_buy, font=("Arial", 12))
        self.buy_button.pack(pady=10)

        print("Iniciando conexão com a API...")
        asyncio.create_task(self.connect())

    async def connect(self):
        try:
            await self.conn.connect()
            await self.update_balance()
        except Exception as e:
            print(f"Erro ao conectar: {e}")

    async def update_balance(self):
        balance = await self.conn.send_request({"balance": 1})
        self.balance_label.config(text=f"Saldo: ${balance['balance']['balance']:.2f}")

    def start_buy(self):
        print("Botão Comprar CALL clicado!")
        asyncio.create_task(self.bot.run())

    def on_closing(self):
        print("Fechando a janela...")
        self.running = False
        self.root.destroy()