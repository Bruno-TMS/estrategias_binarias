import tkinter as tk
from tkinter import ttk
from deriv.autobots import DerivedBot
import asyncio

class GraficoGUI:
    def __init__(self, root, conn):
        self.root = root
        self.conn = conn
        self.root.title("estratégias_binárias")
        self.running = True
        self.bot = None
        self.loop = asyncio.get_event_loop()

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

        self.contract_type_label = tk.Label(root, text="Tipo de Contrato:")
        self.contract_type_label.pack()
        self.contract_type_var = tk.StringVar(value="rise")
        self.contract_type_menu = ttk.OptionMenu(root, self.contract_type_var, "rise", "rise", "fall")
        self.contract_type_menu.pack()

        self.buy_button = tk.Button(root, text="Comprar", command=self.buy)
        self.buy_button.pack(pady=10)

    def update_balance(self, balance):
        self.label.config(text=f"Saldo: ${balance:.2f}")

    async def buy(self):
        print("Botão Comprar clicado! Tipo de contrato: {}, Stake: {}, Duração: {} minutos".format(
            self.contract_type_var.get(), self.stake_entry.get(), self.duration_entry.get()))
        stake = float(self.stake_entry.get())
        duration = float(self.duration_entry.get())
        contract_type = self.contract_type_var.get()

        self.bot = DerivedBot(self.conn, stake=stake, duration=duration, trade_type="higher_lower", contract_type=contract_type)
        await self.bot.run()

    def on_closing(self):
        self.running = False
        if self.bot:
            asyncio.run_coroutine_threadsafe(self.bot.stop(), self.loop)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    conn = Connection()
    app = GraficoGUI(root, conn)
    root.mainloop()