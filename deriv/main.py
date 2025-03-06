import asyncio
import tkinter as tk
from deriv.modulo_grafico import GraficoGUI
import nest_asyncio
from deriv.connection import Connection
import datetime
import time

async def test_connection(conn):
    print("Iniciando testes de conexão...")
    start_time = time.time()
    start_datetime = datetime.datetime.now()
    print(f"Horário inicial da conexão: {start_datetime}")

    try:
        await conn.connect()
        balance_response = await conn.send({"balance": 1})
        if 'balance' in balance_response:
            balance_value = balance_response['balance'].get('balance', 0.0)
            print(f"Status: Saldo disponível: ${balance_value:.2f}")
        else:
            raise ValueError("Erro: Resposta do saldo não contém 'balance'")
        end_time = time.time()
        total_time = end_time - start_time
        print(f"Conexão ok! Tempo total de conexão: {total_time:.2f} segundos")
        return True
    except Exception as e:
        print(f"Falha na conexão: {e}")
        return False

async def main():
    conn = Connection()

    if await test_connection(conn):
        root = tk.Tk()
        app = GraficoGUI(root, conn)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        nest_asyncio.apply()
        try:
            while app.running:
                root.update()
                await asyncio.sleep(0.01)
        except tk.TclError:
            pass
    else:
        print("Encerrando programa devido a falha na conexão.")

if __name__ == "__main__":
    asyncio.run(main())