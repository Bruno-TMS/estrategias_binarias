import asyncio
import tkinter as tk
from deriv.modulo_grafico import GraficoGUI

async def main():
    root = tk.Tk()
    app = GraficoGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    while app.running:
        root.update()
        await asyncio.sleep(0.01)

if __name__ == "__main__":
    asyncio.run(main())