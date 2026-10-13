"""Interface gráfica moderna com Flet para o Deriv Quantum Trading Bot.

Oferece controle e monitoramento completo em 3 painéis:
  1. Dashboard Geral: Saldo da conta, status da conexão WebSocket e ações rápidas.
  2. Catálogo e Cotações: Consulta de ativos sintéticos, cotações ao vivo e durações de contratos.
  3. Bot Autônomo (Auto-Run): Calibração retrospectiva em grid de 100 variações com IA,
     diagnóstico de regime de mercado e execução segura com travas de risco.
"""

import asyncio
from datetime import datetime
import logging
import os
import sys
from typing import Any

import flet as ft
import httpx

try:
    from deriv.symbol import ActiveSymbol, Asset
except ImportError:
    from symbol import ActiveSymbol, Asset

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ui_app")

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


def format_currency(amount: float, currency: str = "USD") -> str:
    """Formata valor financeiro no padrão com separadores (ex: USD 10.001,66)."""
    formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{currency} {formatted}"


class DerivApiClient:
    """Cliente híbrido resiliente:

    Conecta à API FastAPI local via HTTP ou, caso a API esteja offline,
    utiliza diretamente os serviços internos assíncronos (DerivService, MemoryService).
    """

    def __init__(self, base_url: str = API_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self.mode = "api"  # "api" ou "direct"

    async def authorize(self) -> dict[str, Any]:
        """Executa ou verifica a autenticação da conta na Deriv."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/deriv/auth/verify")
                if resp.status_code == 200:
                    self.mode = "api"
                    return resp.json().get("data", {})
        except Exception:
            pass

        # Fallback direto
        self.mode = "direct"
        from api.deps import deriv_service

        return await deriv_service.authorize()

    async def get_balance(self) -> dict[str, Any]:
        """Consulta o saldo da conta."""
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"{self.base_url}/deriv/balance")
                if resp.status_code == 200:
                    self.mode = "api"
                    return resp.json().get("data", {})
        except Exception:
            pass

        # Fallback direto
        self.mode = "direct"
        from api.deps import deriv_service

        return await deriv_service.get_balance()

    async def get_symbols(self, synthetic_only: bool = True) -> list[dict[str, Any]]:
        """Consulta lista de ativos sintéticos disponíveis."""
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(
                    f"{self.base_url}/deriv/symbols",
                    params={"synthetic_only": synthetic_only},
                )
                if resp.status_code == 200:
                    self.mode = "api"
                    return resp.json().get("data", [])
        except Exception:
            pass

        self.mode = "direct"
        from api.deps import deriv_service

        return await deriv_service.get_symbols(synthetic_only=synthetic_only)

    async def get_latest_tick(self, symbol: str) -> dict[str, Any]:
        """Obtém a cotação mais recente de um ativo."""
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"{self.base_url}/deriv/ticks/{symbol}")
                if resp.status_code == 200:
                    self.mode = "api"
                    return resp.json().get("data", {})
        except Exception:
            pass

        self.mode = "direct"
        from api.deps import deriv_service

        return await deriv_service.get_latest_tick(symbol=symbol)

    async def get_contracts(self, symbol: str) -> list[dict[str, Any]]:
        """Consulta contratos e durações permitidas para o ativo."""
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"{self.base_url}/deriv/contracts/{symbol}")
                if resp.status_code == 200:
                    self.mode = "api"
                    return resp.json().get("data", [])
        except Exception:
            pass

        self.mode = "direct"
        from api.deps import deriv_service

        return await deriv_service.get_contracts_for(symbol=symbol)

    async def sync_symbols(self) -> int:
        """Força a sincronização do cache de símbolos."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{self.base_url}/deriv/symbols/sync")
                if resp.status_code == 200:
                    self.mode = "api"
                    return resp.json().get("total", 0)
        except Exception:
            pass

        self.mode = "direct"
        from api.deps import deriv_service

        return await deriv_service.sync_symbols()

    async def auto_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Executa o ciclo completo de calibração retrospectiva e disparo."""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.base_url}/deriv/bot/auto-run",
                    json=payload,
                )
                if resp.status_code == 200:
                    self.mode = "api"
                    return resp.json()
                else:
                    try:
                        err_data = resp.json()
                        detail = err_data.get("detail", resp.text)
                    except Exception:
                        detail = resp.text
                    raise RuntimeError(f"Erro {resp.status_code}: {detail}")
        except httpx.ConnectError:
            pass
        except httpx.ConnectTimeout:
            pass

        # Fallback direto
        self.mode = "direct"
        from api.deps import deriv_service, memory_service
        from api.routes.deriv import AutoRunRequest, auto_run_bot

        req = AutoRunRequest(**payload)
        return await auto_run_bot(
            payload=req,
            service=deriv_service,
            memory_service=memory_service,
        )

    async def subscribe_ticks(
        self, symbol: str, callback: Any
    ) -> Any:
        """Subscreve ao stream WebSocket de ticks em tempo real."""
        from api.deps import deriv_service

        return await deriv_service.subscribe_ticks(symbol=symbol, callback=callback)

    async def unsubscribe_ticks(self, symbol: str) -> None:
        """Cancela a subscrição de ticks do ativo especificado via forget."""
        from api.deps import deriv_service

        await deriv_service.unsubscribe_ticks(symbol=symbol)

    async def unsubscribe_all_ticks(self) -> None:
        """Cancela todas as subscrições ativas de ticks."""
        from api.deps import deriv_service

        await deriv_service.unsubscribe_all_ticks()

    async def get_server_time(self) -> dict[str, Any]:
        """Consulta o relógio oficial do servidor Deriv via API REST ou diretamente."""
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"{self.base_url}/deriv/time")
                if resp.status_code == 200:
                    self.mode = "api"
                    return resp.json().get("data", {})
        except Exception:
            pass

        self.mode = "direct"
        from services.time_operations import time_operations

        return await time_operations.get_server_time()


async def main(page: ft.Page) -> None:
    """Função principal da interface gráfica Flet."""
    page.title = "Deriv Quantum Trading Bot"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.CYAN)
    page.padding = 0

    api_client = DerivApiClient()

    # Estado compartilhado da aplicação
    state: dict[str, Any] = {
        "balance": 0.0,
        "currency": "USD",
        "loginid": "--",
        "fullname": "--",
        "is_virtual": True,
        "account_type": "Conta Demo",
        "is_authenticated": False,
        "ws_connected": False,
        "selected_symbol": "1HZ100V",
        "symbols_list": [],
        "last_quote": 0.0,
        "live_stream_active": True,
        "recent_ticks": [],
        "tick_diff": 0.0,
        "tick_diff_pct": 0.0,
        "polling_active": False,
        "session_cycles": 0,
        "session_profit": 0.0,
        "session_wins": 0,
        "session_losses": 0,
        "server_time_utc": "--:--:-- UTC",
        "server_time_full_utc": "--",
        "tempo_logado_str": "--",
        "tempo_atualizacao": 60.0,
    }

    # Notificações Toast / SnackBar
    def notify(msg: str, is_error: bool = False) -> None:
        snack = ft.SnackBar(
            content=ft.Text(msg, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.RED_800 if is_error else ft.Colors.GREEN_800,
            open=True,
        )
        page.overlay.append(snack)
        page.update()

    # Log de atividades
    log_list_view = ft.ListView(
        expand=True,
        spacing=4,
        auto_scroll=True,
    )

    def log_event(message: str, level: str = "INFO") -> None:
        now_str = datetime.now().strftime("%H:%M:%S")
        color_map = {
            "INFO": ft.Colors.CYAN_200,
            "SUCCESS": ft.Colors.GREEN_300,
            "WARNING": ft.Colors.AMBER_300,
            "ERROR": ft.Colors.RED_300,
        }
        text_color = color_map.get(level, ft.Colors.WHITE)
        entry = ft.Text(
            f"[{now_str}] [{level}] {message}",
            color=text_color,
            size=12,
            font_family="monospace",
        )
        log_list_view.controls.append(entry)
        page.update()

    # --- Elementos da Barra Superior (AppBar) ---
    appbar_ws_icon = ft.Icon(
        ft.Icons.WIFI,
        size=18,
        color="#FF5252",
    )
    appbar_ws_status = ft.Container(
        content=appbar_ws_icon,
        tooltip="WebSocket Deriv: Desconectado / Sem Sessão",
        bgcolor="#1E1014",
        border=ft.Border.all(1, "#FF5252"),
        border_radius=8,
        height=36,
        padding=ft.padding.Padding(10, 0, 10, 0),
        alignment=ft.Alignment.CENTER,
        animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
    )
    appbar_clock_icon = ft.Icon(ft.Icons.SCHEDULE_ROUNDED, size=16, color=ft.Colors.CYAN_200)
    appbar_clock_text = ft.Text("--/--/-- --:--:--", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE)
    appbar_clock_chip = ft.Container(
        content=ft.Row(
            [appbar_clock_icon, appbar_clock_text],
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor="#121C24",
        border=ft.Border.all(1, ft.Colors.CYAN_700),
        border_radius=8,
        height=36,
        padding=ft.padding.Padding(10, 0, 10, 0),
        alignment=ft.Alignment.CENTER,
        tooltip="Relógio Oficial Deriv (UTC) [DD/MM/AA HH:MM:SS]",
    )

    appbar_session_icon = ft.Icon(ft.Icons.TIMER_ROUNDED, size=16, color=ft.Colors.AMBER_200)
    appbar_session_text = ft.Text("Sessão: --", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    appbar_session_chip = ft.Container(
        content=ft.Row(
            [appbar_session_icon, appbar_session_text],
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor="#1C1814",
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=8,
        height=36,
        padding=ft.padding.Padding(10, 0, 10, 0),
        alignment=ft.Alignment.CENTER,
        tooltip="Tempo Logado na Sessão Ativa [0d 0h 0m]",
    )

    appbar_account_icon = ft.Icon(ft.Icons.ACCOUNT_CIRCLE_ROUNDED, size=16, color=ft.Colors.WHITE)
    appbar_account_text = ft.Text("Conta: Aguardando", size=11, color=ft.Colors.WHITE)
    appbar_account_chip = ft.Container(
        content=ft.Row(
            [appbar_account_icon, appbar_account_text],
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor="#1C1814",
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=8,
        height=36,
        padding=ft.padding.Padding(10, 0, 10, 0),
        alignment=ft.Alignment.CENTER,
    )

    appbar_balance_icon = ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, size=16, color=ft.Colors.GREEN_300)
    appbar_balance_text = ft.Text(f"Saldo: {format_currency(0.0)}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    appbar_balance_chip = ft.Container(
        content=ft.Row(
            [appbar_balance_icon, appbar_balance_text],
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor="#0F2318",
        border=ft.Border.all(1, ft.Colors.GREEN_700),
        border_radius=8,
        height=36,
        padding=ft.padding.Padding(10, 0, 10, 0),
        alignment=ft.Alignment.CENTER,
    )

    def update_header_status() -> None:
        if state["ws_connected"]:
            appbar_ws_icon.name = ft.Icons.WIFI
            appbar_ws_icon.color = "#00E676"
            appbar_ws_status.bgcolor = "#0B2014"
            appbar_ws_status.border = ft.Border.all(1, "#00E676")
            appbar_ws_status.tooltip = "WebSocket Deriv: Conectado e Ativo"
        else:
            appbar_ws_icon.name = ft.Icons.WIFI
            appbar_ws_icon.color = "#FF5252"
            appbar_ws_status.bgcolor = "#1E1014"
            appbar_ws_status.border = ft.Border.all(1, "#FF5252")
            appbar_ws_status.tooltip = "WebSocket Deriv: Desconectado / Sem Sessão"

        if state["is_authenticated"]:
            tag = "Demo" if state["is_virtual"] else "Real"
            appbar_account_text.value = f"{state['loginid']} ({tag})"
            appbar_account_text.weight = ft.FontWeight.BOLD
            appbar_account_text.color = ft.Colors.WHITE
            appbar_account_chip.bgcolor = "#0E241F" if state["is_virtual"] else "#2A1D0E"
            appbar_account_chip.border = ft.Border.all(
                1, ft.Colors.TEAL_600 if state["is_virtual"] else ft.Colors.AMBER_600
            )
            appbar_account_icon.name = ft.Icons.VERIFIED_USER_ROUNDED
            appbar_account_icon.color = ft.Colors.TEAL_300 if state["is_virtual"] else ft.Colors.AMBER_300
        else:
            appbar_account_text.value = "Não Autenticado"
            appbar_account_text.weight = ft.FontWeight.NORMAL
            appbar_account_text.color = ft.Colors.WHITE
            appbar_account_chip.bgcolor = "#1C1814"
            appbar_account_chip.border = ft.Border.all(1, ft.Colors.OUTLINE_VARIANT)
            appbar_account_icon.name = ft.Icons.ACCOUNT_CIRCLE_ROUNDED
            appbar_account_icon.color = ft.Colors.WHITE

        bal = state["balance"]
        curr = state["currency"]
        appbar_balance_text.value = f"Saldo: {format_currency(bal, curr)}"
        appbar_balance_text.color = ft.Colors.WHITE

        srv_time = state.get("server_time_utc", "--/--/-- --:--:--")
        appbar_clock_text.value = f"{srv_time}"
        appbar_clock_text.color = ft.Colors.WHITE

        if state.get("is_authenticated", False) and time_operations.is_logged_in:
            appbar_session_chip.bgcolor = "#2A1D0E"
            appbar_session_chip.border = ft.Border.all(1, ft.Colors.AMBER_600)
            appbar_session_text.value = f"Sessão: {state.get('tempo_logado_str', '--')}"
            appbar_session_text.color = ft.Colors.WHITE
            appbar_session_icon.color = ft.Colors.AMBER_300
        else:
            appbar_session_chip.bgcolor = "#1C1814"
            appbar_session_chip.border = ft.Border.all(1, ft.Colors.OUTLINE_VARIANT)
            appbar_session_text.value = "Sessão: --"
            appbar_session_text.color = ft.Colors.WHITE
            appbar_session_icon.color = ft.Colors.AMBER_200

        page.update()

    # =========================================================================
    # VIEW 1: DASHBOARD GERAL
    # =========================================================================

    # Controles da Aba de Ajustes (Settings)
    from services.time_operations import time_operations

    settings_server_time_detail = ft.Text(
        "Relógio Deriv: Aguardando sincronização...",
        size=13,
        color=ft.Colors.GREY_300,
    )
    settings_session_start_detail = ft.Text(
        "Início da Sessão: Não autenticado",
        size=13,
        color=ft.Colors.GREY_300,
    )
    settings_tempo_logado_detail = ft.Text(
        "Duração Acumulada: --",
        size=13,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.AMBER_300,
    )

    def update_time_displays() -> None:
        srv_time = state.get("server_time_utc", "--/--/-- --:--:--")
        srv_full = state.get("server_time_full_utc", "--")
        t_logado = state.get("tempo_logado_str", "0d 0h 0m")

        appbar_clock_text.value = f"{srv_time}"
        appbar_clock_text.color = ft.Colors.WHITE
        settings_server_time_detail.value = f"Relógio Oficial Deriv (UTC): {srv_time}"

        if state.get("is_authenticated") and time_operations.is_logged_in:
            appbar_session_chip.bgcolor = "#2A1D0E"
            appbar_session_chip.border = ft.Border.all(1, ft.Colors.AMBER_600)
            appbar_session_text.value = f"Sessão: {t_logado}"
            appbar_session_text.color = ft.Colors.WHITE
            appbar_session_icon.color = ft.Colors.AMBER_300
            settings_tempo_logado_detail.value = f"Duração Acumulada: {t_logado}"

            if time_operations.inicio_sessao_utc:
                dt_str = time_operations.inicio_sessao_utc.strftime("%d/%m/%y %H:%M:%S")
                settings_session_start_detail.value = f"Início da Sessão: {dt_str} UTC"
        else:
            appbar_session_chip.bgcolor = "#1C1814"
            appbar_session_chip.border = ft.Border.all(1, ft.Colors.OUTLINE_VARIANT)
            appbar_session_text.value = "Sessão: --"
            appbar_session_text.color = ft.Colors.WHITE
            appbar_session_icon.color = ft.Colors.AMBER_200
            settings_session_start_detail.value = "Início da Sessão: Não autenticado"
            settings_tempo_logado_detail.value = "Duração Acumulada: --"

        page.update()

    async def server_time_and_session_loop() -> None:
        """Loop contínuo em background com relógio UTC local nativo em Python (DD/MM/AA HH:MM:SS)."""
        while True:
            try:
                # Relógio UTC Local Nativo em Python (timezone.utc estrito)
                res = time_operations.get_current_utc_time()
                dt_utc = res["datetime_utc"]
                state["server_time_utc"] = dt_utc.strftime("%d/%m/%y %H:%M:%S")
                state["server_time_full_utc"] = res["formatted"]

                if state.get("is_authenticated") and time_operations.is_logged_in:
                    state["tempo_logado_str"] = time_operations.format_tempo_logado()
                else:
                    state["tempo_logado_str"] = "--"

                update_time_displays()
            except Exception as exc:
                logger.debug(f"Exceção no loop temporal: {exc}")

            await asyncio.sleep(1.0)

    # Controles do Monitor de Ticks em Tempo Real (Dashboard)
    dash_live_symbol_chip = ft.Chip(
        label=ft.Text("1HZ100V", weight=ft.FontWeight.BOLD),
        bgcolor=ft.Colors.CYAN_900,
    )
    dash_live_status_badge = ft.Container(
        content=ft.Text("● AO VIVO (WebSocket)", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_200),
        bgcolor=ft.Colors.GREEN_900,
        border_radius=4,
        padding=ft.padding.Padding(6, 2, 6, 2),
    )
    dash_live_price_text = ft.Text(
        "--.----",
        size=28,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.CYAN_300,
    )
    dash_live_diff_icon = ft.Icon(
        ft.Icons.TRENDING_FLAT_ROUNDED,
        color=ft.Colors.GREY_400,
        size=24,
    )
    dash_live_diff_text = ft.Text(
        "+0.0000 (+0.00%)",
        size=12,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.GREY_400,
    )
    dash_live_time_text = ft.Text("Aguardando stream de ticks...", size=11, color=ft.Colors.GREY_400)
    dash_ticks_sparkline_row = ft.Row(
        spacing=3,
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.END,
        height=32,
    )

    def update_recent_ticks_display() -> None:
        ticks = state.get("recent_ticks", [])
        if not ticks:
            return
        min_p = min(ticks)
        max_p = max(ticks)
        span = (max_p - min_p) if (max_p - min_p) > 1e-9 else 1.0

        bars = []
        for i, p in enumerate(ticks):
            h = 6 + int(((p - min_p) / span) * 22)
            if i > 0:
                is_up = p >= ticks[i - 1]
                bar_color = ft.Colors.GREEN_400 if is_up else ft.Colors.RED_400
            else:
                bar_color = ft.Colors.CYAN_400
            bars.append(
                ft.Container(
                    width=6,
                    height=h,
                    bgcolor=bar_color,
                    border_radius=2,
                    tooltip=f"Tick {i+1}: {p:.4f}",
                )
            )
        dash_ticks_sparkline_row.controls = bars

    async def handle_live_tick(tick_data: dict[str, Any]) -> None:
        quote = float(tick_data.get("quote", 0.0))
        epoch = int(tick_data.get("epoch", 0))
        symbol = str(tick_data.get("symbol", state["selected_symbol"]))

        if quote <= 0:
            return

        last = state.get("last_quote", 0.0)
        diff = quote - last if last > 0 else 0.0
        diff_pct = (diff / last * 100.0) if last > 0 else 0.0

        state["last_quote"] = quote
        state["tick_diff"] = diff
        state["tick_diff_pct"] = diff_pct

        recent = state.setdefault("recent_ticks", [])
        recent.append(quote)
        if len(recent) > 20:
            recent.pop(0)

        dash_live_symbol_chip.label = ft.Text(symbol, weight=ft.FontWeight.BOLD)
        dash_live_price_text.value = f"{quote:,.4f}"

        dt_str = datetime.fromtimestamp(epoch).strftime("%H:%M:%S") if epoch else datetime.now().strftime("%H:%M:%S")
        dash_live_time_text.value = f"Último tick às {dt_str}"

        if diff > 0:
            dash_live_price_text.color = ft.Colors.GREEN_400
            dash_live_diff_icon.icon = ft.Icons.TRENDING_UP_ROUNDED
            dash_live_diff_icon.color = ft.Colors.GREEN_400
            dash_live_diff_text.value = f"+{diff:.4f} (+{diff_pct:.2f}%)"
            dash_live_diff_text.color = ft.Colors.GREEN_400
        elif diff < 0:
            dash_live_price_text.color = ft.Colors.RED_400
            dash_live_diff_icon.icon = ft.Icons.TRENDING_DOWN_ROUNDED
            dash_live_diff_icon.color = ft.Colors.RED_400
            dash_live_diff_text.value = f"{diff:.4f} ({diff_pct:.2f}%)"
            dash_live_diff_text.color = ft.Colors.RED_400
        else:
            dash_live_price_text.color = ft.Colors.CYAN_300
            dash_live_diff_icon.icon = ft.Icons.TRENDING_FLAT_ROUNDED
            dash_live_diff_icon.color = ft.Colors.GREY_400
            dash_live_diff_text.value = "+0.0000 (+0.00%)"
            dash_live_diff_text.color = ft.Colors.GREY_400

        update_recent_ticks_display()

        try:
            cur_focused = dropdown_symbol.value if dropdown_symbol.value else state["selected_symbol"]
            if symbol == cur_focused:
                tick_price_display.value = f"{quote:,.4f}"
                tick_price_display.color = dash_live_price_text.color
                tick_diff_icon.icon = dash_live_diff_icon.icon
                tick_diff_icon.color = dash_live_diff_icon.color
                tick_time_text.value = f"Último tick (WebSocket): {dt_str} (Epoch: {epoch})"
                tick_symbol_badge.label = ft.Text(symbol, weight=ft.FontWeight.BOLD)
        except Exception:
            pass

        page.update()

    async def set_active_subscription(new_symbol: str) -> None:
        try:
            await api_client.unsubscribe_all_ticks()
            state["recent_ticks"] = []
            dash_ticks_sparkline_row.controls.clear()
            dash_live_status_badge.content = ft.Text(
                "● CONECTANDO STREAM...",
                size=10,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.AMBER_200,
            )
            dash_live_status_badge.bgcolor = ft.Colors.AMBER_900
            dash_live_symbol_chip.label = ft.Text(new_symbol, weight=ft.FontWeight.BOLD)
            page.update()

            sub_id = await api_client.subscribe_ticks(
                symbol=new_symbol,
                callback=handle_live_tick,
            )
            dash_live_status_badge.content = ft.Text(
                "● AO VIVO (WebSocket)",
                size=10,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.GREEN_200,
            )
            dash_live_status_badge.bgcolor = ft.Colors.GREEN_900
            log_event(
                f"Stream de ticks em tempo real ativo para {new_symbol}.",
                "SUCCESS",
            )
            page.update()
        except Exception as exc:
            dash_live_status_badge.content = ft.Text(
                "● STREAM OFFLINE",
                size=10,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.RED_200,
            )
            dash_live_status_badge.bgcolor = ft.Colors.RED_900
            log_event(f"Falha ao conectar stream de {new_symbol}: {exc}", "WARNING")
            page.update()

    async def action_authenticate(e: Any = None) -> bool:
        log_event("Iniciando autenticação via WebSocket com credenciais do .env...", "INFO")
        try:
            auth_data = await api_client.authorize()
            state["loginid"] = str(auth_data.get("loginid", "--"))
            state["fullname"] = str(auth_data.get("fullname", "--"))
            state["is_virtual"] = bool(auth_data.get("is_virtual", True))
            state["balance"] = float(auth_data.get("balance", state["balance"]))
            state["currency"] = str(auth_data.get("currency", "USD"))
            state["is_authenticated"] = True
            state["ws_connected"] = True

            update_header_status()

            acc_type_label = "Conta Demo" if state["is_virtual"] else "Conta Real"
            log_event(
                f"Autorização confirmada com sucesso: {state['loginid']} ({acc_type_label}) | Saldo: {format_currency(state['balance'], state['currency'])}",
                "SUCCESS",
            )
            notify(f"Autenticado com sucesso: {state['loginid']} ({acc_type_label})")
            return True
        except Exception as exc:
            state["is_authenticated"] = False
            state["ws_connected"] = False
            update_header_status()
            log_event(f"Falha de autenticação junto à Deriv: {exc}", "ERROR")
            notify(f"Erro ao autenticar: {exc}", is_error=True)
            return False

    async def action_fetch_balance(e: Any = None) -> None:
        log_event("Consultando saldo junto à Deriv API...", "INFO")
        try:
            if not state["is_authenticated"]:
                success = await action_authenticate()
                if not success:
                    return

            bal_data = await api_client.get_balance()
            state["balance"] = float(bal_data.get("balance", state["balance"]))
            state["currency"] = str(bal_data.get("currency", "USD"))
            if bal_data.get("loginid"):
                state["loginid"] = str(bal_data.get("loginid"))
            state["ws_connected"] = True

            update_header_status()
            log_event(
                f"Saldo atualizado: {format_currency(state['balance'], state['currency'])} (ID: {state['loginid']})",
                "SUCCESS",
            )
            notify(f"Saldo atualizado: {format_currency(state['balance'], state['currency'])}")
        except Exception as exc:
            state["ws_connected"] = False
            update_header_status()
            log_event(f"Erro ao consultar saldo: {exc}", "ERROR")
            notify(f"Erro ao consultar saldo: {exc}", is_error=True)

    async def action_ping_deriv(e: Any = None) -> None:
        log_event("Enviando requisição de ping à Deriv API...", "INFO")
        try:
            await api_client.get_symbols(synthetic_only=True)
            state["ws_connected"] = True
            update_header_status()
            log_event("Comunicação com Deriv estabelecida com sucesso.", "SUCCESS")
            notify("Deriv WebSocket respondendo normalmente.")
        except Exception as exc:
            state["ws_connected"] = False
            update_header_status()
            log_event(f"Falha de comunicação: {exc}", "ERROR")
            notify(f"Erro ao testar ping: {exc}", is_error=True)

    async def action_sync_cache(e: Any = None) -> None:
        log_event("Iniciando sincronização forçada de símbolos com a Deriv API...", "INFO")
        try:
            total = await api_client.sync_symbols()
            log_event(f"Cache de símbolos atualizado: {total} ativos disponíveis.", "SUCCESS")
            notify(f"{total} ativos sincronizados com sucesso!")
            await load_symbols_into_ui()
        except Exception as exc:
            log_event(f"Falha na sincronização: {exc}", "ERROR")
            notify(f"Erro ao sincronizar símbolos: {exc}", is_error=True)

    def clear_logs(e: Any = None) -> None:
        log_list_view.controls.clear()
        log_event("Console de atividades limpo.", "INFO")

    def build_dashboard_view() -> ft.Control:
        log_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.TERMINAL_ROUNDED, size=20, color=ft.Colors.CYAN_300),
                                    ft.Text("Console de Atividades & Auditoria", size=15, weight=ft.FontWeight.BOLD),
                                ],
                                spacing=8,
                            ),
                            ft.OutlinedButton(
                                "Limpar Console",
                                icon=ft.Icons.DELETE_SWEEP_ROUNDED,
                                on_click=clear_logs,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(
                        content=log_list_view,
                        bgcolor=ft.Colors.BLACK,
                        padding=12,
                        border_radius=8,
                        height=380,
                    ),
                ],
                spacing=10,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=16,
            border_radius=12,
            expand=True,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Column(
                        [
                            ft.Text("Dashboard Geral", size=22, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Visão integrada da conexão com a Deriv, métricas de conta e console de execução.",
                                size=13,
                                color=ft.Colors.GREY_400,
                            ),
                        ],
                        spacing=2,
                    ),
                    log_card,
                ],
                spacing=18,
                expand=True,
            ),
            padding=20,
            expand=True,
        )

    # =========================================================================
    # VIEW 2: CATÁLOGO MULTIATIVO & MULTI-CONTRATO (ActiveSymbol & Asset)
    # =========================================================================
    from deriv.symbol import ActiveSymbol, Asset

    # Estado reativo do Catálogo e Boleta
    catalog_state = {
        "active_market": "synthetic_index",
        "active_modality": "Rise/Fall",
        "duration_value": 5,
        "duration_unit": "t",
        "selected_digit": 5,
        "barrier_offset": "0",
        "entry_stake": 10.0,
        "favorite_symbols": {"1HZ100V", "frxEURUSD", "frxXAUUSD", "cryBTCUSD"},
    }

    # Definição dos 5 Mercados
    MARKET_TABS = [
        {"id": "synthetic_index", "label": "Derivados (Sintéticos)", "market_filter": ["synthetic_index", "synthetic"]},
        {"id": "forex", "label": "Forex", "market_filter": ["forex"]},
        {"id": "indices", "label": "Ações & Índices", "market_filter": ["indices", "stock", "stockindex"]},
        {"id": "commodities", "label": "Matérias-Primas", "market_filter": ["commodities", "commodity"]},
        {"id": "cryptocurrency", "label": "Criptomoedas", "market_filter": ["cryptocurrency", "crypto"]},
    ]

    # Definição dos Grupos e Modalidades (Asset)
    MODALITY_SECTIONS = [
        {
            "group": "Direcional",
            "icon": ft.Icons.SWAP_VERT_ROUNDED,
            "items": [
                {"label": "Rise/Fall", "contract": "CALL/PUT", "has_digit": False, "has_barrier": False},
                {"label": "Touch/No Touch", "contract": "ONETOUCH/NOTOUCH", "has_digit": False, "has_barrier": True},
                {"label": "Higher/Lower", "contract": "HIGHER/LOWER", "has_digit": False, "has_barrier": True},
            ],
        },
        {
            "group": "Crescimento",
            "icon": ft.Icons.ECO_ROUNDED,
            "items": [
                {"label": "Accumulators", "contract": "ACCU", "has_digit": False, "has_barrier": False},
                {"label": "Multipliers", "contract": "MULTUP/MULTDOWN", "has_digit": False, "has_barrier": False},
                {"label": "Turbos", "contract": "TURBOSLONG/SHORT", "has_digit": False, "has_barrier": True},
            ],
        },
        {
            "group": "Dígitos",
            "icon": ft.Icons.DATA_ARRAY_ROUNDED,
            "items": [
                {"label": "Matches/Differs", "contract": "DIGITMATCH/DIFF", "has_digit": True, "has_barrier": False},
                {"label": "Over/Under", "contract": "DIGITOVER/UNDER", "has_digit": True, "has_barrier": False},
                {"label": "Even/Odd", "contract": "DIGITEVEN/ODD", "has_digit": True, "has_barrier": False},
            ],
        },
    ]

    # Controles de Cotação e Resumo
    tick_price_display = ft.Text(
        "--.----",
        size=36,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.CYAN_300,
    )
    tick_diff_icon = ft.Icon(ft.Icons.TRENDING_FLAT_ROUNDED, color=ft.Colors.GREY_400, size=28)
    tick_time_text = ft.Text("Última atualização: --", size=12, color=ft.Colors.GREY_400)
    tick_symbol_badge = ft.Chip(label=ft.Text("1HZ100V", weight=ft.FontWeight.BOLD))
    switch_live_stream = ft.Switch(label="Stream WebSocket em Tempo Real", value=True)

    # Controles da Boleta (Contract Parameter Configurator)
    boleta_trade_type_dropdown = ft.Dropdown(
        label="Trade Type (Tipo de Negociação)",
        options=[
            ft.DropdownOption("Rise/Fall", "Rise/Fall"),
            ft.DropdownOption("Touch/No Touch", "Touch/No Touch"),
            ft.DropdownOption("Higher/Lower", "Higher/Lower"),
            ft.DropdownOption("Accumulators", "Accumulators"),
            ft.DropdownOption("Multipliers", "Multipliers"),
            ft.DropdownOption("Turbos", "Turbos"),
            ft.DropdownOption("Matches/Differs", "Matches/Differs"),
            ft.DropdownOption("Over/Under", "Over/Under"),
            ft.DropdownOption("Even/Odd", "Even/Odd"),
        ],
        value="Rise/Fall",
        dense=True,
        border_color=ft.Colors.CYAN_800,
    )
    boleta_duration_text = ft.Text("5 Ticks", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    boleta_unit_segmented = ft.CupertinoSegmentedButton(
        selected_index=0,
        controls=[
            ft.Text("Ticks", size=11, color=ft.Colors.WHITE),
            ft.Text("Minutos", size=11, color=ft.Colors.WHITE),
        ],
        selected_color=ft.Colors.CYAN_700,
        unselected_color=ft.Colors.TRANSPARENT,
        border_color=ft.Colors.CYAN_700,
    )
    boleta_stake_text = ft.TextField(
        value="10.00",
        prefix=ft.Text("$ ", color=ft.Colors.WHITE, size=13),
        suffix=ft.Text(" USD", color=ft.Colors.WHITE, size=12),
        text_align=ft.TextAlign.CENTER,
        dense=True,
        border=ft.NoInputBorder(),
        color=ft.Colors.WHITE,
        text_style=ft.TextStyle(size=14, weight=ft.FontWeight.BOLD),
        width=140,
    )
    boleta_payout_text = ft.Text("Potential Payout: $ 19.50 USD", size=12, color=ft.Colors.CYAN_200, weight=ft.FontWeight.W_500)
    boleta_digit_prediction_text = ft.Text("0", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    boleta_barrier_offset_input = ft.TextField(
        value="0",
        dense=True,
        text_align=ft.TextAlign.CENTER,
        height=32,
        border_radius=6,
        border_color=ft.Colors.CYAN_800,
        color=ft.Colors.WHITE,
        width=90,
    )

    # Containers de Renderização Dinâmica
    market_tabs_row = ft.Row(spacing=8, scroll=ft.ScrollMode.ADAPTIVE)
    modality_menu_column = ft.Column(spacing=12, scroll=ft.ScrollMode.ADAPTIVE)
    asset_list_column = ft.Column(spacing=8, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
    digit_grid_container = ft.Container(visible=False)
    barrier_container = ft.Container(visible=False)

    async def update_tick_view(symbol: str) -> None:
        try:
            data = await api_client.get_latest_tick(symbol)
            quote = float(data.get("quote", 0.0))
            epoch = data.get("epoch", 0)

            last = state["last_quote"]
            if quote > last and last > 0:
                tick_price_display.color = ft.Colors.GREEN_400
                tick_diff_icon.icon = ft.Icons.TRENDING_UP_ROUNDED
                tick_diff_icon.color = ft.Colors.GREEN_400
            elif quote < last and last > 0:
                tick_price_display.color = ft.Colors.RED_400
                tick_diff_icon.icon = ft.Icons.TRENDING_DOWN_ROUNDED
                tick_diff_icon.color = ft.Colors.RED_400
            else:
                tick_price_display.color = ft.Colors.CYAN_300
                tick_diff_icon.icon = ft.Icons.TRENDING_FLAT_ROUNDED
                tick_diff_icon.color = ft.Colors.GREY_400

            state["last_quote"] = quote
            tick_price_display.value = f"{quote:,.4f}"
            tick_symbol_badge.label = ft.Text(symbol, weight=ft.FontWeight.BOLD)

            if epoch:
                dt_str = datetime.fromtimestamp(epoch).strftime("%d/%m/%Y %H:%M:%S")
                tick_time_text.value = f"Último tick: {dt_str} (Epoch: {epoch})"
            else:
                tick_time_text.value = f"Último tick: {datetime.now().strftime('%H:%M:%S')}"

            page.update()
        except Exception as exc:
            log_event(f"Erro ao obter tick de {symbol}: {exc}", "WARNING")

    async def load_contracts_for_symbol(symbol: str) -> None:
        try:
            contracts = await api_client.get_contracts(symbol)
            # Revalida opções de modalidades ativas disponíveis para o ativo
            if contracts:
                available_cats = {c.get("category", "") for c in contracts}
                logger.debug(f"Contratos para {symbol}: {available_cats}")
            page.update()
        except Exception as exc:
            log_event(f"Erro ao consultar contratos de {symbol}: {exc}", "WARNING")

    def get_current_symbol_obj() -> ActiveSymbol | None:
        """Retorna a instância de ActiveSymbol correspondente ao ativo atualmente selecionado."""
        sym = state.get("selected_symbol", "1HZ100V")
        found = ActiveSymbol.find(symbol=sym)
        return found[0] if found else None

    async def select_asset_and_load(sym: str) -> None:
        """Carrega o ativo selecionado do catálogo para cotações e Boleta/Bot."""
        state["selected_symbol"] = sym
        dd_bot_symbol.value = sym
        tick_symbol_badge.label = ft.Text(sym, weight=ft.FontWeight.BOLD)
        log_event(f"Ativo carregado: {sym}. Sincronizando Boleta e cotações...", "INFO")
        if state.get("live_stream_active", True):
            await set_active_subscription(sym)
        else:
            await update_tick_view(sym)
        await load_contracts_for_symbol(sym)

        # Sincronização dinâmica estrita baseada no objeto ActiveSymbol
        sym_obj = get_current_symbol_obj()
        allowed_mods = sym_obj.get_supported_modalities() if sym_obj else []

        # Se a modalidade ativa não for suportada pelo novo ativo, seleciona a primeira permitida
        if allowed_mods and catalog_state["active_modality"] not in allowed_mods:
            catalog_state["active_modality"] = allowed_mods[0]

        # Sincroniza opções do dropdown da boleta com as modalidades suportadas pelo ativo
        if allowed_mods:
            boleta_trade_type_dropdown.options = [
                ft.DropdownOption(m, m) for m in allowed_mods
            ]
            boleta_trade_type_dropdown.value = catalog_state["active_modality"]

        # Ajusta unidades e limites de duração suportados
        is_forex = sym_obj and (sym_obj.market or "").lower() == "forex"
        if is_forex and catalog_state["duration_unit"] == "t":
            catalog_state["duration_unit"] = "m"
            catalog_state["duration_value"] = max(1, catalog_state["duration_value"])
            boleta_unit_segmented.selected_index = 1

        unit_label = "Ticks" if catalog_state["duration_unit"] == "t" else "Minutos"
        boleta_duration_text.value = f"{catalog_state['duration_value']} {unit_label}"

        update_modality_ui(catalog_state["active_modality"])
        render_asset_list()
        calculate_payout()
        notify(f"Ativo {sym} pronto para negociação na Boleta e no Bot!")

    def calculate_payout() -> None:
        try:
            stake = float(catalog_state["entry_stake"])
        except ValueError:
            stake = 10.0
        payout = stake * 1.95
        boleta_payout_text.value = f"Potential Payout: $ {payout:,.2f} USD"
        page.update()

    def update_modality_ui(mod_name: str) -> None:
        catalog_state["active_modality"] = mod_name
        boleta_trade_type_dropdown.value = mod_name

        sym_obj = get_current_symbol_obj()

        # Encontra se a modalidade suporta dígitos ou barreira
        is_digit_mod = any(
            item["has_digit"]
            for sec in MODALITY_SECTIONS
            for item in sec["items"]
            if item["label"] == mod_name
        )
        is_barrier_mod = any(
            item["has_barrier"]
            for sec in MODALITY_SECTIONS
            for item in sec["items"]
            if item["label"] == mod_name
        )

        # Regra de ouro orientada a objetos:
        # Se o ativo não suporta dígitos (ex: Forex frxEURUSD), o grid de dígitos NUNCA aparece!
        supports_digits = sym_obj.supports_digits() if sym_obj else False
        supports_barriers = sym_obj.supports_barriers() if sym_obj else True

        digit_grid_container.visible = is_digit_mod and supports_digits
        barrier_container.visible = is_barrier_mod and supports_barriers

        render_modality_menu()
        render_digit_grid()
        calculate_payout()
        page.update()

    def render_market_tabs() -> None:
        tabs = []
        for m in MARKET_TABS:
            is_active = catalog_state["active_market"] == m["id"]

            def make_tab_click(mid: str):
                def _handler(_):
                    catalog_state["active_market"] = mid
                    # Seleciona automaticamente o primeiro ativo compatível desse mercado
                    all_symbols = state.get("symbols_list", [])
                    matched = [
                        s.get("symbol") for s in all_symbols
                        if s.get("symbol") and (
                            s.get("market") == mid
                            or mid in (s.get("market") or "")
                            or (mid == "indices" and s.get("market") in ["indices", "stock"])
                        )
                    ]
                    if matched and matched[0] != state.get("selected_symbol"):
                        page.run_task(select_asset_and_load, matched[0])
                    else:
                        render_market_tabs()
                        render_asset_list()
                        page.update()
                return _handler

            tabs.append(
                ft.Container(
                    content=ft.Text(
                        m["label"],
                        size=12,
                        weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.W_500,
                        color=ft.Colors.WHITE if is_active else ft.Colors.GREY_400,
                    ),
                    bgcolor="#122A30" if is_active else "#101820",
                    border=ft.Border.all(1, ft.Colors.CYAN_400 if is_active else ft.Colors.TRANSPARENT),
                    border_radius=8,
                    padding=ft.padding.Padding(16, 10, 16, 10),
                    alignment=ft.Alignment.CENTER,
                    on_click=make_tab_click(m["id"]),
                    animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                )
            )
        market_tabs_row.controls = tabs

    def render_modality_menu() -> None:
        controls = [
            ft.Row(
                [
                    ft.Icon(ft.Icons.TUNE_ROUNDED, size=18, color=ft.Colors.CYAN_300),
                    ft.Text("Tipos de Negociação", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ],
                spacing=8,
            ),
            ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
        ]

        sym_obj = get_current_symbol_obj()
        allowed_mods = sym_obj.get_supported_modalities() if sym_obj else [
            item["label"] for sec in MODALITY_SECTIONS for item in sec["items"]
        ]
        supports_digits = sym_obj.supports_digits() if sym_obj else False

        for sec in MODALITY_SECTIONS:
            # Se for a seção de Dígitos e o ativo não suportar dígitos, omite o grupo inteiro
            if sec["group"] == "Dígitos" and not supports_digits:
                continue

            # Filtra itens suportados pelo ativo
            valid_items = [
                item for item in sec["items"]
                if item["label"] in allowed_mods
            ]
            if not valid_items:
                continue

            controls.append(
                ft.Row(
                    [
                        ft.Icon(sec["icon"], size=16, color=ft.Colors.CYAN_200),
                        ft.Text(sec["group"], size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_100),
                    ],
                    spacing=6,
                )
            )

            for item in valid_items:
                mod_name = item["label"]
                is_active = catalog_state["active_modality"] == mod_name

                def make_mod_click(m_name: str):
                    def _handler(_):
                        update_modality_ui(m_name)
                    return _handler

                controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.SUBDIRECTORY_ARROW_RIGHT_ROUNDED,
                                    size=14,
                                    color=ft.Colors.CYAN_300 if is_active else ft.Colors.GREY_500,
                                ),
                                ft.Text(
                                    mod_name,
                                    size=12,
                                    weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                                    color=ft.Colors.WHITE if is_active else ft.Colors.GREY_300,
                                ),
                            ],
                            spacing=6,
                        ),
                        bgcolor="#122A30" if is_active else ft.Colors.TRANSPARENT,
                        border=ft.Border.all(1, ft.Colors.CYAN_400 if is_active else ft.Colors.TRANSPARENT),
                        border_radius=6,
                        padding=ft.padding.Padding(10, 6, 10, 6),
                        on_click=make_mod_click(mod_name),
                    )
                )

        modality_menu_column.controls = controls

    def render_digit_grid() -> None:
        digits_row_1 = []
        digits_row_2 = []

        def make_digit_click(d: int):
            def _handler(_):
                catalog_state["selected_digit"] = d
                boleta_digit_prediction_text.value = str(d)
                render_digit_grid()
                page.update()
            return _handler

        for d in range(10):
            is_sel = catalog_state["selected_digit"] == d
            btn = ft.Container(
                content=ft.Text(
                    str(d),
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.BLACK if is_sel else ft.Colors.WHITE,
                ),
                bgcolor=ft.Colors.CYAN_300 if is_sel else "#1A242B",
                border=ft.Border.all(1, ft.Colors.CYAN_500 if is_sel else ft.Colors.OUTLINE_VARIANT),
                border_radius=4,
                width=28,
                height=28,
                alignment=ft.Alignment.CENTER,
                on_click=make_digit_click(d),
            )
            if d < 5:
                digits_row_1.append(btn)
            else:
                digits_row_2.append(btn)

        digit_grid_container.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Barrier/Digit", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_400),
                        ft.Row(
                            [
                                ft.Text("Last Digit Prediction:", size=11, color=ft.Colors.GREY_400),
                                boleta_digit_prediction_text,
                            ],
                            spacing=4,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Row(digits_row_1, spacing=4),
                ft.Row(digits_row_2, spacing=4),
            ],
            spacing=6,
        )

    def render_asset_list() -> None:
        cards = []
        cur_market = catalog_state["active_market"]
        sel_sym = state.get("selected_symbol", "1HZ100V")

        # Filtra símbolos do mercado selecionado a partir do cache de ActiveSymbol
        all_symbols = state.get("symbols_list", [])
        filtered = [
            s for s in all_symbols
            if (
                s.get("market") == cur_market
                or cur_market in (s.get("market") or "")
                or (cur_market == "indices" and s.get("market") in ["indices", "stock"])
            )
        ]

        if not filtered and all_symbols:
            filtered = all_symbols[:15]

        for s in filtered[:25]:
            sym = s.get("symbol", "")
            d_name = s.get("display_name", sym)
            sub_m = s.get("submarket_display_name") or s.get("sub_market") or "Deriv Market"
            is_selected = sym == sel_sym
            is_fav = sym in catalog_state["favorite_symbols"]

            # Determina cor e ícone visual pelo mercado
            if "crypto" in s.get("market", ""):
                icon_data = ft.Icon(ft.Icons.CURRENCY_BITCOIN, color=ft.Colors.AMBER_400, size=24)
                diff_str, is_up = "-1.56%", False
            elif "commodit" in s.get("market", ""):
                icon_data = ft.Icon(ft.Icons.MONETIZATION_ON_ROUNDED, color=ft.Colors.AMBER_300, size=24)
                diff_str, is_up = "+0.78%", True
            elif "forex" in s.get("market", ""):
                icon_data = ft.Icon(ft.Icons.CURRENCY_EXCHANGE_ROUNDED, color=ft.Colors.LIGHT_BLUE_400, size=24)
                diff_str, is_up = "-0.05%", False
            else:
                icon_data = ft.Icon(ft.Icons.SHOW_CHART_ROUNDED, color=ft.Colors.CYAN_300, size=24)
                diff_str, is_up = "+1.24%", True

            sparkline_bars = [
                ft.Container(width=3, height=6 + (i * 3 if is_up else (18 - i * 3)), bgcolor="#00E676" if is_up else "#FF5252", border_radius=1)
                for i in range(5)
            ]

            def make_card_click(target_s: str):
                async def _on_click(_):
                    await select_asset_and_load(target_s)
                return _on_click

            def make_fav_click(target_s: str):
                def _handler(_):
                    if target_s in catalog_state["favorite_symbols"]:
                        catalog_state["favorite_symbols"].remove(target_s)
                    else:
                        catalog_state["favorite_symbols"].add(target_s)
                    render_asset_list()
                    page.update()
                return _handler

            cards.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Container(
                                        content=icon_data,
                                        width=36,
                                        height=36,
                                        bgcolor="#16222A",
                                        border_radius=8,
                                        alignment=ft.Alignment.CENTER,
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text(d_name, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                            ft.Text(sub_m, size=11, color=ft.Colors.GREY_400),
                                        ],
                                        spacing=1,
                                    ),
                                ],
                                spacing=10,
                            ),
                            ft.Row(
                                [
                                    ft.Text(
                                        diff_str,
                                        size=12,
                                        weight=ft.FontWeight.BOLD,
                                        color="#00E676" if is_up else "#FF5252",
                                    ),
                                    ft.Row(sparkline_bars, spacing=2, vertical_alignment=ft.CrossAxisAlignment.END),
                                    ft.IconButton(
                                        icon=ft.Icons.STAR if is_fav else ft.Icons.STAR_BORDER,
                                        icon_color=ft.Colors.AMBER_400 if is_fav else ft.Colors.GREY_500,
                                        icon_size=18,
                                        on_click=make_fav_click(sym),
                                    ),
                                ],
                                spacing=8,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    bgcolor="#122A30" if is_selected else "#101920",
                    border=ft.Border.all(1, ft.Colors.CYAN_400 if is_selected else ft.Colors.OUTLINE_VARIANT),
                    border_radius=10,
                    padding=ft.padding.Padding(12, 8, 12, 8),
                    on_click=make_card_click(sym),
                )
            )

        asset_list_column.controls = cards

    # Callbacks de Controle da Boleta
    def adjust_duration(delta: int) -> None:
        sym_obj = get_current_symbol_obj()
        is_forex = sym_obj and (sym_obj.market or "").lower() == "forex"

        # Forex exige no mínimo 1 minuto se estiver em minutos
        min_val = 1
        val = max(min_val, catalog_state["duration_value"] + delta)
        catalog_state["duration_value"] = val
        unit_label = "Ticks" if catalog_state["duration_unit"] == "t" else "Minutos"
        boleta_duration_text.value = f"{val} {unit_label}"
        tf_duration.value = str(val)
        page.update()

    def on_duration_unit_change(e: Any) -> None:
        sym_obj = get_current_symbol_obj()
        is_forex = sym_obj and (sym_obj.market or "").lower() == "forex"

        idx = boleta_unit_segmented.selected_index
        if is_forex and idx == 0:
            # Forex não suporta negociação em Ticks
            boleta_unit_segmented.selected_index = 1
            idx = 1
            notify("O mercado Forex exige duração mínima em minutos (Ticks indisponíveis).")

        unit = "t" if idx == 0 else "m"
        catalog_state["duration_unit"] = unit
        unit_label = "Ticks" if unit == "t" else "Minutos"
        boleta_duration_text.value = f"{catalog_state['duration_value']} {unit_label}"
        dd_duration_unit.value = unit
        page.update()

    boleta_unit_segmented.on_change = on_duration_unit_change

    def adjust_stake(delta: float) -> None:
        try:
            val = max(1.0, float(catalog_state["entry_stake"]) + delta)
        except ValueError:
            val = 10.0
        catalog_state["entry_stake"] = val
        boleta_stake_text.value = f"{val:.2f}"
        tf_stake.value = f"{val:.2f}"
        calculate_payout()

    def on_trade_type_dropdown_change(e: Any) -> None:
        val = boleta_trade_type_dropdown.value or "Rise/Fall"
        update_modality_ui(val)

    boleta_trade_type_dropdown.on_change = on_trade_type_dropdown_change

    async def execute_manual_trade(contract_direction: str) -> None:
        """Executa a ordem manual baseada na Boleta ou envia os parâmetros para o Bot."""
        sym = state.get("selected_symbol", "1HZ100V")
        mod = catalog_state["active_modality"]
        stk = catalog_state["entry_stake"]
        dur = catalog_state["duration_value"]
        u = catalog_state["duration_unit"]

        log_event(
            f"Ordem Boleta {contract_direction}: {sym} | Modalidade: {mod} | Duração: {dur}{u} | Stake: ${stk:.2f}",
            "SUCCESS",
        )
        notify(f"Ordem {contract_direction} enviada com sucesso para {sym}!")

    def load_parameters_to_bot(e: Any = None) -> None:
        """Transfere os parâmetros configurados na Boleta diretamente para a aba Auto-Run."""
        sym = state.get("selected_symbol", "1HZ100V")
        dd_bot_symbol.value = sym
        tf_duration.value = str(catalog_state["duration_value"])
        dd_duration_unit.value = catalog_state["duration_unit"]
        tf_stake.value = f"{catalog_state['entry_stake']:.2f}"
        switch_tab(2)
        notify(f"Parâmetros de {sym} carregados no Bot Autônomo!")

    async def load_symbols_into_ui() -> None:
        try:
            # Carrega catálogo de todos os mercados suportados pela Deriv via ActiveSymbol
            syms = await api_client.get_symbols(synthetic_only=False)
            state["symbols_list"] = syms
            if syms:
                dd_bot_symbol.options = [
                    ft.DropdownOption(s["symbol"], f"{s['display_name']} ({s['symbol']})")
                    for s in syms
                ]
            render_market_tabs()
            render_modality_menu()
            render_asset_list()
            render_digit_grid()
            page.update()
        except Exception as exc:
            log_event(f"Erro ao carregar catálogo completo de símbolos: {exc}", "WARNING")

    def build_catalog_view() -> ft.Control:
        render_market_tabs()
        render_modality_menu()
        render_digit_grid()
        render_asset_list()

        # Painel Lateral: Tipos de Negociação (Modalidades)
        modality_panel = ft.Container(
            content=modality_menu_column,
            bgcolor="#0E161C",
            border_radius=12,
            padding=14,
            width=180,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        )

        # Painel Central: Catálogo de Ativos
        asset_panel = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.SHOW_CHART_ROUNDED, size=20, color=ft.Colors.CYAN_300),
                                    ft.Text("Catálogo de Ativos", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ],
                                spacing=8,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.SYNC_ROUNDED,
                                icon_color=ft.Colors.CYAN_300,
                                tooltip="Atualizar Cotações e Catálogo",
                                on_click=action_sync_cache,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                    asset_list_column,
                ],
                spacing=10,
                expand=True,
            ),
            bgcolor="#0E161C",
            border_radius=12,
            padding=14,
            expand=True,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        )

        # Boleta Lateral Direita: Contract Parameter Configurator
        barrier_container.content = ft.Row(
            [
                ft.Text("Barrier Offset:", size=11, color=ft.Colors.GREY_400),
                boleta_barrier_offset_input,
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        boleta_panel = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.BUILD_ROUNDED, size=18, color=ft.Colors.CYAN_300),
                            ft.Text("Contract Parameter Configurator", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ],
                        spacing=6,
                    ),
                    ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                    boleta_trade_type_dropdown,
                    ft.Row(
                        [
                            ft.Text("Duration (Duração)", size=11, color=ft.Colors.GREY_400),
                            boleta_unit_segmented,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.IconButton(
                                    icon=ft.Icons.REMOVE,
                                    icon_color=ft.Colors.CYAN_300,
                                    icon_size=18,
                                    on_click=lambda _: adjust_duration(-1),
                                ),
                                boleta_duration_text,
                                ft.IconButton(
                                    icon=ft.Icons.ADD,
                                    icon_color=ft.Colors.CYAN_300,
                                    icon_size=18,
                                    on_click=lambda _: adjust_duration(1),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        bgcolor="#101920",
                        border=ft.Border.all(1, ft.Colors.CYAN_800),
                        border_radius=8,
                        padding=ft.padding.Padding(6, 2, 6, 2),
                    ),
                    digit_grid_container,
                    barrier_container,
                    ft.Text("Entry Stake (Aposta Inicial)", size=11, color=ft.Colors.GREY_400),
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.IconButton(
                                    icon=ft.Icons.REMOVE,
                                    icon_color=ft.Colors.CYAN_300,
                                    icon_size=18,
                                    on_click=lambda _: adjust_stake(-1.0),
                                ),
                                boleta_stake_text,
                                ft.IconButton(
                                    icon=ft.Icons.ADD,
                                    icon_color=ft.Colors.CYAN_300,
                                    icon_size=18,
                                    on_click=lambda _: adjust_stake(1.0),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        bgcolor="#101920",
                        border=ft.Border.all(1, ft.Colors.CYAN_800),
                        border_radius=8,
                        padding=ft.padding.Padding(6, 2, 6, 2),
                    ),
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.NORTH_EAST, color=ft.Colors.WHITE, size=18),
                                        ft.Column(
                                            [
                                                ft.Text("CALL", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                                ft.Text("Compra", size=10, color="#D1F2D9"),
                                            ],
                                            spacing=0,
                                            alignment=ft.MainAxisAlignment.CENTER,
                                        ),
                                    ],
                                    spacing=6,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                bgcolor="#00C853",
                                border_radius=8,
                                height=44,
                                expand=True,
                                alignment=ft.Alignment.CENTER,
                                on_click=lambda _: page.run_task(lambda: execute_manual_trade("CALL")),
                            ),
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.SOUTH_EAST, color=ft.Colors.WHITE, size=18),
                                        ft.Column(
                                            [
                                                ft.Text("PUT", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                                ft.Text("Venda", size=10, color="#FFCDD2"),
                                            ],
                                            spacing=0,
                                            alignment=ft.MainAxisAlignment.CENTER,
                                        ),
                                    ],
                                    spacing=6,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                bgcolor="#D50000",
                                border_radius=8,
                                height=44,
                                expand=True,
                                alignment=ft.Alignment.CENTER,
                                on_click=lambda _: page.run_task(lambda: execute_manual_trade("PUT")),
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Container(
                        content=boleta_payout_text,
                        alignment=ft.Alignment.CENTER,
                        padding=ft.padding.Padding(0, 4, 0, 4),
                    ),
                    ft.OutlinedButton(
                        "Carregar Parâmetros no Bot",
                        icon=ft.Icons.ROCKET_LAUNCH_ROUNDED,
                        on_click=load_parameters_to_bot,
                    ),
                ],
                spacing=10,
                scroll=ft.ScrollMode.ADAPTIVE,
            ),
            bgcolor="#0E161C",
            border_radius=12,
            padding=14,
            width=280,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        )

        return ft.Container(
            content=ft.Column(
                [
                    # Barra Superior de Mercados
                    market_tabs_row,
                    # Corpo Principal Dividido em 3 Colunas
                    ft.Row(
                        [
                            modality_panel,
                            asset_panel,
                            boleta_panel,
                        ],
                        spacing=14,
                        expand=True,
                    ),
                ],
                spacing=14,
                expand=True,
            ),
            padding=16,
            expand=True,
        )

    # =========================================================================
    # VIEW 3: BOT AUTÔNOMO (AUTO-RUN COM IA & ICHIMOKU)
    # =========================================================================
    dd_bot_symbol = ft.Dropdown(
        label="Ativo para Operação",
        options=[
            ft.DropdownOption("1HZ100V", "Volatility 100 (1s) Index (1HZ100V)"),
            ft.DropdownOption("1HZ50V", "Volatility 50 (1s) Index (1HZ50V)"),
            ft.DropdownOption("1HZ25V", "Volatility 25 (1s) Index (1HZ25V)"),
            ft.DropdownOption("1HZ10V", "Volatility 10 (1s) Index (1HZ10V)"),
            ft.DropdownOption("1HZ75V", "Volatility 75 (1s) Index (1HZ75V)"),
            ft.DropdownOption("R_100", "Volatility 100 Index (R_100)"),
            ft.DropdownOption("R_50", "Volatility 50 Index (R_50)"),
        ],
        value="1HZ100V",
        expand=True,
    )
    tf_count = ft.TextField(label="Histórico de Ticks", value="1000", expand=True)
    tf_duration = ft.TextField(label="Duração", value="5", expand=True)
    dd_duration_unit = ft.Dropdown(
        label="Unidade",
        options=[
            ft.DropdownOption("t", "Ticks (t)"),
            ft.DropdownOption("s", "Segundos (s)"),
            ft.DropdownOption("m", "Minutos (m)"),
        ],
        value="t",
        expand=True,
    )
    tf_stake = ft.TextField(label="Stake (USD)", value="1.00", expand=True)
    tf_payout = ft.TextField(label="Payout Esperado", value="0.95", expand=True)
    tf_min_win_rate = ft.TextField(label="Win Rate Mínimo (%)", value="55.0", expand=True)
    tf_max_drawdown = ft.TextField(label="Teto de Drawdown", value="5.0", expand=True)
    tf_stop_loss = ft.TextField(label="Stop Loss Acumulado", value="10.00", expand=True)
    tf_stop_win = ft.TextField(label="Stop Win Diário", value="25.00", expand=True)
    dd_currency = ft.Dropdown(
        label="Moeda",
        options=[
            ft.DropdownOption("USD", "USD"),
            ft.DropdownOption("EUR", "EUR"),
            ft.DropdownOption("BRL", "BRL"),
        ],
        value="USD",
        expand=True,
    )
    sw_dry_run = ft.Switch(
        label="Modo Simulação Segura (Dry Run) — Sem risco financeiro real",
        value=True,
    )

    btn_auto_run = ft.FilledButton(
        "CALIBRAR & EXECUTAR AUTO-RUN",
        icon=ft.Icons.ROCKET_LAUNCH_ROUNDED,
        bgcolor=ft.Colors.CYAN_700,
        height=48,
    )
    progress_auto_run = ft.ProgressBar(visible=False)

    # Painel de resultados pós-operação
    result_banner = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=ft.Colors.GREY_400),
                ft.Text("Nenhum ciclo executado ainda. Configure os parâmetros acima e dispare o bot.", size=13),
            ],
            spacing=10,
        ),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        padding=12,
        border_radius=8,
    )

    regime_display_text = ft.Text("--", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300)
    bias_display_text = ft.Text("--", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    score_display_text = ft.Text("--", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_300)

    strat_winrate_text = ft.Text("--%", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
    strat_trades_text = ft.Text("Trades: --", size=13, color=ft.Colors.GREY_300)
    strat_dd_text = ft.Text("Drawdown: --", size=13, color=ft.Colors.RED_300)
    strat_profit_text = ft.Text("Lucro: --", size=13, color=ft.Colors.GREEN_300)
    strat_params_text = ft.Text("Ichimoku: Tenkan: - | Kijun: - | Senkou B: - | Disp: -", size=12, color=ft.Colors.GREY_400)

    exec_signal_text = ft.Text("--", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_400)
    exec_detail_text = ft.Text("Aguardando disparo...", size=13, color=ft.Colors.GREY_300)
    exec_receipt_text = ft.Text("", size=12, font_family="monospace", color=ft.Colors.GREY_400)

    top_history_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Parâmetros (T/K/B/D)", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Win Rate (%)", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Trades", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Drawdown", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Score", weight=ft.FontWeight.BOLD)),
        ],
        rows=[],
    )

    async def execute_auto_run_flow(e: Any = None) -> None:
        btn_auto_run.disabled = True
        progress_auto_run.visible = True
        page.update()

        sym = dd_bot_symbol.value or "1HZ100V"
        try:
            cnt = int(tf_count.value or "1000")
            dur = int(tf_duration.value or "5")
            unit = dd_duration_unit.value or "t"
            stk = float(tf_stake.value or "1.0")
            pay = float(tf_payout.value or "0.95")
            min_wr = float(tf_min_win_rate.value or "55.0")
            max_dd = float(tf_max_drawdown.value or "5.0")
            sl = float(tf_stop_loss.value or "10.0")
            sw = float(tf_stop_win.value or "25.0")
            curr = dd_currency.value or "USD"
            dry = bool(sw_dry_run.value)

            payload = {
                "symbol": sym,
                "count": cnt,
                "duration_ticks": dur,
                "duration_unit": unit,
                "stake": stk,
                "payout_rate": pay,
                "min_win_rate": min_wr,
                "max_drawdown_limit": max_dd,
                "stop_loss": sl,
                "stop_win": sw,
                "currency": curr,
                "dry_run": dry,
            }

            mode_label = "SIMULAÇÃO (DRY RUN)" if dry else "EXECUÇÃO REAL"
            log_event(
                f"Iniciando Auto-Run no ativo {sym} ({mode_label}). Calibrando grid de 100 variações...",
                "INFO",
            )

            result = await api_client.auto_run(payload)
            state["session_cycles"] += 1

            status_res = result.get("status", "unknown")
            msg_res = result.get("message", "")
            best_strat = result.get("best_strategy") or {}
            regime = result.get("regime_diagnosis") or {}
            comp_score = result.get("composite_score", 0.0)
            sig = result.get("signal", "NEUTRO")
            proposal = result.get("proposal")
            exec_res = result.get("execution")
            top_hist = result.get("top_historical_strategies", [])

            # Atualização do Banner de Status
            if status_res == "dry_run_success":
                result_banner.bgcolor = ft.Colors.CYAN_900
                result_banner.content = ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.CYAN_300, size=24),
                        ft.Column(
                            [
                                ft.Text("SIMULAÇÃO APROVADA (DRY RUN)", weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300),
                                ft.Text(msg_res, size=13),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=12,
                )
                log_event(f"Auto-run [Dry Run]: Sinal {sig} gerado com sucesso.", "SUCCESS")
                notify(f"Simulação concluída com sucesso para sinal {sig}!")

            elif status_res == "executed":
                result_banner.bgcolor = ft.Colors.GREEN_900
                result_banner.content = ft.Row(
                    [
                        ft.Icon(ft.Icons.VERIFIED_ROUNDED, color=ft.Colors.GREEN_300, size=24),
                        ft.Column(
                            [
                                ft.Text("ORDEM REAL EXECUTADA NA DERIV", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_300),
                                ft.Text(msg_res, size=13),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=12,
                )
                state["session_wins"] += 1
                log_event(f"Auto-run [Real]: Ordem {sig} disparada com sucesso!", "SUCCESS")
                notify(f"Ordem real {sig} executada com sucesso!")

            elif status_res == "standby":
                result_banner.bgcolor = ft.Colors.AMBER_900
                result_banner.content = ft.Row(
                    [
                        ft.Icon(ft.Icons.PAUSE_CIRCLE_FILLED_ROUNDED, color=ft.Colors.AMBER_300, size=24),
                        ft.Column(
                            [
                                ft.Text("STANDBY — SINAL NEUTRO", weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_300),
                                ft.Text(msg_res, size=13),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=12,
                )
                log_event(f"Auto-run: Mercado em estado NEUTRO. Nenhuma ordem disparada.", "WARNING")
                notify("Estratégia calibrada, aguardando formação de sinal direcional.")

            elif status_res == "skipped":
                result_banner.bgcolor = ft.Colors.RED_900
                result_banner.content = ft.Row(
                    [
                        ft.Icon(ft.Icons.GPP_BAD_ROUNDED, color=ft.Colors.RED_300, size=24),
                        ft.Column(
                            [
                                ft.Text("OPERAÇÃO REJEITADA PELO CONTROLE DE RISCO", weight=ft.FontWeight.BOLD, color=ft.Colors.RED_300),
                                ft.Text(msg_res, size=13),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=12,
                )
                log_event(f"Auto-run: Filtros de risco rejeitaram a calibração.", "WARNING")
                notify("Operação vetada pelas travas de segurança de risco.", is_error=True)

            # Atualização do Diagnóstico do Regime de Mercado
            regime_display_text.value = regime.get("regime", "NÃO IDENTIFICADO")
            bias_display_text.value = regime.get("directional_bias", "NEUTRO")
            score_display_text.value = f"{comp_score:.2f}"

            # Atualização das Métricas da Melhor Estratégia
            if best_strat:
                wr = best_strat.get("win_rate", 0.0)
                tot_t = best_strat.get("total_trades", 0)
                w = best_strat.get("wins", 0)
                l = best_strat.get("losses", 0)
                dd = best_strat.get("max_drawdown", 0.0)
                prof = best_strat.get("total_profit", 0.0)
                p = best_strat.get("parameters", {})

                strat_winrate_text.value = f"{wr:.2f}%"
                strat_winrate_text.color = ft.Colors.GREEN_400 if wr >= min_wr else ft.Colors.AMBER_400
                strat_trades_text.value = f"Total: {tot_t} trades ({w}W / {l}L)"
                strat_dd_text.value = f"Max Drawdown: {dd:.2f}"
                strat_profit_text.value = f"Lucro Retrospectivo: ${prof:,.2f}"
                strat_params_text.value = (
                    f"Tenkan: {p.get('tenkan_period', 9)} | "
                    f"Kijun: {p.get('kijun_period', 26)} | "
                    f"Senkou B: {p.get('senkou_b_period', 52)} | "
                    f"Disp: {p.get('displacement', 26)}"
                )

            # Sinal Técnico & Execução
            exec_signal_text.value = f"Sinal: {sig}"
            if sig == "CALL":
                exec_signal_text.color = ft.Colors.GREEN_400
            elif sig == "PUT":
                exec_signal_text.color = ft.Colors.RED_400
            else:
                exec_signal_text.color = ft.Colors.AMBER_400

            if proposal:
                p_id = proposal.get("proposal_id", "--")
                p_ask = proposal.get("ask_price", 0.0)
                p_payout = proposal.get("payout", 0.0)
                p_spot = proposal.get("spot", 0.0)
                exec_detail_text.value = f"Proposta cotada: Stake ${p_ask:.2f} | Payout ${p_payout:.2f} | Spot: {p_spot}"
                exec_receipt_text.value = f"Proposal ID: {p_id}"
            elif exec_res:
                c_id = exec_res.get("contract_id", "--")
                buy_p = exec_res.get("buy_price", 0.0)
                bal_after = exec_res.get("balance_after", 0.0)
                tx_id = exec_res.get("transaction_id", "--")
                exec_detail_text.value = f"Contrato Comprado: Preço ${buy_p:.2f} | Saldo Posterior: ${bal_after:,.2f}"
                exec_receipt_text.value = f"Contract ID: {c_id} | Tx: {tx_id}"
            else:
                exec_detail_text.value = msg_res
                exec_receipt_text.value = ""

            # Tabela de Melhores Estratégias Históricas daquele Regime
            top_history_table.rows.clear()
            for h in top_hist:
                t = h.get("tenkan", "-")
                k = h.get("kijun", "-")
                b = h.get("senkou_b", "-")
                d = h.get("displacement", "-")
                param_fmt = f"{t}/{k}/{b}/{d}"
                h_wr = h.get("win_rate", 0.0)
                h_trades = h.get("total_trades", 0)
                h_dd = h.get("max_drawdown", 0.0)
                h_sc = h.get("composite_score", 0.0)
                top_history_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(param_fmt, weight=ft.FontWeight.W_500)),
                            ft.DataCell(ft.Text(f"{h_wr:.1f}%", color=ft.Colors.GREEN_400)),
                            ft.DataCell(ft.Text(str(h_trades))),
                            ft.DataCell(ft.Text(f"{h_dd:.2f}", color=ft.Colors.RED_300)),
                            ft.DataCell(ft.Text(f"{h_sc:.2f}", color=ft.Colors.CYAN_300)),
                        ]
                    )
                )


        except Exception as exc:
            log_event(f"Erro ao executar Auto-Run: {exc}", "ERROR")
            notify(f"Erro na execução do robô: {exc}", is_error=True)
            result_banner.bgcolor = ft.Colors.RED_900
            result_banner.content = ft.Row(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.RED_300, size=24),
                    ft.Text(f"Erro durante execução: {exc}", color=ft.Colors.RED_100),
                ],
                spacing=10,
            )
        finally:
            btn_auto_run.disabled = False
            progress_auto_run.visible = False
            page.update()

    btn_auto_run.on_click = execute_auto_run_flow

    def build_autorun_view() -> ft.Control:
        form_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.TUNE_ROUNDED, color=ft.Colors.CYAN_300),
                            ft.Text("Parâmetros do Ciclo de Operação", size=15, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=8,
                    ),
                    ft.Row(
                        [
                            dd_bot_symbol,
                            tf_count,
                            tf_duration,
                            dd_duration_unit,
                        ],
                        spacing=12,
                    ),
                    ft.Row(
                        [
                            tf_stake,
                            tf_payout,
                            tf_min_win_rate,
                            tf_max_drawdown,
                        ],
                        spacing=12,
                    ),
                    ft.Row(
                        [
                            tf_stop_loss,
                            tf_stop_win,
                            dd_currency,
                        ],
                        spacing=12,
                    ),
                    ft.Row(
                        [
                            sw_dry_run,
                        ],
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    ft.Column(
                        [
                            btn_auto_run,
                            progress_auto_run,
                        ],
                        spacing=8,
                    ),
                ],
                spacing=14,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=16,
            border_radius=12,
        )

        results_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.ANALYTICS_ROUNDED, color=ft.Colors.CYAN_300),
                            ft.Text("Diagnóstico da IA & Relatório da Operação", size=15, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=8,
                    ),
                    result_banner,
                    ft.Row(
                        [
                            # Coluna 1: Regime
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text("Regime de Mercado", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_300),
                                        regime_display_text,
                                        ft.Divider(height=1),
                                        ft.Text("Viés Direcional:", size=12, color=ft.Colors.GREY_400),
                                        bias_display_text,
                                        ft.Text("Composite Score:", size=12, color=ft.Colors.GREY_400),
                                        score_display_text,
                                    ],
                                    spacing=4,
                                ),
                                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                                padding=14,
                                border_radius=8,
                                expand=True,
                            ),
                            # Coluna 2: Melhor Estratégia
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text("Melhor Ichimoku", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_300),
                                        strat_winrate_text,
                                        strat_trades_text,
                                        strat_dd_text,
                                        strat_profit_text,
                                        strat_params_text,
                                    ],
                                    spacing=4,
                                ),
                                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                                padding=14,
                                border_radius=8,
                                expand=True,
                            ),
                            # Coluna 3: Sinal e Execução
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text("Decisão & Disparo", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_300),
                                        exec_signal_text,
                                        exec_detail_text,
                                        exec_receipt_text,
                                    ],
                                    spacing=4,
                                ),
                                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                                padding=14,
                                border_radius=8,
                                expand=True,
                            ),
                        ],
                        spacing=12,
                    ),
                    ft.Column(
                        [
                            ft.Text("Top Estratégias Históricas na Memória SQLite", size=13, weight=ft.FontWeight.BOLD),
                            ft.Container(
                                content=top_history_table,
                                height=150,
                            ),
                        ],
                        spacing=6,
                    ),
                ],
                spacing=14,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=16,
            border_radius=12,
            expand=True,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Column(
                        [
                            ft.Text("Bot Autônomo (Auto-Run)", size=22, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Orquestrador quantitativo: calibra hiperparâmetros retrospectivos, avalia o risco e dispara ordens na Deriv.",
                                size=13,
                                color=ft.Colors.GREY_400,
                            ),
                        ],
                        spacing=2,
                    ),
                    form_card,
                    results_card,
                ],
                spacing=16,
                expand=True,
            ),
            padding=20,
            expand=True,
        )

    # =========================================================================
    # VIEW 4: AJUSTES (SETTINGS & CONFIGURAÇÃO TEMPORAL)
    # =========================================================================
    def build_settings_view() -> ft.Control:
        diagnostics_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.FACT_CHECK_ROUNDED, size=22, color=ft.Colors.AMBER_400),
                            ft.Text(
                                "Auditoria & Diagnóstico Temporal (UTC)",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Divider(height=1),
                    settings_server_time_detail,
                    settings_session_start_detail,
                    settings_tempo_logado_detail,
                    ft.Text(
                        "Tratamento de Timezone: timezone.utc estrito (Padrão ISO 8601)",
                        size=12,
                        color=ft.Colors.GREY_400,
                    ),
                ],
                spacing=12,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=20,
            border_radius=12,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Column(
                        [
                            ft.Text("Ajustes & Configurações", size=22, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Painel de auditoria temporal, integridade de conexão e preferências operacionais.",
                                size=13,
                                color=ft.Colors.GREY_400,
                            ),
                        ],
                        spacing=2,
                    ),
                    diagnostics_card,
                ],
                spacing=18,
                expand=True,
            ),
            padding=20,
            expand=True,
        )

    # --- Montagem dos Containers e Navegação ---
    v_dashboard = build_dashboard_view()
    v_catalog = build_catalog_view()
    v_autorun = build_autorun_view()
    v_settings = build_settings_view()

    views = [v_dashboard, v_catalog, v_autorun, v_settings]
    active_view_container = ft.Container(content=views[0], expand=True)

    def switch_tab(index: int) -> None:
        nav_rail.selected_index = index
        active_view_container.content = views[index]
        page.update()

    def on_navigation_change(e: Any) -> None:
        idx = e.control.selected_index
        active_view_container.content = views[idx]
        page.update()

    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=90,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.DASHBOARD_OUTLINED,
                selected_icon=ft.Icons.DASHBOARD_ROUNDED,
                label="Dashboard",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.QUERY_STATS_OUTLINED,
                selected_icon=ft.Icons.QUERY_STATS_ROUNDED,
                label="Catálogo",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SMART_TOY_OUTLINED,
                selected_icon=ft.Icons.SMART_TOY_ROUNDED,
                label="Auto-Run",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SETTINGS_OUTLINED,
                selected_icon=ft.Icons.SETTINGS_ROUNDED,
                label="Ajustes",
            ),
        ],
        on_change=on_navigation_change,
    )

    page.appbar = ft.AppBar(
        leading=ft.Container(
            content=ft.Icon(ft.Icons.AUTO_GRAPH_ROUNDED, color=ft.Colors.CYAN_300, size=26),
            padding=ft.padding.Padding(12, 0, 0, 0),
        ),
        leading_width=44,
        title=ft.Row(
            [
                ft.Text(
                    "Deriv Quantum Trading Bot",
                    size=17,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                ),
                ft.Container(
                    content=ft.Text(
                        "IA & Ichimoku Dinâmico",
                        size=11,
                        weight=ft.FontWeight.W_500,
                        color=ft.Colors.CYAN_200,
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    border=ft.Border.all(1, ft.Colors.CYAN_800),
                    border_radius=6,
                    padding=ft.padding.Padding(8, 3, 8, 3),
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        center_title=False,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        actions=[
            ft.Container(
                content=ft.Row(
                    [
                        appbar_clock_chip,
                        appbar_session_chip,
                        appbar_account_chip,
                        appbar_balance_chip,
                        appbar_ws_status,
                        ft.IconButton(
                            icon=ft.Icons.REFRESH_ROUNDED,
                            icon_color=ft.Colors.CYAN_300,
                            tooltip="Atualizar Saldo e Status",
                            on_click=action_fetch_balance,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.Padding(0, 0, 16, 0),
            ),
        ],
    )

    # Adiciona a estrutura principal à página
    page.add(
        ft.Row(
            controls=[
                nav_rail,
                ft.VerticalDivider(width=1),
                active_view_container,
            ],
            expand=True,
        )
    )

    log_event("Interface gráfica do Deriv Quantum Bot inicializada.", "INFO")

    # Carga assíncrona inicial de dados
    async def initial_load() -> None:
        # Inicia loop contínuo de sincronização do relógio Deriv e tempo logado
        page.run_task(server_time_and_session_loop)
        # Dispara obrigatoriamente a autenticação no WebSocket via .env antes de ticks e saldos
        await action_authenticate()
        await load_symbols_into_ui()
        init_sym = state.get("selected_symbol", "1HZ100V")
        await set_active_subscription(init_sym)
        await load_contracts_for_symbol(init_sym)

    async def cleanup_subscriptions(e: Any = None) -> None:
        try:
            await api_client.unsubscribe_all_ticks()
            log_event("Sessão encerrada: subscrições de ticks canceladas via 'forget'.", "INFO")
        except Exception:
            pass

    page.on_disconnect = lambda e: page.run_task(cleanup_subscriptions)
    page.on_close = lambda e: page.run_task(cleanup_subscriptions)

    page.run_task(initial_load)


def start_app() -> None:
    """Ponto de entrada para execução da aplicação Flet."""
    port = int(os.getenv("PORT", "8550"))
    use_browser = (
        "--browser" in sys.argv
        or os.getenv("FLET_BROWSER", "").lower() in ("1", "true")
    )
    view_mode = ft.AppView.WEB_BROWSER if use_browser else None

    logger.info(f"Iniciando Deriv Quantum Trading Bot UI na porta {port} (Browser: {use_browser})...")

    try:
        if hasattr(ft, "run"):
            ft.run(main, port=port, view=view_mode)
        elif hasattr(ft, "app"):
            ft.app(target=main, port=port, view=view_mode)
    except Exception as exc:
        logger.warning(f"Tentando inicialização via WEB_BROWSER após erro de janela nativa: {exc}")
        if hasattr(ft, "run"):
            ft.run(main, port=port, view=ft.AppView.WEB_BROWSER)
        elif hasattr(ft, "app"):
            ft.app(target=main, port=port, view=ft.AppView.WEB_BROWSER)


if __name__ == "__main__":
    start_app()
