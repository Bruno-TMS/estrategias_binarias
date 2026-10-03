"""Testes unitários para o script de login e autenticação na Deriv API."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import unittest

from fastapi.testclient import TestClient
from main import app
from scripts.test_login import (
    authenticate_deriv,
    get_candidate_endpoints,
    mask_email,
    mask_token,
)
from services.deriv_service import DerivService


class TestLoginScript(unittest.TestCase):
    """Testes para as funções utilitárias e de autenticação do test_login.py."""

    def test_mask_token_security(self):
        """Garante que o token nunca seja exposto em texto claro."""
        self.assertEqual(mask_token(None), "[NÃO CONFIGURADO]")
        self.assertEqual(mask_token(""), "[NÃO CONFIGURADO]")
        self.assertEqual(mask_token("12345"), "***")
        self.assertEqual(mask_token("12345678"), "***")

        long_token = "pat_abcdef1234567890xyz"
        masked = mask_token(long_token)
        self.assertEqual(masked, "pat_...0xyz")
        self.assertNotIn("abcdef1234567890", masked)

    def test_mask_email_privacy(self):
        """Garante a anonimização correta de e-mails."""
        self.assertEqual(mask_email(None), "--")
        self.assertEqual(mask_email(""), "--")
        self.assertEqual(mask_email("invalid_email"), "invalid_email")
        self.assertEqual(mask_email("trader@deriv.com"), "tr***r@deriv.com")
        self.assertEqual(mask_email("ab@deriv.com"), "a*@deriv.com")

    def test_candidate_endpoints_generation(self):
        """Verifica a geração de URLs candidatas com app_id."""
        endpoints = get_candidate_endpoints(app_id="1089", ws_url="wss://custom.url")
        self.assertIn("wss://custom.url", endpoints)
        self.assertIn("wss://custom.url?app_id=1089", endpoints)
        self.assertTrue(any("1089" in ep for ep in endpoints))

    def test_authenticate_deriv_mock_mode(self):
        """Testa o modo mock retornando todas as informações esperadas."""
        result = asyncio.run(authenticate_deriv(token="dummy_token_123", app_id="1089", mock=True))
        self.assertTrue(result["success"])
        self.assertEqual(result["loginid"], "VRTC9876543")
        self.assertEqual(result["fullname"], "Trader Demonstrativo")
        self.assertTrue(result["is_virtual"])
        self.assertEqual(result["account_type"], "Demo (Virtual)")
        self.assertEqual(result["balance"], 10000.0)
        self.assertEqual(result["currency"], "USD")
        self.assertEqual(result["balance_formatted"], "USD 10,000.00")
        self.assertIn("read", result["scopes"])
        self.assertIn("trade", result["scopes"])

    def test_authenticate_deriv_empty_token(self):
        """Garante exceção quando o token é vazio."""
        with self.assertRaises(ValueError):
            asyncio.run(authenticate_deriv(token="", mock=False))

    @patch("scripts.test_login.websockets.connect")
    def test_authenticate_deriv_api_error(self, mock_ws_connect):
        """Testa o tratamento seguro de erro retornado pela Deriv API (InvalidToken)."""
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.recv = AsyncMock(
            return_value='{"error": {"code": "InvalidToken", "message": "Your token has expired or is invalid."}}'
        )
        mock_ws.__aenter__.return_value = mock_ws
        mock_ws.__aexit__.return_value = None
        mock_ws_connect.return_value = mock_ws

        result = asyncio.run(
            authenticate_deriv(token="expired_token_123", app_id="1089", mock=False)
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "InvalidToken")
        self.assertIn("Your token has expired", result["error_message"])
        self.assertEqual(result["masked_token"], "expi..._123")


class TestDerivServiceAuthorize(unittest.IsolatedAsyncioTestCase):
    """Testes para o método DerivService.authorize()."""

    async def test_deriv_service_authorize_success(self):
        """Testa autorização bem-sucedida no DerivService."""
        service = DerivService()
        service.client = MagicMock()
        service.client.is_alive = True
        service.send = AsyncMock(
            return_value={
                "msg_type": "authorize",
                "authorize": {
                    "loginid": "VRTC112233",
                    "is_virtual": 1,
                    "balance": 5000.50,
                    "currency": "USD",
                    "email": "user@example.com",
                    "scopes": ["read", "trade"],
                },
            }
        )

        auth_data = await service.authorize(token="valid_token_abc")
        self.assertEqual(auth_data["loginid"], "VRTC112233")
        self.assertTrue(auth_data["is_virtual"])
        self.assertEqual(auth_data["account_type"], "Demo (Virtual)")
        self.assertEqual(auth_data["balance"], 5000.50)
        self.assertEqual(auth_data["currency"], "USD")

    async def test_deriv_service_authorize_permission_error(self):
        """Testa falha de permissão no DerivService.authorize()."""
        service = DerivService()
        service.client = MagicMock()
        service.client.is_alive = True
        service.send = AsyncMock(
            return_value={
                "error": {
                    "code": "InvalidToken",
                    "message": "Token inválido.",
                }
            }
        )

        with self.assertRaises(PermissionError):
            await service.authorize(token="invalid_token")


class TestAuthVerifyEndpoint(unittest.TestCase):
    """Testes para o endpoint GET /deriv/auth/verify."""

    def setUp(self):
        self.client = TestClient(app)

    @patch("api.routes.deriv.DerivService.authorize")
    def test_verify_auth_endpoint_success(self, mock_authorize):
        """Testa resposta 200 no endpoint /deriv/auth/verify."""
        mock_authorize.return_value = {
            "loginid": "CR554433",
            "is_virtual": False,
            "account_type": "Real",
            "balance": 250.75,
            "currency": "USD",
            "email": "trader@deriv.com",
            "scopes": ["read", "trade"],
        }

        response = self.client.get("/deriv/auth/verify")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["data"]["loginid"], "CR554433")
        self.assertEqual(body["data"]["account_type"], "Real")
        self.assertEqual(body["data"]["balance"], 250.75)

    @patch("api.routes.deriv.DerivService.authorize")
    def test_verify_auth_endpoint_unauthorized(self, mock_authorize):
        """Testa resposta 401 no endpoint /deriv/auth/verify quando o token é inválido."""
        mock_authorize.side_effect = PermissionError("Token inválido.")

        response = self.client.get("/deriv/auth/verify")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Token inválido", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
