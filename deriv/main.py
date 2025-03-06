import asyncio
import tkinter as tk
from deriv.modulo_grafico import GraficoGUI
import nest_asyncio
from deriv.connect import Connection
import datetime
import time

async def test_connection():
    print("Iniciando testes de conexão...")
    start_time = time.time()
    start_datetime = datetime.datetime.now()
    print(f"Horário inicial da conexão: {start_datetime}")

    conn = Connection()
    try:
        # Teste de conexão
        await conn.connect()

        # Teste de status (obter saldo)
        balance_response = await conn.send({"balance": 1})
        if 'balance' in balance_response:
            balance_value = balance_response['balance'].get('balance', 0.0)
            print(f"Status: Saldo disponível: ${balance_value:.2f}")
        else:
            raise ValueError("Erro: Resposta do saldo não contém 'balance'")

        # Calcula o tempo total de conexão
        end_time = time.time()
        total_time = end_time - start_time
        print(f"Conexão ok! Tempo total de conexão: {total_time:.2f} segundos")
        return True
    except Exception as e:
        print(f"Falha na conexão: {e}")
        return False

async def main():
    # Executa os testes de conexão
    if await test_connection():
        # Abre a interface gráfica apenas se a conexão for bem-sucedida
        root = tk.Tk()
        app = GraficoGUI(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)

        # Permitir aninhamento de loops asyncio
        nest_asyncio.apply()

        # Manter o loop Tkinter ativo
        try:
            while app.running:
                root.update()
                await asyncio.sleep(0.01)
        except tk.TclError:
            # Ocorre quando a janela é fechada
            pass
    else:
        print("Encerrando programa devido a falha na conexão.")

if __name__ == "__main__":
    asyncio.run(main())