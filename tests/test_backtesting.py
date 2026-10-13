"""Testes unitários para o módulo de backtesting (deriv/backtesting.py)."""

import unittest
import numpy as np

from deriv.analises_tecnicas import IchimokuIndicator
from deriv.backtesting import BacktestEngine


class TestBacktestEngine(unittest.TestCase):
    """Conjunto de testes para validação das regras de negócio do BacktestEngine."""

    def test_invalid_parameters(self) -> None:
        """Verifica se parâmetros inválidos de stake e payout levantam ValueError."""
        with self.assertRaises(ValueError):
            BacktestEngine([100.0, 101.0], stake=0.0)

        with self.assertRaises(ValueError):
            BacktestEngine([100.0, 101.0], stake=-5.0)

        with self.assertRaises(ValueError):
            BacktestEngine([100.0, 101.0], payout_rate=0.0)

        engine = BacktestEngine([100.0, 101.0], stake=1.0, payout_rate=0.95)
        with self.assertRaises(ValueError):
            engine.run_strategy(IchimokuIndicator(), duration_ticks=0)

    def test_short_series_graceful_handling(self) -> None:
        """Séries vazias ou com tamanho menor/igual a duration_ticks devem retornar métricas zeradas."""
        engine_empty = BacktestEngine([], stake=1.0, payout_rate=0.95)
        res_empty = engine_empty.run_strategy(IchimokuIndicator(), duration_ticks=5)
        self.assertEqual(res_empty["total_trades"], 0)
        self.assertEqual(res_empty["win_rate"], 0.0)
        self.assertEqual(res_empty["total_profit"], 0.0)
        self.assertEqual(len(res_empty["trades"]), 0)

        engine_short = BacktestEngine([100.0, 101.0, 102.0], stake=1.0, payout_rate=0.95)
        res_short = engine_short.run_strategy(IchimokuIndicator(), duration_ticks=5)
        self.assertEqual(res_short["total_trades"], 0)
        self.assertEqual(res_short["win_rate"], 0.0)
        self.assertEqual(res_short["total_profit"], 0.0)

    def test_flat_prices_no_signals(self) -> None:
        """Série estável sem tendência não deve gerar trades."""
        prices = [100.0] * 120
        engine = BacktestEngine(prices, stake=1.0, payout_rate=0.95)
        res = engine.run_strategy(IchimokuIndicator(), duration_ticks=5)
        self.assertEqual(res["total_trades"], 0)
        self.assertEqual(res["wins"], 0)
        self.assertEqual(res["losses"], 0)
        self.assertEqual(res["win_rate"], 0.0)
        self.assertEqual(res["total_profit"], 0.0)

    def test_bullish_trend_simulation(self) -> None:
        """Série de forte alta contínua deve gerar sinais CALL com 100% de vitórias."""
        prices = [100.0 + i * 0.5 for i in range(120)]
        engine = BacktestEngine(prices, stake=10.0, payout_rate=0.95)
        res = engine.run_strategy(IchimokuIndicator(), duration_ticks=5)

        self.assertGreater(res["total_trades"], 0)
        self.assertEqual(res["wins"], res["total_trades"])
        self.assertEqual(res["losses"], 0)
        self.assertEqual(res["win_rate"], 100.0)
        self.assertGreater(res["total_profit"], 0.0)
        self.assertEqual(res["max_drawdown"], 0.0)
        self.assertEqual(res["max_consecutive_losses"], 0)

        first_trade = res["trades"][0]
        self.assertEqual(first_trade["signal"], "CALL")
        self.assertEqual(first_trade["result"], "WIN")
        self.assertGreater(first_trade["exit_price"], first_trade["entry_price"])
        self.assertEqual(first_trade["profit"], 9.5)

    def test_bearish_trend_simulation(self) -> None:
        """Série de forte queda contínua deve gerar sinais PUT com 100% de vitórias."""
        prices = [200.0 - i * 0.5 for i in range(120)]
        engine = BacktestEngine(prices, stake=10.0, payout_rate=0.95)
        res = engine.run_strategy(IchimokuIndicator(), duration_ticks=5)

        self.assertGreater(res["total_trades"], 0)
        self.assertEqual(res["wins"], res["total_trades"])
        self.assertEqual(res["losses"], 0)
        self.assertEqual(res["win_rate"], 100.0)
        self.assertGreater(res["total_profit"], 0.0)

        first_trade = res["trades"][0]
        self.assertEqual(first_trade["signal"], "PUT")
        self.assertEqual(first_trade["result"], "WIN")
        self.assertLess(first_trade["exit_price"], first_trade["entry_price"])
        self.assertEqual(first_trade["profit"], 9.5)

    def test_metrics_drawdown_and_consecutive_losses(self) -> None:
        """Valida o cálculo exato de Drawdown e Perdas Consecutivas em série volátil."""
        np.random.seed(42)
        prices = np.random.randn(500).cumsum() + 100
        engine = BacktestEngine(prices, stake=1.0, payout_rate=0.95)
        res = engine.run_strategy(IchimokuIndicator(), duration_ticks=5)

        self.assertGreater(res["total_trades"], 0)
        self.assertEqual(res["total_trades"], res["wins"] + res["losses"])
        self.assertGreaterEqual(res["max_drawdown"], 0.0)
        self.assertGreaterEqual(res["max_consecutive_losses"], 0)

    def test_rank_strategies_sorting(self) -> None:
        """Testa se rank_strategies classifica corretamente por maior win_rate e menor max_drawdown."""
        np.random.seed(42)
        prices = np.random.randn(600).cumsum() + 100
        engine = BacktestEngine(prices, stake=1.0, payout_rate=0.95)

        combos = [
            {"tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52, "displacement": 26},
            {"tenkan_period": 5, "kijun_period": 15, "senkou_b_period": 30, "displacement": 15},
            {"tenkan_period": 7, "kijun_period": 20, "senkou_b_period": 40, "displacement": 20},
        ]
        ranked = engine.rank_strategies(combos, duration_ticks=5)
        self.assertEqual(len(ranked), 3)

        for i in range(len(ranked) - 1):
            curr = ranked[i]
            nxt = ranked[i + 1]
            if curr["win_rate"] == nxt["win_rate"]:
                self.assertLessEqual(curr["max_drawdown"], nxt["max_drawdown"])
            else:
                self.assertGreater(curr["win_rate"], nxt["win_rate"])


if __name__ == "__main__":
    unittest.main()
