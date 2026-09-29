"""Testes unitários para o endpoint POST /deriv/bot/auto-run."""

import unittest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from pydantic import ValidationError

from api.routes.deriv import auto_run_bot, AutoRunRequest
from main import app


class TestApiAutoRunBot(unittest.IsolatedAsyncioTestCase):
    """Testes para o ciclo autônomo de calibração e execução do DerivedBot."""

    def test_route_registration(self) -> None:
        """Verifica se a rota /deriv/bot/auto-run está registrada no OpenAPI do FastAPI."""
        paths = app.openapi()["paths"]
        self.assertIn("/deriv/bot/auto-run", paths)
        self.assertIn("post", paths["/deriv/bot/auto-run"])

    def test_request_validation(self) -> None:
        """Testa validações de esquema do AutoRunRequest."""
        # count inválido
        with self.assertRaises(ValidationError):
            AutoRunRequest(count=0)
        with self.assertRaises(ValidationError):
            AutoRunRequest(count=5001)

        # duration_ticks inválido
        with self.assertRaises(ValidationError):
            AutoRunRequest(duration_ticks=0)

        # stake inválido
        with self.assertRaises(ValidationError):
            AutoRunRequest(stake=0.0)

        # min_win_rate inválido
        with self.assertRaises(ValidationError):
            AutoRunRequest(min_win_rate=-1.0)
        with self.assertRaises(ValidationError):
            AutoRunRequest(min_win_rate=101.0)

        # Valores padrão
        valid = AutoRunRequest()
        self.assertEqual(valid.symbol, "1HZ100V")
        self.assertEqual(valid.count, 1000)
        self.assertEqual(valid.duration_ticks, 5)
        self.assertTrue(valid.dry_run)

    async def test_auto_run_skipped_by_risk_filter(self) -> None:
        """Testa rejeição (skipped) quando win_rate não atinge min_win_rate."""
        mock_service = AsyncMock()
        # Série com preços aleatórios que não atingirão 99% de acerto
        prices = [100.0 + (i % 3) * 0.1 for i in range(200)]
        mock_service.get_ticks_history.return_value = {
            "symbol": "1HZ100V",
            "prices": prices,
            "times": list(range(len(prices))),
        }

        req = AutoRunRequest(
            symbol="1HZ100V",
            count=200,
            min_win_rate=99.0,  # Exigência impossível
        )
        res = await auto_run_bot(req, service=mock_service)
        self.assertEqual(res["status"], "skipped")
        self.assertIn("rejeitada pelos filtros de risco", res["message"])
        self.assertIn("regime_diagnosis", res)
        self.assertIn("composite_score", res)
        self.assertIn("top_historical_strategies", res)
        self.assertIsNone(res["execution"])

    async def test_auto_run_standby_on_neutral_market(self) -> None:
        """Testa resposta standby quando o mercado está neutro."""
        mock_service = AsyncMock()
        # Série estática sem tendência (gera NEUTRO)
        prices = [100.0] * 200
        mock_service.get_ticks_history.return_value = {
            "symbol": "1HZ100V",
            "prices": prices,
            "times": list(range(len(prices))),
        }

        req = AutoRunRequest(
            symbol="1HZ100V",
            count=200,
            min_win_rate=0.0,  # Sem corte de taxa de acerto
            max_drawdown_limit=100.0,
        )
        res = await auto_run_bot(req, service=mock_service)
        self.assertEqual(res["status"], "standby")
        self.assertEqual(res["signal"], "NEUTRO")
        self.assertIn("NEUTRO", res["message"])

    async def test_auto_run_dry_run_success_on_call(self) -> None:
        """Testa simulação de proposta (dry_run=True) quando sinal direcional é gerado."""
        mock_service = AsyncMock()
        # Tendência altista clara (gera CALL)
        prices = [100.0 + i * 0.5 for i in range(150)]
        mock_service.get_ticks_history.return_value = {
            "symbol": "1HZ100V",
            "prices": prices,
            "times": list(range(len(prices))),
        }
        # Mock para get_proposal
        mock_service.client = AsyncMock()
        mock_service.client.ws_url = "wss://api.derivws.com/trading/v1/options/ws/public"
        mock_service.client.is_public_mode = True
        mock_service.is_alive = True
        mock_service.send.return_value = {
            "proposal": {
                "id": "mock_prop_123",
                "ask_price": 1.0,
                "payout": 1.95,
                "spot": 175.0,
            }
        }

        req = AutoRunRequest(
            symbol="1HZ100V",
            count=150,
            min_win_rate=50.0,
            max_drawdown_limit=5.0,
            dry_run=True,
        )
        res = await auto_run_bot(req, service=mock_service)
        self.assertEqual(res["status"], "dry_run_success")
        self.assertEqual(res["signal"], "CALL")
        self.assertTrue(res["dry_run"])
        self.assertIsNotNone(res["proposal"])
        self.assertEqual(res["proposal"]["proposal_id"], "mock_prop_123")
        self.assertIn("regime_diagnosis", res)
        self.assertIn("composite_score", res)
        self.assertIn("top_historical_strategies", res)
        self.assertIsInstance(res["top_historical_strategies"], list)

    async def test_auto_run_real_trade_permission_error_maps_401(self) -> None:
        """Testa se PermissionError (falha de autenticação em ordem real) retorna HTTP 401."""
        mock_service = AsyncMock()
        prices = [100.0 + i * 0.5 for i in range(150)]
        mock_service.get_ticks_history.return_value = {
            "symbol": "1HZ100V",
            "prices": prices,
            "times": list(range(len(prices))),
        }
        mock_service.client = AsyncMock()
        mock_service.client.ws_url = "wss://api.derivws.com/trading/v1/options/ws/public"
        mock_service.client.is_public_mode = True
        mock_service.is_alive = True

        # 1ª chamada (proposal) sucede, 2ª chamada (buy) retorna AuthorizationRequired
        mock_service.send.side_effect = [
            {"proposal": {"id": "prop_123", "ask_price": 1.0, "payout": 1.95, "spot": 175.0}},
            {"error": {"code": "AuthorizationRequired", "message": "Authentication required."}},
        ]

        req = AutoRunRequest(
            symbol="1HZ100V",
            count=150,
            min_win_rate=50.0,
            max_drawdown_limit=5.0,
            dry_run=False,  # Disparo real
        )
        with self.assertRaises(HTTPException) as ctx:
            await auto_run_bot(req, service=mock_service)
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_auto_run_empty_ticks_maps_400(self) -> None:
        """Testa se histórico vazio levanta HTTP 400."""
        mock_service = AsyncMock()
        mock_service.get_ticks_history.return_value = {
            "symbol": "1HZ100V",
            "prices": [],
            "times": [],
        }

        req = AutoRunRequest()
        with self.assertRaises(HTTPException) as ctx:
            await auto_run_bot(req, service=mock_service)
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
