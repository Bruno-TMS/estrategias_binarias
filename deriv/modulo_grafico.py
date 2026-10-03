"""Módulo Gráfico e Interface Visual do Deriv Quantum Trading Bot.

Migrado para arquitetura gráfica moderna reativa com Flet (Python puro).
Ao ser executado via terminal ('python deriv/modulo_grafico.py'), inicializa
a aplicação Flet completa com autenticação WebSocket reativa e monitoramento em tempo real.
"""

import logging
import sys
from typing import Any

from ui_app import DerivApiClient, format_currency, main, start_app

logger = logging.getLogger("deriv.modulo_grafico")


class GraficoGUI:
    """Classe de compatibilidade para código legado (deriv/main.py).

    A aplicação principal agora opera via Flet através de ui_app.start_app().
    """

    def __init__(self, root: Any = None, initial_bot: Any = None, loop: Any = None) -> None:
        self.root = root
        self.conn = getattr(initial_bot, "conn", None) if initial_bot else None
        self.bot = initial_bot
        self.loop = loop
        self.running = True

    def update_balance(self, balance: float) -> None:
        """Compatibilidade para atualização de saldo."""
        logger.info(f"[GraficoGUI] Saldo atualizado: ${balance:.2f}")

    def buy(self) -> None:
        """Compatibilidade para disparo de ordem."""
        if self.bot and self.loop:
            self.loop.create_task(self.bot.run())

    async def on_closing(self, conn: Any = None, shutdown_event: Any = None) -> None:
        """Compatibilidade para encerramento de conexão."""
        self.running = False
        try:
            from api.deps import deriv_service
            await deriv_service.unsubscribe_all_ticks()
        except Exception:
            pass
        if self.bot and hasattr(self.bot, "stop"):
            await self.bot.stop()
        if conn and hasattr(conn, "disconnect"):
            await conn.disconnect()
        elif self.conn and hasattr(self.conn, "disconnect"):
            await self.conn.disconnect()
        if shutdown_event and hasattr(shutdown_event, "set"):
            shutdown_event.set()


__all__ = ["GraficoGUI", "main", "start_app", "DerivApiClient", "format_currency"]

if __name__ == "__main__":
    start_app()