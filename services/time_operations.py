"""Módulo de Operações Temporais, Sincronização com Deriv e Controle de Sessão.

Utiliza a biblioteca nativa datetime com tratamento rigoroso de fuso horário (timezone.utc).
Fornece controle de tempo logado, relógio oficial do servidor Deriv e configuração
dinâmica da frequência de sincronização (tempo_atualizacao, default: 300s / 5 min).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

logger = logging.getLogger("services.time_operations")

DEFAULT_TEMPO_ATUALIZACAO: float = 300.0  # 5 minutos (300 segundos)


class TimeOperations:
    """Gerenciador de sincronização temporal e métricas de sessão da Deriv."""

    def __init__(
        self,
        service: Any = None,
        default_tempo_atualizacao: float = DEFAULT_TEMPO_ATUALIZACAO,
    ) -> None:
        self.service = service
        self._login_time_utc: datetime | None = None
        self._tempo_atualizacao: float = float(default_tempo_atualizacao)
        self._last_server_time_utc: datetime | None = None
        self._last_server_epoch: int | None = None
        self._change_listeners: list[Callable[[float], Any]] = []

    # -------------------------------------------------------------------------
    # Propriedade Dinâmica: tempo_atualizacao
    # -------------------------------------------------------------------------
    @property
    def tempo_atualizacao(self) -> float:
        """Frequência de sincronização em segundos (default: 300s = 5 minutos)."""
        return self._tempo_atualizacao

    @tempo_atualizacao.setter
    def tempo_atualizacao(self, value: float | int) -> None:
        """Altera a frequência de atualização em tempo de execução."""
        val = float(value)
        if val <= 0:
            raise ValueError(
                "O intervalo de atualização (tempo_atualizacao) deve ser maior que zero."
            )
        old_val = self._tempo_atualizacao
        self._tempo_atualizacao = val
        logger.info(
            f"Frequência de atualização alterada: {old_val:.1f}s -> {self._tempo_atualizacao:.1f}s "
            f"({self._tempo_atualizacao / 60.0:.2f} min)"
        )
        self._notify_listeners(val)

    @property
    def tempo_atualizacao_minutos(self) -> float:
        """Frequência de sincronização em minutos."""
        return self._tempo_atualizacao / 60.0

    @tempo_atualizacao_minutos.setter
    def tempo_atualizacao_minutos(self, minutes: float | int) -> None:
        """Altera a frequência de atualização fornecendo valor em minutos."""
        self.tempo_atualizacao = float(minutes) * 60.0

    def add_listener(self, listener: Callable[[float], Any]) -> None:
        """Registra callback notificado na alteração de tempo_atualizacao."""
        if listener not in self._change_listeners:
            self._change_listeners.append(listener)

    def remove_listener(self, listener: Callable[[float], Any]) -> None:
        """Remove callback registrado."""
        if listener in self._change_listeners:
            self._change_listeners.remove(listener)

    def _notify_listeners(self, new_value: float) -> None:
        for listener in list(self._change_listeners):
            try:
                res = listener(new_value)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception as exc:
                logger.warning(f"Erro ao executar listener de tempo_atualizacao: {exc}")

    # -------------------------------------------------------------------------
    # Controle: tempo_logado / Sessão Ativa
    # -------------------------------------------------------------------------
    def register_login(self, login_dt: datetime | None = None) -> datetime:
        """Registra o timestamp UTC da autenticação bem-sucedida."""
        if login_dt is None:
            self._login_time_utc = datetime.now(timezone.utc)
        else:
            if login_dt.tzinfo is None:
                self._login_time_utc = login_dt.replace(tzinfo=timezone.utc)
            else:
                self._login_time_utc = login_dt.astimezone(timezone.utc)

        logger.info(
            f"Login registrado em UTC: {self._login_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        return self._login_time_utc

    def reset_login(self) -> None:
        """Reseta o timestamp de início da sessão."""
        self._login_time_utc = None

    @property
    def inicio_sessao_utc(self) -> datetime | None:
        """Retorna o datetime UTC de início da sessão autenticada, ou None."""
        return self._login_time_utc

    @property
    def is_logged_in(self) -> bool:
        """Verifica se há sessão autenticada ativa."""
        return self._login_time_utc is not None

    def get_tempo_logado(self, current_dt: datetime | None = None) -> timedelta | None:
        """Calcula a diferença acumulada de sessão como timedelta (agora_utc - inicio_sessao_utc)."""
        if self._login_time_utc is None:
            return None
        now_utc = current_dt or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        else:
            now_utc = now_utc.astimezone(timezone.utc)

        diff = now_utc - self._login_time_utc
        if diff.total_seconds() < 0:
            return timedelta(seconds=0)
        return diff

    def format_tempo_logado(self, current_dt: datetime | None = None) -> str:
        """Formata o tempo logado no formato canônico '01h 25m 43s'."""
        td = self.get_tempo_logado(current_dt)
        if td is None:
            return "--"
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"

    # -------------------------------------------------------------------------
    # Relógio do Servidor Deriv (UTC)
    # -------------------------------------------------------------------------
    async def get_server_time(self, service: Any = None) -> dict[str, Any]:
        """Consulta o relógio oficial do servidor Deriv via WebSocket ('{"time": 1}').

        Converte o Epoch retornado em um objeto datetime UTC e string formatada
        ('YYYY-MM-DD HH:MM:SS UTC').
        """
        active_service = service or self.service
        if active_service is None:
            from api.deps import deriv_service

            active_service = deriv_service

        epoch_raw = await active_service.get_server_time()
        if isinstance(epoch_raw, dict):
            epoch_val = int(epoch_raw.get("epoch", epoch_raw.get("time", 0)))
        else:
            epoch_val = int(epoch_raw)

        dt_utc = datetime.fromtimestamp(epoch_val, tz=timezone.utc)
        formatted = dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

        self._last_server_epoch = epoch_val
        self._last_server_time_utc = dt_utc

        return {
            "epoch": epoch_val,
            "datetime_utc": dt_utc,
            "formatted": formatted,
        }

    @property
    def last_server_time_utc(self) -> datetime | None:
        """Último datetime UTC retornado pelo servidor Deriv."""
        return self._last_server_time_utc

    @property
    def last_server_epoch(self) -> int | None:
        """Último timestamp Epoch retornado pelo servidor Deriv."""
        return self._last_server_epoch

    # -------------------------------------------------------------------------
    # Utilitários Estáticos
    # -------------------------------------------------------------------------
    @staticmethod
    def epoch_to_utc_datetime(epoch: int | float) -> datetime:
        """Converte epoch para datetime com timezone.utc explícito."""
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc)

    @staticmethod
    def format_utc_datetime(dt: datetime) -> str:
        """Formata qualquer datetime para string 'YYYY-MM-DD HH:MM:SS UTC'."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    @staticmethod
    def format_seconds_duration(seconds: float | int) -> str:
        """Formata segundos em '00h 00m 00s'."""
        total = max(0, int(seconds))
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}h {m:02d}m {s:02d}s"


# Instância global padrão
time_operations = TimeOperations()

__all__ = [
    "TimeOperations",
    "time_operations",
    "DEFAULT_TEMPO_ATUALIZACAO",
]

