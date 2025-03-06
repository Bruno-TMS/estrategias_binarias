import asyncio
import tkinter as tk
from deriv.connect import Connection
from deriv.autobots import DerivedBot
from deriv.config import DURATION

class GraficoGUI:
    def __init__(self, root):
        print("Iniciando a interface gráfica...")
        self.root = root
        self.root.title("Robô Deriv")
        self.conn = Connection()
        self.account_type = self.conn.account_type
        self.running = True
        self.tasks = []  # Lista para rastrear tarefas assíncronas

        # Variáveis de controle
        self.contract_type = tk.StringVar(value="rise")  # Padrão para CALL
        self.stake = tk.DoubleVar(value=1.0)  # Stake inicial
        self.duration = tk.DoubleVar(value=DURATION)  # Duração inicial

        # Label para tipo de conta
        self.account_label = tk.Label(root, text=f"Conta: {self.account_type.upper()}", font=("Arial", 12))
        self.account_label.pack(pady=5)

        # Label para saldo
        self.balance_label = tk.Label(root, text="Saldo: $0.00", font=("Arial", 14))
        self.balance_label.pack(pady=10)

        # Label para lucro/perda
        self.profit_label = tk.Label(root, text="Lucro/Perda: $0.00", font=("Arial", 14))
        self.profit_label.pack(pady=10)

        # Menu de seleção de contrato
        contract_options = ["rise", "fall"]  # CALL e PUT
        self.contract_menu = tk.OptionMenu(root, self.contract_type, *contract_options)
        self.contract_menu.pack(pady=5)

        # Campo para stake
        tk.Label(root, text="Stake ($):", font=("Arial", 10)).pack(pady=5)
        tk.Entry(root, textvariable=self.stake, font=("Arial", 10)).pack(pady=5)

        # Campo para duration
        tk.Label(root, text="Duração (minutos):", font=("Arial", 10)).pack(pady=5)
        tk.Entry(root, textvariable=self.duration, font=("Arial", 10)).pack(pady=5)

        # Botão de compra (inicialmente desabilitado)
        self.buy_button = tk.Button(root, text="Comprar", command=self.start_buy, font=("Arial", 12), state=tk.DISABLED)
        self.buy_button.pack(pady=10)

        print("Iniciando conexão com a API...")
        self.tasks.append(asyncio.create_task(self.connect()))

    async def connect(self):
        try:
            await self.connect_to_api()
            await self.update_balance()
            # Habilita o botão apenas após a conexão e saldo
            self.buy_button.config(state=tk.NORMAL)
        except Exception as e:
            print(f"Erro ao conectar: {e}")

    async def connect_to_api(self):
        await self.conn.connect()

    async def update_balance(self):
        try:
            balance_response = await self.conn.send({"balance": 1})
            print(f"Resposta do saldo: {balance_response}")
            if 'balance' in balance_response:
                balance_value = balance_response['balance'].get('balance', 0.0)
                self.balance_label.config(text=f"Saldo: ${balance_value:.2f}")
                print(f"Saldo atualizado na interface: ${balance_value:.2f}")
            else:
                print("Erro: Resposta não contém 'balance'")
        except Exception as e:
            print(f"Erro ao atualizar saldo: {e}")

    def start_buy(self):
        print(f"Botão Comprar clicado! Tipo de contrato: {self.contract_type.get()}, Stake: ${self.stake.get()}, Duração: {self.duration.get()} minutos")
        self.buy_button.config(state=tk.DISABLED)  # Desabilita o botão após o clique
        self.bot = DerivedBot(symbol="volatility_10", stake=self.stake.get(), duration=self.duration.get(), trade_type="higher_lower", contract_type=self.contract_type.get())
        self.tasks.append(asyncio.create_task(self.bot.run()))

    def on_closing(self):
        print("Fechando a janela...")
        # Cancela todas as tarefas assíncronas
        for task in self.tasks:
            if not task.done():
                task.cancel()
        self.running = False
        self.root.destroy()