import asyncio
import tkinter as tk
from deriv.modulo_grafico import GraficoGUI
import nest_asyncio
from deriv.connection import Connection
from deriv.autobots import DerivedBot  # Importação já corrigida
import time

async def test_connection(conn):
    print("Iniciando testes de conexão...")
    start_time = time.time()
    start_datetime = time.strftime("%Y-%m-%d %H:%M:%S")
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
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()
    closing_task = None

    if await test_connection(conn):
        initial_bot = DerivedBot.create_robot(conn)
        root = tk.Tk()
        app = GraficoGUI(root, initial_bot, loop)  # Passando o loop para a GUI
        root.protocol("WM_DELETE_WINDOW", lambda: loop.create_task(app.on_closing(conn, shutdown_event)))
        nest_asyncio.apply()
        try:
            while app.running:
                root.update()
                await asyncio.sleep(0.01)
        except tk.TclError:
            pass
        finally:
            if closing_task:
                await asyncio.wait([closing_task])  # Aguarda a tarefa on_closing terminar
            pending = asyncio.all_tasks(loop) - {asyncio.current_task(loop)}
            if pending:
                loop.run_until_complete(asyncio.gather(*pending))  # Aguarda todas as tarefas pendentes
            await conn.disconnect()
            print("Encerrando o loop asyncio...")
            loop.close()
    else:
        print("Encerrando programa devido a falha na conexão.")

if __name__ == "__main__":
    asyncio.run(main())