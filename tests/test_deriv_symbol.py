"""Testes unitários para validação de regras de domínio de ActiveSymbol e Asset."""

import unittest
from deriv.symbol import ActiveSymbol, Asset, populate


class TestActiveSymbolDomainRules(unittest.TestCase):
    """Testa o comportamento dinâmico orientado a objetos de ActiveSymbol e Asset."""

    def setUp(self):
        Asset.clear()
        ActiveSymbol.clear()
        self.mock_active_symbols = [
            {
                "symbol": "1HZ100V",
                "display_name": "Volatility 100 (1s) Index",
                "market": "synthetic_index",
                "submarket": "random_index",
            },
            {
                "symbol": "frxEURUSD",
                "display_name": "EUR/USD",
                "market": "forex",
                "submarket": "major_pairs",
            },
            {
                "symbol": "cryBTCUSD",
                "display_name": "BTC/USD",
                "market": "cryptocurrency",
                "submarket": "crypto",
            },
            {
                "symbol": "frxXAUUSD",
                "display_name": "Gold/USD",
                "market": "commodities",
                "submarket": "metals",
            },
        ]
        populate(lst_active_symbols=self.mock_active_symbols)

    def test_synthetic_index_supports_digits_and_ticks(self):
        """Valida que índices sintéticos suportam dígitos e duração em ticks."""
        sym_obj = ActiveSymbol.find(symbol="1HZ100V")[0]
        self.assertIsNotNone(sym_obj)
        self.assertTrue(sym_obj.supports_digits())
        self.assertTrue(sym_obj.supports_barriers())
        self.assertTrue(sym_obj.supports_modality("Matches/Differs"))
        self.assertTrue(sym_obj.supports_modality("Over/Under"))
        self.assertTrue(sym_obj.supports_modality("Even/Odd"))
        self.assertTrue(sym_obj.supports_modality("Rise/Fall"))

        mods = sym_obj.get_supported_modalities()
        self.assertIn("Matches/Differs", mods)
        self.assertIn("Over/Under", mods)
        self.assertIn("Even/Odd", mods)

        durations = sym_obj.get_allowed_durations("Rise/Fall")
        self.assertTrue(durations[0]["has_ticks"])
        self.assertEqual(durations[0]["unit_min"], "t")

    def test_forex_blocks_digits_and_requires_minutes(self):
        """Valida que ativos de Forex bloqueiam dígitos e não aceitam ticks."""
        sym_obj = ActiveSymbol.find(symbol="frxEURUSD")[0]
        self.assertIsNotNone(sym_obj)
        self.assertFalse(sym_obj.supports_digits())
        self.assertFalse(sym_obj.supports_modality("Matches/Differs"))
        self.assertFalse(sym_obj.supports_modality("Over/Under"))
        self.assertFalse(sym_obj.supports_modality("Even/Odd"))

        mods = sym_obj.get_supported_modalities()
        self.assertNotIn("Matches/Differs", mods)
        self.assertNotIn("Over/Under", mods)
        self.assertNotIn("Even/Odd", mods)
        self.assertIn("Rise/Fall", mods)

        durations = sym_obj.get_allowed_durations("Rise/Fall")
        self.assertFalse(durations[0]["has_ticks"])
        self.assertEqual(durations[0]["unit_min"], "m")

    def test_crypto_and_commodities_block_digits(self):
        """Valida que criptomoedas e commodities também não expõem dígitos."""
        btc = ActiveSymbol.find(symbol="cryBTCUSD")[0]
        gold = ActiveSymbol.find(symbol="frxXAUUSD")[0]
        self.assertFalse(btc.supports_digits())
        self.assertFalse(gold.supports_digits())

    def test_asset_duration_properties(self):
        """Valida acesso às propriedades do objeto Asset."""
        assets = Asset.get_all()
        self.assertGreater(len(assets), 0)
        for a in assets:
            self.assertTrue(hasattr(a, "modality"))
            self.assertTrue(hasattr(a, "group"))
            self.assertTrue(hasattr(a, "min_duration"))
            self.assertTrue(hasattr(a, "max_duration"))


if __name__ == "__main__":
    unittest.main()
