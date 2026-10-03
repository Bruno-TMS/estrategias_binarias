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
        "tempo_atualizacao": 300.0,
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

    # --- Elementos do AppBar ---
    appbar_api_mode = ft.Chip(
        label=ft.Text("Modo: Detectando...", size=11),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
    )
    appbar_ws_status = ft.Chip(
        label=ft.Text("WS: Standby", size=11, color=ft.Colors.AMBER_200),
        bgcolor=ft.Colors.AMBER_900,
    )
    appbar_account_chip = ft.Chip(
        leading=ft.Icon(ft.Icons.ACCOUNT_CIRCLE_ROUNDED, size=16, color=ft.Colors.GREY_400),
        label=ft.Text("Conta: Standby", size=11),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
    )
    appbar_balance_chip = ft.Chip(
        label=ft.Text(f"Saldo: {format_currency(0.0)}", size=11, weight=ft.FontWeight.BOLD),
        bgcolor=ft.Colors.GREEN_900,
    )
    appbar_clock_chip = ft.Chip(
        leading=ft.Icon(ft.Icons.SCHEDULE_ROUNDED, size=16, color=ft.Colors.CYAN_200),
        label=ft.Text("UTC: --:--:--", size=11, weight=ft.FontWeight.W_500),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        tooltip="Relógio Oficial Deriv (UTC)",
    )
    appbar_session_chip = ft.Chip(
        leading=ft.Icon(ft.Icons.TIMER_ROUNDED, size=16, color=ft.Colors.AMBER_200),
        label=ft.Text("Sessão: --", size=11, weight=ft.FontWeight.BOLD),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        tooltip="Tempo Logado na Sessão Ativa",
    )

    def update_header_status() -> None:
        mode_text = "API REST (:8000)" if api_client.mode == "api" else "Serviços Diretos"
        appbar_api_mode.label = ft.Text(f"Modo: {mode_text}", size=11)

        if state["ws_connected"]:
            appbar_ws_status.label = ft.Text("WS: Conectado", size=11, color=ft.Colors.GREEN_200)
            appbar_ws_status.bgcolor = ft.Colors.GREEN_900
        else:
            appbar_ws_status.label = ft.Text("WS: Desconectado", size=11, color=ft.Colors.RED_200)
            appbar_ws_status.bgcolor = ft.Colors.RED_900

        if state["is_authenticated"]:
            tag = "Demo" if state["is_virtual"] else "Real"
            appbar_account_chip.label = ft.Text(
                f"{state['loginid']} ({tag})",
                size=11,
                weight=ft.FontWeight.BOLD,
            )
            appbar_account_chip.bgcolor = ft.Colors.TEAL_900 if state["is_virtual"] else ft.Colors.AMBER_900
            appbar_account_chip.leading = ft.Icon(
                ft.Icons.VERIFIED_USER_ROUNDED,
                size=16,
                color=ft.Colors.TEAL_200 if state["is_virtual"] else ft.Colors.AMBER_200,
            )
        else:
            appbar_account_chip.label = ft.Text("Não Autenticado", size=11)
            appbar_account_chip.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGHEST
            appbar_account_chip.leading = ft.Icon(
                ft.Icons.ACCOUNT_CIRCLE_ROUNDED,
                size=16,
                color=ft.Colors.GREY_400,
            )

        bal = state["balance"]
        curr = state["currency"]
        appbar_balance_chip.label = ft.Text(
            f"Saldo: {format_currency(bal, curr)}",
            size=11,
            weight=ft.FontWeight.BOLD,
        )

        appbar_clock_chip.label = ft.Text(
            f"UTC: {state.get('server_time_utc', '--:--:--')}",
            size=11,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.CYAN_100,
        )
        if state.get("is_authenticated", False):
            appbar_session_chip.bgcolor = ft.Colors.AMBER_900
            appbar_session_chip.label = ft.Text(
                f"Sessão: {state.get('tempo_logado_str', '--')}",
                size=11,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.AMBER_100,
            )
        else:
            appbar_session_chip.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGHEST
            appbar_session_chip.label = ft.Text("Sessão: --", size=11, color=ft.Colors.GREY_400)

        page.update()

    # =========================================================================
    # VIEW 1: DASHBOARD GERAL
    # =========================================================================
    dash_balance_text = ft.Text(
        format_currency(0.0),
        size=26,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.GREEN_400,
    )
    dash_account_id_text = ft.Text("Titular: Standby | ID: --", size=12, color=ft.Colors.GREY_400)
    dash_account_badge = ft.Container(
        content=ft.Text("Standby", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_300),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        border_radius=4,
        padding=ft.padding.Padding(6, 2, 6, 2),
    )
    dash_ws_text = ft.Text("Desconectado", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400)
    from core.config import settings
    dash_ws_subtext = ft.Text(f"App ID: {settings.deriv_app_id} | Options WS", size=12, color=ft.Colors.GREY_400)
    dash_backend_text = ft.Text("Detectando...", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_400)
    dash_backend_subtext = ft.Text("SQLite: trading_memory.db", size=12, color=ft.Colors.GREY_400)
    dash_session_profit_text = ft.Text("USD +0.00", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    dash_session_subtext = ft.Text("0 ciclos | 0W - 0L", size=12, color=ft.Colors.GREY_400)

    # Controles de Sincronização Temporal e Tempo Logado
    dash_server_time_text = ft.Text(
        "--:--:-- UTC",
        size=22,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.CYAN_300,
    )
    dash_tempo_logado_text = ft.Text(
        "--",
        size=22,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.AMBER_300,
    )
    dash_sync_interval_text = ft.Text(
        "Sincronização: a cada 5.0m (300s)",
        size=11,
        color=ft.Colors.GREY_400,
    )
    dash_session_start_text = ft.Text(
        "Sessão: Não iniciada",
        size=11,
        color=ft.Colors.GREY_400,
    )
    dash_session_badge = ft.Container(
        content=ft.Text("Standby", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_300),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        border_radius=4,
        padding=ft.padding.Padding(6, 2, 6, 2),
    )

    # Controles da Aba de Ajustes (Settings)
    from services.time_operations import time_operations

    settings_interval_dropdown = ft.Dropdown(
        label="Intervalo de Atualização do Tempo Logado",
        options=[
            ft.DropdownOption("60", "1 Minuto (60s)"),
            ft.DropdownOption("180", "3 Minutos (180s)"),
            ft.DropdownOption("300", "5 Minutos (300s) — Padrão"),
            ft.DropdownOption("600", "10 Minutos (600s)"),
            ft.DropdownOption("900", "15 Minutos (900s)"),
        ],
        value="300",
        width=380,
    )
    settings_interval_badge = ft.Text(
        "Intervalo Atual: 5.0 min (300s)",
        size=13,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.CYAN_300,
    )
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
        srv_time = state.get("server_time_utc", "--:--:-- UTC")
        srv_full = state.get("server_time_full_utc", "--")
        t_logado = state.get("tempo_logado_str", "--")

        appbar_clock_chip.label = ft.Text(
            f"UTC: {srv_time}",
            size=11,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.CYAN_100,
        )
        dash_server_time_text.value = srv_time
        settings_server_time_detail.value = f"Relógio Deriv (UTC): {srv_full or srv_time}"

        if state.get("is_authenticated") and time_operations.is_logged_in:
            appbar_session_chip.bgcolor = ft.Colors.AMBER_900
            appbar_session_chip.label = ft.Text(
                f"Sessão: {t_logado}",
                size=11,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.AMBER_100,
            )
            dash_tempo_logado_text.value = t_logado
            dash_session_badge.content = ft.Text(
                "Sessão Ativa",
                size=10,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.GREEN_200,
            )
            dash_session_badge.bgcolor = ft.Colors.GREEN_900
            settings_tempo_logado_detail.value = f"Duração Acumulada: {t_logado}"

            if time_operations.inicio_sessao_utc:
                dt_str = time_operations.inicio_sessao_utc.strftime("%H:%M:%S UTC")
                dt_full = time_operations.inicio_sessao_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
                dash_session_start_text.value = f"Início: {dt_str}"
                settings_session_start_detail.value = f"Início da Sessão: {dt_full}"
        else:
            appbar_session_chip.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGHEST
            appbar_session_chip.label = ft.Text("Sessão: --", size=11, color=ft.Colors.GREY_400)
            dash_tempo_logado_text.value = "--"
            dash_session_badge.content = ft.Text(
                "Standby",
                size=10,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.GREY_400,
            )
            dash_session_badge.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGH
            dash_session_start_text.value = "Sessão: Não iniciada"
            settings_session_start_detail.value = "Início da Sessão: Não autenticado"
            settings_tempo_logado_detail.value = "Duração Acumulada: --"

        sec = int(time_operations.tempo_atualizacao)
        mins = sec / 60.0
        dash_sync_interval_text.value = f"Sincronização: a cada {mins:.1f}m ({sec}s)"
        settings_interval_badge.value = f"Intervalo Atual: {mins:.1f} min ({sec}s)"
        page.update()

    sync_trigger_event = asyncio.Event()

    async def on_interval_dropdown_change(e: Any = None) -> None:
        try:
            val_sec = float(settings_interval_dropdown.value or "300")
            time_operations.tempo_atualizacao = val_sec
            state["tempo_atualizacao"] = val_sec
            mins = val_sec / 60.0
            log_event(
                f"Intervalo de atualização do tempo logado alterado para {mins:.1f} min ({int(val_sec)}s).",
                "INFO",
            )
            notify(f"Intervalo de sincronização ajustado para {mins:.1f} min!")
            sync_trigger_event.set()
            update_time_displays()
        except Exception as exc:
            log_event(f"Erro ao alterar intervalo: {exc}", "ERROR")
            notify(f"Erro ao alterar intervalo: {exc}", is_error=True)

    async def action_sync_server_time(e: Any = None) -> None:
        log_event("Sincronizando relógio oficial Deriv via WebSocket...", "INFO")
        try:
            res = await time_operations.get_server_time(api_client)
            dt_utc = res.get("datetime_utc")
            if dt_utc:
                state["server_time_utc"] = dt_utc.strftime("%H:%M:%S UTC")
                state["server_time_full_utc"] = res.get("formatted", "")
            update_time_displays()
            log_event(
                f"Relógio Deriv sincronizado: {res.get('formatted')} (Epoch: {res.get('epoch')})",
                "SUCCESS",
            )
            notify("Relógio Deriv sincronizado com sucesso!")
        except Exception as exc:
            log_event(f"Erro ao sincronizar relógio: {exc}", "WARNING")
            notify(f"Erro ao sincronizar relógio: {exc}", is_error=True)

    async def action_restore_default_interval(e: Any = None) -> None:
        settings_interval_dropdown.value = "300"
        await on_interval_dropdown_change()

    settings_interval_dropdown.on_change = lambda e: page.run_task(
        lambda: on_interval_dropdown_change(e)
    )

    async def server_time_and_session_loop() -> None:
        """Loop contínuo em background para sincronização temporal e tempo logado."""
        last_sync_time = 0.0
        while True:
            try:
                now_mono = asyncio.get_event_loop().time()
                current_interval = float(time_operations.tempo_atualizacao)

                if (now_mono - last_sync_time) >= current_interval or last_sync_time == 0.0:
                    try:
                        res = await time_operations.get_server_time(api_client)
                        dt_utc = res.get("datetime_utc")
                        if dt_utc:
                            state["server_time_utc"] = dt_utc.strftime("%H:%M:%S UTC")
                            state["server_time_full_utc"] = res.get("formatted", "")
                        last_sync_time = now_mono
                    except Exception as exc:
                        logger.debug(f"Erro ao sincronizar tempo com Deriv: {exc}")

                if state.get("is_authenticated") and time_operations.is_logged_in:
                    state["tempo_logado_str"] = time_operations.format_tempo_logado()
                else:
                    state["tempo_logado_str"] = "--"

                update_time_displays()
            except Exception as exc:
                logger.debug(f"Exceção no loop temporal: {exc}")

            try:
                await asyncio.wait_for(sync_trigger_event.wait(), timeout=1.0)
                sync_trigger_event.clear()
                last_sync_time = 0.0
            except asyncio.TimeoutError:
                pass

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

            dash_balance_text.value = format_currency(state["balance"], state["currency"])
            dash_account_id_text.value = f"Titular: {state['fullname']} | ID: {state['loginid']}"
            dash_ws_text.value = "Conectado"
            dash_ws_text.color = ft.Colors.GREEN_400
            dash_backend_text.value = "FastAPI :8000" if api_client.mode == "api" else "Serviços Diretos"

            if state["is_virtual"]:
                dash_account_badge.content = ft.Text(
                    "Conta Demo (Virtual)",
                    size=10,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.TEAL_200,
                )
                dash_account_badge.bgcolor = ft.Colors.TEAL_900
            else:
                dash_account_badge.content = ft.Text(
                    "Conta Real",
                    size=10,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.AMBER_200,
                )
                dash_account_badge.bgcolor = ft.Colors.AMBER_900

            dash_ws_subtext.value = f"App ID: {settings.deriv_app_id} | Options WS"
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
            dash_ws_text.value = "Falha Auth"
            dash_ws_text.color = ft.Colors.RED_400
            dash_account_badge.content = ft.Text(
                "Não Autenticado",
                size=10,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.RED_200,
            )
            dash_account_badge.bgcolor = ft.Colors.RED_900
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

            dash_balance_text.value = format_currency(state["balance"], state["currency"])
            if state["fullname"] and state["fullname"] != "--":
                dash_account_id_text.value = f"Titular: {state['fullname']} | ID: {state['loginid']}"
            else:
                dash_account_id_text.value = f"Conta: {state['loginid']} (Ativa)"
            dash_ws_text.value = "Conectado"
            dash_ws_text.color = ft.Colors.GREEN_400
            dash_backend_text.value = "FastAPI :8000" if api_client.mode == "api" else "Serviços Diretos"

            update_header_status()
            log_event(
                f"Saldo atualizado: {format_currency(state['balance'], state['currency'])} (ID: {state['loginid']})",
                "SUCCESS",
            )
            notify(f"Saldo atualizado: {format_currency(state['balance'], state['currency'])}")
        except Exception as exc:
            state["ws_connected"] = False
            dash_ws_text.value = "Falha de Conexão"
            dash_ws_text.color = ft.Colors.RED_400
            update_header_status()
            log_event(f"Erro ao consultar saldo: {exc}", "ERROR")
            notify(f"Erro ao consultar saldo: {exc}", is_error=True)

    async def action_ping_deriv(e: Any = None) -> None:
        log_event("Enviando requisição de ping à Deriv API...", "INFO")
        try:
            await api_client.get_symbols(synthetic_only=True)
            state["ws_connected"] = True
            dash_ws_text.value = "Conectado"
            dash_ws_text.color = ft.Colors.GREEN_400
            update_header_status()
            log_event("Comunicação com Deriv estabelecida com sucesso.", "SUCCESS")
            notify("Deriv WebSocket respondendo normalmente.")
        except Exception as exc:
            state["ws_connected"] = False
            dash_ws_text.value = "Desconectado"
            dash_ws_text.color = ft.Colors.RED_400
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
        kpi_row = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(
                                                ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                                                color=ft.Colors.GREEN_400,
                                                size=24,
                                            ),
                                            ft.Text(
                                                "Saldo & Conta",
                                                size=13,
                                                weight=ft.FontWeight.W_500,
                                                color=ft.Colors.GREY_300,
                                            ),
                                        ],
                                        spacing=6,
                                    ),
                                    dash_account_badge,
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            dash_balance_text,
                            dash_account_id_text,
                        ],
                        spacing=6,
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    padding=16,
                    border_radius=12,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.WIFI_ROUNDED, color=ft.Colors.CYAN_400, size=24),
                                    ft.Text("Deriv WebSocket", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_300),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            dash_ws_text,
                            dash_ws_subtext,
                        ],
                        spacing=6,
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    padding=16,
                    border_radius=12,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.HUB_ROUNDED, color=ft.Colors.PURPLE_300, size=24),
                                    ft.Text("Arquitetura Backend", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_300),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            dash_backend_text,
                            dash_backend_subtext,
                        ],
                        spacing=6,
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    padding=16,
                    border_radius=12,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.INSIGHTS_ROUNDED, color=ft.Colors.AMBER_400, size=24),
                                    ft.Text("Sessão do Bot", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_300),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            dash_session_profit_text,
                            dash_session_subtext,
                        ],
                        spacing=6,
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    padding=16,
                    border_radius=12,
                    expand=True,
                ),
            ],
            spacing=16,
        )

        time_sync_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.ACCESS_TIME_ROUNDED, color=ft.Colors.CYAN_400, size=22),
                                    ft.Text("Sincronização Temporal & Sessão Ativa", size=15, weight=ft.FontWeight.BOLD),
                                ],
                                spacing=8,
                            ),
                            ft.Row(
                                [
                                    dash_session_badge,
                                    ft.OutlinedButton(
                                        "Sincronizar Relógio",
                                        icon=ft.Icons.SYNC_ROUNDED,
                                        on_click=action_sync_server_time,
                                    ),
                                    ft.OutlinedButton(
                                        "Configurar Intervalo",
                                        icon=ft.Icons.SETTINGS_ROUNDED,
                                        on_click=lambda _: switch_tab(3),
                                    ),
                                ],
                                spacing=8,
                                wrap=True,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                    ),
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text("Relógio Oficial Deriv (UTC)", size=12, color=ft.Colors.GREY_400),
                                        dash_server_time_text,
                                        dash_sync_interval_text,
                                    ],
                                    spacing=2,
                                ),
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text("Tempo Logado na Sessão", size=12, color=ft.Colors.GREY_400),
                                        dash_tempo_logado_text,
                                        dash_session_start_text,
                                    ],
                                    spacing=2,
                                ),
                                expand=True,
                            ),
                        ],
                        spacing=16,
                    ),
                ],
                spacing=12,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=16,
            border_radius=12,
        )

        live_ticker_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.STREAM_ROUNDED,
                                        color=ft.Colors.CYAN_400,
                                        size=22,
                                    ),
                                    ft.Text(
                                        "Monitor de Ticks em Tempo Real",
                                        size=15,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    dash_live_symbol_chip,
                                ],
                                spacing=8,
                            ),
                            ft.Row(
                                [
                                    dash_live_status_badge,
                                    ft.IconButton(
                                        icon=ft.Icons.SYNC_ROUNDED,
                                        tooltip="Reconectar Stream de Ticks",
                                        on_click=lambda _: page.run_task(
                                            lambda: set_active_subscription(state["selected_symbol"])
                                        ),
                                    ),
                                ],
                                spacing=6,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    dash_live_price_text,
                                    ft.Row(
                                        [
                                            dash_live_diff_icon,
                                            dash_live_diff_text,
                                            dash_live_time_text,
                                        ],
                                        spacing=6,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                ],
                                spacing=2,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            "Últimos Ticks (Tendência)",
                                            size=10,
                                            weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.GREY_400,
                                        ),
                                        dash_ticks_sparkline_row,
                                    ],
                                    spacing=4,
                                    alignment=ft.MainAxisAlignment.END,
                                ),
                                padding=ft.padding.Padding(0, 0, 8, 0),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=10,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=16,
            border_radius=12,
        )

        quick_actions_card = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Painel de Controle Rápido", size=15, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            ft.FilledButton(
                                "Autenticar Conta",
                                icon=ft.Icons.LOCK_OPEN_ROUNDED,
                                on_click=action_authenticate,
                            ),
                            ft.FilledButton(
                                "Consultar Saldo",
                                icon=ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                                on_click=action_fetch_balance,
                            ),
                            ft.OutlinedButton(
                                "Testar Ping Deriv",
                                icon=ft.Icons.NETWORK_CHECK_ROUNDED,
                                on_click=action_ping_deriv,
                            ),
                            ft.OutlinedButton(
                                "Sincronizar Cache de Símbolos",
                                icon=ft.Icons.SYNC_ROUNDED,
                                on_click=action_sync_cache,
                            ),
                            ft.FilledButton(
                                "Ir para Bot Autônomo",
                                icon=ft.Icons.ROCKET_LAUNCH_ROUNDED,
                                bgcolor=ft.Colors.CYAN_700,
                                on_click=lambda _: switch_tab(2),
                            ),
                        ],
                        spacing=12,
                        wrap=True,
                    ),
                ],
                spacing=12,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=16,
            border_radius=12,
        )

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
                        height=280,
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
                    kpi_row,
                    time_sync_card,
                    live_ticker_card,
                    quick_actions_card,
                    log_card,
                ],
                spacing=18,
                expand=True,
            ),
            padding=20,
            expand=True,
        )

    # =========================================================================
    # VIEW 2: CATÁLOGO E COTAÇÕES EM TEMPO REAL
    # =========================================================================
    dropdown_symbol = ft.Dropdown(
        label="Ativo Sintético Selecionado",
        width=300,
        options=[
            ft.DropdownOption("1HZ100V", "Volatility 100 (1s) Index"),
            ft.DropdownOption("1HZ50V", "Volatility 50 (1s) Index"),
            ft.DropdownOption("1HZ25V", "Volatility 25 (1s) Index"),
            ft.DropdownOption("1HZ10V", "Volatility 10 (1s) Index"),
            ft.DropdownOption("1HZ75V", "Volatility 75 (1s) Index"),
            ft.DropdownOption("R_100", "Volatility 100 Index"),
            ft.DropdownOption("R_50", "Volatility 50 Index"),
            ft.DropdownOption("R_25", "Volatility 25 Index"),
            ft.DropdownOption("R_10", "Volatility 10 Index"),
            ft.DropdownOption("R_75", "Volatility 75 Index"),
        ],
        value="1HZ100V",
    )

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

    contracts_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Tipo de Contrato", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Categoria", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Duração Mínima", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Duração Máxima", weight=ft.FontWeight.BOLD)),
        ],
        rows=[],
    )

    catalog_data_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Símbolo", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Nome do Ativo", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Mercado", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Status", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Ação", weight=ft.FontWeight.BOLD)),
        ],
        rows=[],
    )

    search_catalog_input = ft.TextField(
        label="Filtrar catálogo por símbolo ou nome...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        expand=True,
    )

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
            contracts_table.rows.clear()
            for c in contracts[:10]:
                c_type = c.get("contract_type", "CALL/PUT")
                c_cat = c.get("category", "Rise/Fall")
                min_d = f"{c.get('min_duration', 5)} {c.get('min_duration_unit', 't')}"
                max_d = f"{c.get('max_duration', 365)} {c.get('max_duration_unit', 'd')}"
                contracts_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(c_type, weight=ft.FontWeight.W_500)),
                            ft.DataCell(ft.Text(c_cat)),
                            ft.DataCell(ft.Text(min_d, color=ft.Colors.GREEN_300)),
                            ft.DataCell(ft.Text(max_d, color=ft.Colors.CYAN_300)),
                        ]
                    )
                )
            page.update()
        except Exception as exc:
            log_event(f"Erro ao consultar contratos de {symbol}: {exc}", "WARNING")

    async def on_symbol_selected(e: Any = None) -> None:
        sym = dropdown_symbol.value or "1HZ100V"
        state["selected_symbol"] = sym
        dd_bot_symbol.value = sym
        log_event(f"Ativo selecionado: {sym}. Consultando cotação e contratos...", "INFO")
        if state.get("live_stream_active", True):
            await set_active_subscription(sym)
        else:
            await update_tick_view(sym)
        await load_contracts_for_symbol(sym)

    async def on_switch_live_stream_change(e: Any = None) -> None:
        active = bool(switch_live_stream.value)
        state["live_stream_active"] = active
        sym = dropdown_symbol.value or state["selected_symbol"]
        if active:
            log_event(f"Reativando stream contínuo de ticks para {sym}...", "INFO")
            await set_active_subscription(sym)
        else:
            log_event("Stream contínuo de ticks pausado pelo usuário.", "INFO")
            await api_client.unsubscribe_all_ticks()
            dash_live_status_badge.content = ft.Text(
                "● PAUSADO",
                size=10,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.AMBER_200,
            )
            dash_live_status_badge.bgcolor = ft.Colors.AMBER_900
            page.update()

    def filter_catalog(e: Any = None) -> None:
        query = (search_catalog_input.value or "").strip().lower()
        all_syms = state.get("symbols_list", [])
        catalog_data_table.rows.clear()
        filtered = [
            s
            for s in all_syms
            if query in s.get("symbol", "").lower() or query in s.get("display_name", "").lower()
        ]
        for s in filtered[:25]:
            sym = s.get("symbol", "")
            name = s.get("display_name", "")
            market = s.get("market_name", "Sintético")
            is_open = s.get("is_trading_suspended", 0) == 0

            def make_select_callback(selected_s: str):
                async def _on_click(_):
                    dropdown_symbol.value = selected_s
                    state["selected_symbol"] = selected_s
                    dd_bot_symbol.value = selected_s
                    if state.get("live_stream_active", True):
                        await set_active_subscription(selected_s)
                    else:
                        await update_tick_view(selected_s)
                    await load_contracts_for_symbol(selected_s)
                    notify(f"Ativo {selected_s} carregado nas cotações e no Bot!")

                return _on_click

            catalog_data_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(sym, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_300)),
                        ft.DataCell(ft.Text(name)),
                        ft.DataCell(ft.Text(market)),
                        ft.DataCell(
                            ft.Text(
                                "Aberto" if is_open else "Suspenso",
                                color=ft.Colors.GREEN_400 if is_open else ft.Colors.RED_400,
                            )
                        ),
                        ft.DataCell(
                            ft.OutlinedButton(
                                "Selecionar",
                                on_click=make_select_callback(sym),
                            )
                        ),
                    ]
                )
            )
        page.update()

    async def load_symbols_into_ui() -> None:
        try:
            syms = await api_client.get_symbols(synthetic_only=True)
            state["symbols_list"] = syms
            if syms:
                dropdown_symbol.options = [
                    ft.DropdownOption(s["symbol"], f"{s['display_name']} ({s['symbol']})")
                    for s in syms
                ]
                dd_bot_symbol.options = dropdown_symbol.options
            filter_catalog()
        except Exception as exc:
            log_event(f"Erro ao carregar catálogo de símbolos: {exc}", "WARNING")

    search_catalog_input.on_change = filter_catalog
    dropdown_symbol.on_change = on_symbol_selected
    switch_live_stream.on_change = lambda e: page.run_task(lambda: on_switch_live_stream_change(e))

    def build_catalog_view() -> ft.Control:
        quote_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    dropdown_symbol,
                                    ft.FilledButton(
                                        "Atualizar Tick",
                                        icon=ft.Icons.REFRESH_ROUNDED,
                                        on_click=on_symbol_selected,
                                    ),
                                ],
                                spacing=12,
                            ),
                            ft.Row(
                                [
                                    switch_live_stream,
                                    ft.FilledButton(
                                        "Usar no Bot",
                                        icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                                        bgcolor=ft.Colors.CYAN_700,
                                        on_click=lambda _: switch_tab(2),
                                    ),
                                ],
                                spacing=12,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                    ),
                    ft.Divider(height=1),
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            tick_symbol_badge,
                                            ft.Text("Cotação em Tempo Real", size=13, color=ft.Colors.GREY_400),
                                        ],
                                        spacing=8,
                                    ),
                                    ft.Row(
                                        [
                                            tick_price_display,
                                            tick_diff_icon,
                                        ],
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        spacing=10,
                                    ),
                                    tick_time_text,
                                ],
                                spacing=4,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                    ),
                ],
                spacing=14,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=16,
            border_radius=12,
        )

        contracts_card = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Contratos & Durações Suportadas", size=15, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=contracts_table,
                        height=190,
                    ),
                ],
                spacing=8,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=16,
            border_radius=12,
        )

        catalog_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("Catálogo de Ativos Sintéticos Deriv", size=15, weight=ft.FontWeight.BOLD),
                            search_catalog_input,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        spacing=16,
                    ),
                    ft.Container(
                        content=catalog_data_table,
                        height=280,
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
                            ft.Text("Catálogo e Cotações", size=22, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Monitore preços de ticks em tempo real e explore parâmetros de contratos dos índices sintéticos.",
                                size=13,
                                color=ft.Colors.GREY_400,
                            ),
                        ],
                        spacing=2,
                    ),
                    quote_card,
                    contracts_card,
                    catalog_card,
                ],
                spacing=16,
                expand=True,
            ),
            padding=20,
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

            # Atualização das métricas da sessão no dashboard
            dash_session_subtext.value = (
                f"{state['session_cycles']} ciclos | {state['session_wins']}W - {state['session_losses']}L"
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
        interval_config_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.TUNE_ROUNDED, size=22, color=ft.Colors.CYAN_300),
                                    ft.Text(
                                        "Intervalo de Atualização do Tempo Logado",
                                        size=16,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                ],
                                spacing=8,
                            ),
                            settings_interval_badge,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                    ),
                    ft.Text(
                        "Frequência periódica de sincronização do relógio oficial da Deriv API (UTC) e recálculo da sessão ativa.",
                        size=13,
                        color=ft.Colors.GREY_400,
                    ),
                    ft.Divider(height=1),
                    ft.Row(
                        [
                            settings_interval_dropdown,
                            ft.FilledButton(
                                "Restaurar Padrão (5m)",
                                icon=ft.Icons.RESTORE_ROUNDED,
                                on_click=action_restore_default_interval,
                            ),
                            ft.FilledButton(
                                "Sincronizar Agora",
                                icon=ft.Icons.SYNC_ROUNDED,
                                bgcolor=ft.Colors.CYAN_700,
                                on_click=action_sync_server_time,
                            ),
                        ],
                        spacing=12,
                        wrap=True,
                    ),
                ],
                spacing=14,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=20,
            border_radius=12,
        )

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
                                "Gerencie os parâmetros temporais, frequência de atualização em tempo real e preferências operacionais.",
                                size=13,
                                color=ft.Colors.GREY_400,
                            ),
                        ],
                        spacing=2,
                    ),
                    interval_config_card,
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
        leading=ft.Icon(ft.Icons.AUTO_GRAPH_ROUNDED, color=ft.Colors.CYAN_400, size=28),
        leading_width=48,
        title=ft.Row(
            [
                ft.Text("Deriv Quantum Trading Bot", size=18, weight=ft.FontWeight.BOLD),
                ft.Text("• IA & Ichimoku Dinâmico", size=13, color=ft.Colors.GREY_400),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        center_title=False,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        actions=[
            ft.Row(
                [
                    appbar_api_mode,
                    appbar_ws_status,
                    appbar_clock_chip,
                    appbar_session_chip,
                    appbar_account_chip,
                    appbar_balance_chip,
                    ft.IconButton(
                        icon=ft.Icons.REFRESH_ROUNDED,
                        tooltip="Atualizar Saldo e Status",
                        on_click=action_fetch_balance,
                    ),
                ],
                spacing=10,
            ),
            ft.Container(width=12),
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
