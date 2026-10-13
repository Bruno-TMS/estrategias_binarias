"""Testes unitários para persistência e consulta de memória analítica (tests/test_database_memory.py)."""

import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.strategy_log import MarketCycle, StrategySnapshot
from services.memory_service import MemoryService


class TestDatabaseMemory(unittest.TestCase):
    """Testa a criação de tabelas, inserção e consulta de ciclos e estratégias."""

    def setUp(self) -> None:
        """Cria banco SQLite em memória isolado para os testes."""
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        self.session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
        Base.metadata.create_all(bind=self.engine)
        self.memory_service = MemoryService(
            session_factory=self.session_factory,
            db_engine=self.engine,
        )

    def tearDown(self) -> None:
        """Destrói as tabelas ao final do teste."""
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_save_cycle_recommendation_persists_data(self) -> None:
        """Verifica se save_cycle_recommendation grava MarketCycle e StrategySnapshot corretamente."""
        regime_diag = {
            "regime": "TENDENCIA_CONSOLIDADA",
            "directional_bias": "CALL_DOMINANTE",
            "recommended_profile": "intermediario",
        }
        best_strat = {
            "win_rate": 64.5,
            "total_profit": 28.5,
            "max_drawdown": 3.8,
            "total_trades": 80,
            "parameters": {
                "tenkan_period": 9,
                "kijun_period": 26,
                "senkou_b_period": 52,
                "displacement": 26,
                "duration_ticks": 5,
            },
        }

        cycle_id = self.memory_service.save_cycle_recommendation(
            symbol="1HZ100V",
            regime_diagnosis=regime_diag,
            best_strategy=best_strat,
            score=18.42,
            ticks_count=1000,
        )

        self.assertIsInstance(cycle_id, int)
        self.assertGreater(cycle_id, 0)

        # Inspeciona banco diretamente
        with self.session_factory() as session:
            cycle = session.get(MarketCycle, cycle_id)
            self.assertIsNotNone(cycle)
            self.assertEqual(cycle.symbol, "1HZ100V")
            self.assertEqual(cycle.regime, "TENDENCIA_CONSOLIDADA")
            self.assertEqual(cycle.directional_bias, "CALL_DOMINANTE")
            self.assertEqual(cycle.ticks_count, 1000)

            self.assertEqual(len(cycle.snapshots), 1)
            snap = cycle.snapshots[0]
            self.assertEqual(snap.tenkan, 9)
            self.assertEqual(snap.kijun, 26)
            self.assertEqual(snap.senkou_b, 52)
            self.assertEqual(snap.displacement, 26)
            self.assertEqual(snap.duration_ticks, 5)
            self.assertEqual(snap.win_rate, 64.5)
            self.assertEqual(snap.total_profit, 28.5)
            self.assertEqual(snap.max_drawdown, 3.8)
            self.assertEqual(snap.composite_score, 18.42)
            self.assertEqual(snap.total_trades, 80)

    def test_get_top_strategies_by_regime_filtering_and_order(self) -> None:
        """Verifica se a busca filtra corretamente por símbolo/regime e ordena por score decrescente."""
        # 1. Ciclo 1 - Tendência consolidada (Score 15.0)
        self.memory_service.save_cycle_recommendation(
            symbol="1HZ100V",
            regime_diagnosis={"regime": "TENDENCIA_CONSOLIDADA", "directional_bias": "CALL_DOMINANTE"},
            best_strategy={
                "win_rate": 58.0,
                "total_profit": 15.0,
                "max_drawdown": 5.0,
                "total_trades": 50,
                "parameters": {"tenkan_period": 7, "kijun_period": 22, "senkou_b_period": 44, "displacement": 22},
            },
            score=15.0,
        )

        # 2. Ciclo 2 - Tendência consolidada (Score 25.0 - Melhor)
        self.memory_service.save_cycle_recommendation(
            symbol="1HZ100V",
            regime_diagnosis={"regime": "TENDENCIA_CONSOLIDADA", "directional_bias": "CALL_DOMINANTE"},
            best_strategy={
                "win_rate": 68.0,
                "total_profit": 35.0,
                "max_drawdown": 2.0,
                "total_trades": 60,
                "parameters": {"tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52, "displacement": 26},
            },
            score=25.0,
        )

        # 3. Ciclo 3 - Regime diferente (Scalping em Lateralização)
        self.memory_service.save_cycle_recommendation(
            symbol="1HZ100V",
            regime_diagnosis={"regime": "ALTA_VOLATILIDADE_SCALPING", "directional_bias": "EQUILIBRADO"},
            best_strategy={
                "win_rate": 54.0,
                "total_profit": 8.0,
                "max_drawdown": 3.0,
                "total_trades": 70,
                "parameters": {"tenkan_period": 5, "kijun_period": 15, "senkou_b_period": 30, "displacement": 15},
            },
            score=10.0,
        )

        # 4. Ciclo 4 - Ativo diferente (R_50)
        self.memory_service.save_cycle_recommendation(
            symbol="R_50",
            regime_diagnosis={"regime": "TENDENCIA_CONSOLIDADA", "directional_bias": "PUT_DOMINANTE"},
            best_strategy={
                "win_rate": 60.0,
                "total_profit": 18.0,
                "max_drawdown": 4.0,
                "total_trades": 45,
                "parameters": {"tenkan_period": 8, "kijun_period": 24, "senkou_b_period": 48, "displacement": 24},
            },
            score=16.0,
        )

        # Consulta: apenas 1HZ100V com TENDENCIA_CONSOLIDADA
        top_strats = self.memory_service.get_top_strategies_by_regime(
            symbol="1HZ100V",
            regime="TENDENCIA_CONSOLIDADA",
            limit=5,
        )

        self.assertEqual(len(top_strats), 2)
        # Primeiro item deve ser o de maior score (25.0)
        self.assertEqual(top_strats[0]["composite_score"], 25.0)
        self.assertEqual(top_strats[0]["win_rate"], 68.0)
        self.assertEqual(top_strats[0]["parameters"]["tenkan_period"], 9)

        # Segundo item deve ser o de score 15.0
        self.assertEqual(top_strats[1]["composite_score"], 15.0)
        self.assertEqual(top_strats[1]["win_rate"], 58.0)

    def test_get_top_strategies_unmatched_returns_empty(self) -> None:
        """Verifica se busca sem correspondência retorna lista vazia."""
        res = self.memory_service.get_top_strategies_by_regime("UNKNOWN_SYM", "REGIME_X")
        self.assertEqual(res, [])


if __name__ == "__main__":
    unittest.main()
