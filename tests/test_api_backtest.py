"""Testes unitários para o endpoint POST /deriv/backtest/ichimoku."""

import unittest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from pydantic import ValidationError

from api.routes.deriv import backtest_ichimoku, IchimokuBacktestRequest
from main import app


class TestApiBacktestIchimoku(unittest.IsolatedAsyncioTestCase):
    """Testes para validação e execução do endpoint de backtest da Deriv."""

    def test_route_registration(self) -> None:
        """Verifica se a rota /deriv/backtest/ichimoku está registrada na aplicação FastAPI."""
        paths = app.openapi()["paths"]
        self.assertIn("/deriv/backtest/ichimoku", paths)
        self.assertIn("post", paths["/deriv/backtest/ichimoku"])

    def test_request_validation(self) -> None:
        """Testa restrições e validações do esquema Pydantic IchimokuBacktestRequest."""
        # count inválido (> 5000)
        with self.assertRaises(ValidationError):
            IchimokuBacktestRequest(count=5001)

        # count inválido (<= 0)
        with self.assertRaises(ValidationError):
            IchimokuBacktestRequest(count=0)

        # duration_ticks inválido (<= 0)
        with self.assertRaises(ValidationError):
            IchimokuBacktestRequest(duration_ticks=0)

        # stake inválido (<= 0)
        with self.assertRaises(ValidationError):
            IchimokuBacktestRequest(stake=0.0)

        # payout_rate inválido (<= 0)
        with self.assertRaises(ValidationError):
            IchimokuBacktestRequest(payout_rate=0.0)

        # Requisição válida com valores padrão
        valid_req = IchimokuBacktestRequest()
        self.assertEqual(valid_req.symbol, "1HZ100V")
        self.assertEqual(valid_req.count, 1000)
        self.assertEqual(valid_req.duration_ticks, 5)

    async def test_endpoint_mock_execution(self) -> None:
        """Testa o processamento do endpoint com histórico simulado."""
        mock_service = AsyncMock()
        mock_prices = [100.0 + i * 0.2 for i in range(150)]
        mock_service.get_ticks_history.return_value = {
            "symbol": "1HZ100V",
            "prices": mock_prices,
            "times": list(range(len(mock_prices))),
        }

        req = IchimokuBacktestRequest(symbol="1HZ100V", count=150)
        response = await backtest_ichimoku(req, service=mock_service)

        self.assertEqual(response["status"], "success")
        self.assertIn("summary", response)
        self.assertIn("best_strategy", response)
        self.assertIn("ranked_strategies", response)
        self.assertEqual(response["summary"]["ticks_count"], 150)
        self.assertEqual(len(response["ranked_strategies"]), 5)
        self.assertIsNotNone(response["best_strategy"])

    async def test_endpoint_empty_prices_returns_400(self) -> None:
        """Verifica se lista vazia de preços gera HTTPException 400."""
        mock_service = AsyncMock()
        mock_service.get_ticks_history.return_value = {
            "symbol": "1HZ100V",
            "prices": [],
            "times": [],
        }

        req = IchimokuBacktestRequest()
        with self.assertRaises(HTTPException) as ctx:
            await backtest_ichimoku(req, service=mock_service)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_endpoint_connection_error_returns_503(self) -> None:
        """Verifica se erro de conexão da Deriv gera HTTPException 503."""
        mock_service = AsyncMock()
        mock_service.get_ticks_history.side_effect = ConnectionError("Falha de conexão com WebSocket")

        req = IchimokuBacktestRequest()
        with self.assertRaises(HTTPException) as ctx:
            await backtest_ichimoku(req, service=mock_service)
        self.assertEqual(ctx.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
