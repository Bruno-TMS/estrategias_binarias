"""Testes unitários dedicados para o módulo de operações temporais e sincronização com a Deriv API."""

import asyncio
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from main import app
from services.deriv_service import DerivService
from services.time_operations import (
    DEFAULT_TEMPO_ATUALIZACAO,
    TimeOperations,
    time_operations,
)
import utils.time_operations as utils_time_ops
import deriv.modulo_grafico as modulo_grafico


class TestTimeOperationsUnit(unittest.IsolatedAsyncioTestCase):
    """Testes unitários dos métodos de cálculo, formatação e controle de sessão do TimeOperations."""

    def setUp(self) -> None:
        self.time_ops = TimeOperations()

    def tearDown(self) -> None:
        self.time_ops.reset_login()

    def test_default_values(self) -> None:
        """Verifica os valores padrão na inicialização do serviço."""
        self.assertEqual(self.time_ops.tempo_atualizacao, DEFAULT_TEMPO_ATUALIZACAO)
        self.assertEqual(self.time_ops.tempo_atualizacao, 300.0)
        self.assertEqual(self.time_ops.tempo_atualizacao_minutos, 5.0)
        self.assertIsNone(self.time_ops.inicio_sessao_utc)
        self.assertFalse(self.time_ops.is_logged_in)
        self.assertIsNone(self.time_ops.get_tempo_logado())
        self.assertEqual(self.time_ops.format_tempo_logado(), "--")
        self.assertIsNone(self.time_ops.last_server_time_utc)
        self.assertIsNone(self.time_ops.last_server_epoch)

    def test_tempo_atualizacao_setter_and_getter(self) -> None:
        """Testa a alteração dinâmica da frequência de atualização em segundos e minutos."""
        # Alteração em segundos
        self.time_ops.tempo_atualizacao = 60.0
        self.assertEqual(self.time_ops.tempo_atualizacao, 60.0)
        self.assertEqual(self.time_ops.tempo_atualizacao_minutos, 1.0)

        # Alteração em minutos
        self.time_ops.tempo_atualizacao_minutos = 10.0
        self.assertEqual(self.time_ops.tempo_atualizacao, 600.0)
        self.assertEqual(self.time_ops.tempo_atualizacao_minutos, 10.0)

        # Validação de valor inválido <= 0
        with self.assertRaises(ValueError):
            self.time_ops.tempo_atualizacao = 0

        with self.assertRaises(ValueError):
            self.time_ops.tempo_atualizacao = -30

        with self.assertRaises(ValueError):
            self.time_ops.tempo_atualizacao_minutos = -1

    def test_listeners_notification(self) -> None:
        """Testa o registro e disparo de callbacks (síncronos e assíncronos) na alteração de frequência."""
        recorded_values: list[float] = []

        def sync_listener(new_val: float) -> None:
            recorded_values.append(new_val)

        self.time_ops.add_listener(sync_listener)
        self.time_ops.tempo_atualizacao = 120.0
        self.assertEqual(recorded_values, [120.0])

        # Remover listener
        self.time_ops.remove_listener(sync_listener)
        self.time_ops.tempo_atualizacao = 180.0
        self.assertEqual(recorded_values, [120.0])

        # Listener com falha não interrompe a alteração
        def failing_listener(val: float) -> None:
            raise RuntimeError("Falha simulada no listener")

        self.time_ops.add_listener(failing_listener)
        self.time_ops.tempo_atualizacao = 240.0
        self.assertEqual(self.time_ops.tempo_atualizacao, 240.0)

    def test_session_lifecycle_and_utc_formatting(self) -> None:
        """Testa o ciclo de vida do login, cálculo de tempo logado e formatação canônica HHh MMm SSs."""
        base_login = datetime(2026, 10, 3, 10, 0, 0, tzinfo=timezone.utc)
        registered = self.time_ops.register_login(base_login)
        self.assertEqual(registered, base_login)
        self.assertTrue(self.time_ops.is_logged_in)
        self.assertEqual(self.time_ops.inicio_sessao_utc, base_login)

        # Simula 1 hora, 25 minutos e 43 segundos após o login
        simulated_now = base_login + timedelta(hours=1, minutes=25, seconds=43)
        diff = self.time_ops.get_tempo_logado(simulated_now)
        self.assertIsNotNone(diff)
        self.assertEqual(int(diff.total_seconds()), 3600 + 25 * 60 + 43)

        formatted = self.time_ops.format_tempo_logado(simulated_now)
        self.assertEqual(formatted, "01h 25m 43s")

        # Teste com naive datetime convertido automaticamente para UTC
        naive_now = datetime(2026, 10, 3, 10, 5, 12)
        diff_naive = self.time_ops.get_tempo_logado(naive_now)
        self.assertEqual(self.time_ops.format_tempo_logado(naive_now), "00h 05m 12s")

        # Se simulated_now for anterior ao login (skew de relógio), clamp para zero
        past_now = base_login - timedelta(seconds=10)
        self.assertEqual(self.time_ops.format_tempo_logado(past_now), "00h 00m 00s")

        # Reset do login
        self.time_ops.reset_login()
        self.assertFalse(self.time_ops.is_logged_in)
        self.assertIsNone(self.time_ops.inicio_sessao_utc)
        self.assertEqual(self.time_ops.format_tempo_logado(), "--")

    def test_register_login_default_and_naive(self) -> None:
        """Testa registro com valor default (now) e com naive datetime."""
        # Naive datetime
        naive_dt = datetime(2026, 1, 1, 12, 0, 0)
        reg_naive = self.time_ops.register_login(naive_dt)
        self.assertEqual(reg_naive.tzinfo, timezone.utc)
        self.assertEqual(reg_naive.year, 2026)

        # Default now(timezone.utc)
        reg_default = self.time_ops.register_login()
        self.assertIsNotNone(reg_default.tzinfo)
        self.assertEqual(reg_default.tzinfo, timezone.utc)

    async def test_get_server_time_with_mock_service(self) -> None:
        """Testa consulta assíncrona ao tempo do servidor Deriv e preenchimento de campos."""
        mock_service = AsyncMock()
        # Epoch para 2024-10-03 12:00:00 UTC = 1727956800
        mock_service.get_server_time.return_value = 1727956800

        result = await self.time_ops.get_server_time(service=mock_service)
        self.assertEqual(result["epoch"], 1727956800)
        self.assertEqual(result["datetime_utc"], datetime(2024, 10, 3, 12, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(result["formatted"], "2024-10-03 12:00:00 UTC")
        self.assertEqual(self.time_ops.last_server_epoch, 1727956800)
        self.assertEqual(self.time_ops.last_server_time_utc, datetime(2024, 10, 3, 12, 0, 0, tzinfo=timezone.utc))

        # Teste com serviço retornando dict {'epoch': ...} ou {'time': ...}
        mock_service.get_server_time.return_value = {"time": 1727956810}
        res_dict = await self.time_ops.get_server_time(service=mock_service)
        self.assertEqual(res_dict["epoch"], 1727956810)

    def test_static_helpers(self) -> None:
        """Testa métodos estáticos de conversão e formatação."""
        dt = TimeOperations.epoch_to_utc_datetime(1727956800)
        self.assertEqual(dt.tzinfo, timezone.utc)
        self.assertEqual(TimeOperations.format_utc_datetime(dt), "2024-10-03 12:00:00 UTC")

        # Naive datetime
        naive = datetime(2026, 5, 10, 8, 30, 0)
        self.assertEqual(TimeOperations.format_utc_datetime(naive), "2026-05-10 08:30:00 UTC")

        # Duração em segundos
        self.assertEqual(TimeOperations.format_seconds_duration(3665), "01h 01m 05s")
        self.assertEqual(TimeOperations.format_seconds_duration(0), "00h 00m 00s")
        self.assertEqual(TimeOperations.format_seconds_duration(-10), "00h 00m 00s")


class TestDerivServiceTimeIntegration(unittest.IsolatedAsyncioTestCase):
    """Testes para o método get_server_time e hooks de sessão em DerivService."""

    async def test_get_server_time_success(self) -> None:
        """Testa DerivService.get_server_time retornando epoch corretamente."""
        service = DerivService()
        service.client = MagicMock()
        service.client.is_alive = True
        service.send = AsyncMock(return_value={"time": 1727956850, "msg_type": "time"})

        epoch = await service.get_server_time()
        self.assertEqual(epoch, 1727956850)
        service.send.assert_awaited_once_with({"time": 1})

    async def test_get_server_time_api_error(self) -> None:
        """Testa tratamento de erro retornado pela Deriv API ao consultar tempo."""
        service = DerivService()
        service.client = MagicMock()
        service.client.is_alive = True
        service.send = AsyncMock(
            return_value={"error": {"code": "RateLimit", "message": "Too many requests"}}
        )

        with self.assertRaises(RuntimeError) as ctx:
            await service.get_server_time()
        self.assertIn("Too many requests", str(ctx.exception))

    async def test_get_server_time_missing_time_field(self) -> None:
        """Testa resposta inesperada sem o campo 'time'."""
        service = DerivService()
        service.client = MagicMock()
        service.client.is_alive = True
        service.send = AsyncMock(return_value={"msg_type": "time"})

        with self.assertRaises(RuntimeError) as ctx:
            await service.get_server_time()
        self.assertIn("Resposta inválida", str(ctx.exception))

    async def test_authorize_and_disconnect_session_hooks(self) -> None:
        """Testa se authorize registra o login e disconnect reseta o login em time_operations."""
        service = DerivService()
        service.client = MagicMock()
        service.client.is_alive = True
        service.send = AsyncMock(
            return_value={
                "authorize": {
                    "loginid": "VRTC12345",
                    "fullname": "Demo Trader",
                    "is_virtual": 1,
                    "balance": 10000.0,
                    "currency": "USD",
                    "scopes": ["read", "trade"],
                }
            }
        )

        # Garante que começa deslogado
        time_operations.reset_login()
        self.assertFalse(time_operations.is_logged_in)

        # Executa authorize
        auth_res = await service.authorize(token="dummy_token")
        self.assertEqual(auth_res["loginid"], "VRTC12345")
        self.assertTrue(time_operations.is_logged_in)
        self.assertIsNotNone(time_operations.inicio_sessao_utc)

        # Executa disconnect
        service.client.disconnect = AsyncMock()
        await service.disconnect()
        self.assertFalse(time_operations.is_logged_in)
        self.assertIsNone(time_operations.inicio_sessao_utc)


class TestApiDerivTimeRoute(unittest.TestCase):
    """Testes para o endpoint GET /deriv/time no FastAPI."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_route_registration(self) -> None:
        """Verifica se a rota /deriv/time está presente na especificação OpenAPI."""
        paths = app.openapi()["paths"]
        self.assertIn("/deriv/time", paths)
        self.assertIn("get", paths["/deriv/time"])

    @patch("api.routes.deriv.TimeOperations.get_server_time")
    def test_get_server_time_endpoint_success(self, mock_get_server_time) -> None:
        """Testa resposta 200 OK do endpoint /deriv/time."""
        mock_get_server_time.return_value = {
            "epoch": 1727956800,
            "datetime_utc": datetime(2024, 10, 3, 12, 0, 0, tzinfo=timezone.utc),
            "formatted": "2024-10-03 12:00:00 UTC",
        }

        response = self.client.get("/deriv/time")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["data"]["epoch"], 1727956800)
        self.assertEqual(body["data"]["formatted"], "2024-10-03 12:00:00 UTC")

    @patch("api.routes.deriv.TimeOperations.get_server_time")
    def test_get_server_time_endpoint_service_unavailable(self, mock_get_server_time) -> None:
        """Testa resposta 503 quando há erro de conexão na consulta de tempo."""
        mock_get_server_time.side_effect = RuntimeError("WebSocket desconectado")

        response = self.client.get("/deriv/time")
        self.assertEqual(response.status_code, 503)
        self.assertIn("WebSocket desconectado", response.json()["detail"])


class TestModuleExports(unittest.TestCase):
    """Garante que as classes e singletons estão exportados nos módulos corretos."""

    def test_utils_reexport(self) -> None:
        """Valida reexportação em utils.time_operations."""
        self.assertTrue(hasattr(utils_time_ops, "TimeOperations"))
        self.assertTrue(hasattr(utils_time_ops, "time_operations"))
        self.assertTrue(hasattr(utils_time_ops, "DEFAULT_TEMPO_ATUALIZACAO"))

    def test_modulo_grafico_reexport(self) -> None:
        """Valida reexportação em deriv.modulo_grafico."""
        self.assertTrue(hasattr(modulo_grafico, "TimeOperations"))
        self.assertTrue(hasattr(modulo_grafico, "time_operations"))


if __name__ == "__main__":
    unittest.main()

