import tkinter as tk
from tkinter import ttk
from deriv.autobots import DerivedBot
import asyncio

class GraficoGUI:
    def __init__(self, root, initial_bot, loop):
        self.root = root
        self.conn = initial_bot.conn
        self.root.title("estratégias_binárias")
        self.running = True
        self.bot = initial_bot
        self.loop = loop  # Recebendo o loop da main

        self.label = tk.Label(root, text="Saldo: $0.00")
        self.label.pack(pady=10)

        self.stake_label = tk.Label(root, text="Stake ($):")
        self.stake_label.pack()
        self.stake_entry = tk.Entry(root)
        self.stake_entry.insert(0, "1.0")
        self.stake_entry.pack()

        self.duration_label = tk.Label(root, text="Duração (minutos):")
        self.duration_label.pack()
        self.duration_entry = tk.Entry(root)
        self.duration_entry.insert(0, "0.25")
        self.duration_entry.pack()

        self.contract_type_label = tk.Label(root, text="Tipo de Contrato (call/put):")
        self.contract_type_label.pack()
        self.contract_type_var = tk.StringVar(value="call")
        self.contract_type_menu = ttk.OptionMenu(root, self.contract_type_var, "call", "call", "put")
        self.contract_type_menu.pack()

        self.buy_button = tk.Button(root, text="Comprar", command=self.buy)
        self.buy_button.pack(pady=10)

    def update_balance(self, balance):
        self.label.config(text=f"Saldo: ${balance:.2f}")

    def buy(self):
        print("Botão Comprar clicado! Tipo de contrato: {}, Stake: {}, Duração: {} minutos".format(
            self.contract_type_var.get(), self.stake_entry.get(), self.duration_entry.get()))
        stake = self.stake_entry.get()
        duration = self.duration_entry.get()
        contract_type = "rise" if self.contract_type_var.get() == "call" else "fall"

        self.bot.set_contract_parameters(stake, duration, contract_type)
        # Inicia a execução assíncrona como uma tarefa, evitando bloqueio
        self.loop.create_task(self.bot.run())

    async def on_closing(self, conn, shutdown_event):
        self.running = False
        if self.bot:
            await self.bot.stop()
        print("Fechando a janela...")
        await conn.disconnect()
        shutdown_event.set()