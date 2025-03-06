import asyncio
import tkinter as tk
from deriv_api import DerivAPI
from config import APP_ID, API_TOKEN, SYMBOL, INITIAL_STAKE

class DerivGUI:
    def __init__(self, root):
        print("Iniciando a interface gráfica...")
        self.root = root
        self.root.title("Robô Deriv")
        self.api = None
        self.running = True

        self.balance_label = tk.Label(root, text="Saldo: $0.00", font=("Arial", 14))
        self.balance_label.pack(pady=10)

        self.profit_label = tk.Label(root, text="Lucro/Perda: $0.00", font=("Arial", 14))
        self.profit_label.pack(pady=10)

        self.buy_button = tk.Button(root, text="Comprar CALL", command=self.start_buy, font=("Arial", 12))
        self.buy_button.pack(pady=10)

        print("Iniciando conexão com a API...")
        asyncio.create_task(self.connect())

    async def connect(self):
        try:
            self.api = DerivAPI(app_id=APP_ID)
            auth_response = await self.api.authorize(API_TOKEN)
            print("Conectado à Deriv API:", auth_response)
            await self.update_balance()
        except Exception as e:
            print(f"Erro ao conectar: {e}")

    async def disconnect(self):
        if self.api:
            await self.api.disconnect()
            print("Desconectado da Deriv API.")

    async def update_balance(self):
        if self.api:
            balance = await self.api.balance()
            print("Atualizando saldo:", balance)
            self.balance_label.config(text=f"Saldo: ${balance['balance']['balance']:.2f}")

    async def buy_contract(self):
        if not self.api:
            print("API não conectada!")
            return
        trade = {
            "buy": 1,
            "price": 1.0,
            "parameters": {
                "contract_type": "CALL",
                "symbol": SYMBOL,
                "duration": 5,
                "duration_unit": "m",
                "currency": "USD",
                "amount": INITIAL_STAKE,
                "basis": "stake"
            }
        }
        print("Requisição enviada:", trade)
        response = await self.api.buy(trade)
        contract_id = response["buy"]["contract_id"]
        print(f"Contrato comprado, ID: {contract_id}")

        while True:
            details = await self.api.proposal_open_contract({"contract_id": contract_id})
            print("Detalhes do contrato:", details)
            if details.get("is_sold", 0) == 1:
                profit = details.get("profit", 0)
                self.profit_label.config(text=f"Lucro/Perda: ${profit:.2f}")
                await self.update_balance()
                break
            await asyncio.sleep(1)

    def start_buy(self):
        print("Botão Comprar CALL clicado!")
        asyncio.create_task(self.buy_contract())

    def on_closing(self):
        print("Fechando a janela...")
        self.running = False
        asyncio.create_task(self.disconnect())
        self.root.destroy()

async def main():
    print("Iniciando o loop principal...")
    root = tk.Tk()
    app = DerivGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    while app.running:
        root.update()
        await asyncio.sleep(0.01)

if __name__ == "__main__":
    asyncio.run(main())