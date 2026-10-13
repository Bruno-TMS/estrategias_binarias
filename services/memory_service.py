"""Serviço de persistência e memória de estratégias e regimes de mercado."""

import logging
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.database import SessionLocal, engine, init_db
from models.strategy_log import MarketCycle, StrategySnapshot

logger = logging.getLogger(__name__)


class MemoryService:
    """Gerencia a persistência e consulta histórica de ciclos de mercado e estratégias vencedoras."""

    def __init__(
        self,
        session_factory: sessionmaker[Session] = SessionLocal,
        db_engine=engine,
    ) -> None:
        """Inicializa o serviço garantindo que as tabelas estejam criadas."""
        self.session_factory = session_factory
        self.engine = db_engine
        init_db(self.engine)

    def save_cycle_recommendation(
        self,
        symbol: str,
        regime_diagnosis: dict[str, Any],
        best_strategy: dict[str, Any],
        score: float = 0.0,
        ticks_count: int = 1000,
    ) -> int:
        """Persiste um ciclo de mercado e o snapshot da estratégia recomendada.

        :param symbol: Símbolo do ativo (ex: '1HZ100V').
        :param regime_diagnosis: Dicionário contendo 'regime' e 'directional_bias'.
        :param best_strategy: Dicionário com 'parameters' e métricas de desempenho.
        :param score: Pontuação multivariável calculada para a estratégia.
        :param ticks_count: Volume de ticks analisados no ciclo.
        :return: ID do ciclo gravado (cycle_id).
        """
        cleaned_symbol = symbol.strip() if symbol else "UNKNOWN"
        regime = regime_diagnosis.get("regime", "INDEFINIDO")
        directional_bias = regime_diagnosis.get("directional_bias", "EQUILIBRADO")

        params = best_strategy.get("parameters", {})
        tenkan = int(params.get("tenkan_period", 9))
        kijun = int(params.get("kijun_period", 26))
        senkou_b = int(params.get("senkou_b_period", 52))
        displacement = int(params.get("displacement", 26))
        duration_ticks = int(params.get("duration_ticks", 5))

        win_rate = float(best_strategy.get("win_rate", 0.0))
        total_profit = float(best_strategy.get("total_profit", 0.0))
        max_drawdown = float(best_strategy.get("max_drawdown", 0.0))
        total_trades = int(best_strategy.get("total_trades", 0))

        with self.session_factory() as session:
            try:
                cycle = MarketCycle(
                    symbol=cleaned_symbol,
                    ticks_count=ticks_count,
                    regime=regime,
                    directional_bias=directional_bias,
                )
                session.add(cycle)
                session.flush()  # Popula cycle.id

                snapshot = StrategySnapshot(
                    cycle_id=cycle.id,
                    tenkan=tenkan,
                    kijun=kijun,
                    senkou_b=senkou_b,
                    displacement=displacement,
                    duration_ticks=duration_ticks,
                    win_rate=win_rate,
                    total_profit=total_profit,
                    max_drawdown=max_drawdown,
                    composite_score=float(score),
                    total_trades=total_trades,
                )
                session.add(snapshot)
                session.commit()
                session.refresh(cycle)
                logger.info(
                    "Ciclo gravado com sucesso: ID=%s, Symbol=%s, Regime=%s, Score=%.2f",
                    cycle.id,
                    cleaned_symbol,
                    regime,
                    score,
                )
                return cycle.id
            except Exception as exc:
                session.rollback()
                logger.error("Erro ao persistir recomendação de ciclo: %s", exc)
                raise

    def get_top_strategies_by_regime(
        self,
        symbol: str,
        regime: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Consulta as melhores estratégias históricas calibradas para determinado ativo e regime.

        :param symbol: Símbolo do ativo.
        :param regime: Regime de mercado desejado (ex: 'TENDENCIA_CONSOLIDADA').
        :param limit: Limite máximo de registros retornados.
        :return: Lista de estratégias formatadas ordenadas pelo composite_score e win_rate.
        """
        cleaned_symbol = symbol.strip() if symbol else ""
        cleaned_regime = regime.strip() if regime else ""

        with self.session_factory() as session:
            stmt = (
                select(StrategySnapshot, MarketCycle)
                .join(MarketCycle, StrategySnapshot.cycle_id == MarketCycle.id)
                .where(
                    MarketCycle.symbol == cleaned_symbol,
                    MarketCycle.regime == cleaned_regime,
                )
                .order_by(
                    StrategySnapshot.composite_score.desc(),
                    StrategySnapshot.win_rate.desc(),
                )
                .limit(limit)
            )

            rows = session.execute(stmt).all()

            results: list[dict[str, Any]] = []
            for snapshot, cycle in rows:
                results.append(
                    {
                        "snapshot_id": snapshot.id,
                        "cycle_id": cycle.id,
                        "symbol": cycle.symbol,
                        "regime": cycle.regime,
                        "directional_bias": cycle.directional_bias,
                        "created_at": (
                            cycle.created_at.isoformat()
                            if cycle.created_at
                            else None
                        ),
                        "parameters": {
                            "tenkan_period": snapshot.tenkan,
                            "kijun_period": snapshot.kijun,
                            "senkou_b_period": snapshot.senkou_b,
                            "displacement": snapshot.displacement,
                            "duration_ticks": snapshot.duration_ticks,
                        },
                        "win_rate": snapshot.win_rate,
                        "total_profit": snapshot.total_profit,
                        "max_drawdown": snapshot.max_drawdown,
                        "composite_score": snapshot.composite_score,
                        "total_trades": snapshot.total_trades,
                    }
                )

            return results
