"""Modelos ORM para persistência de ciclos de mercado e snapshots de estratégias."""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class MarketCycle(Base):
    """Representa um ciclo temporal analisado para determinado ativo."""

    __tablename__ = "market_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    ticks_count: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    regime: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    directional_bias: Mapped[str] = mapped_column(String(32), default="EQUILIBRADO", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    snapshots: Mapped[List["StrategySnapshot"]] = relationship(
        back_populates="cycle",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<MarketCycle(id={self.id}, symbol='{self.symbol}', regime='{self.regime}', "
            f"bias='{self.directional_bias}', ticks={self.ticks_count})>"
        )


class StrategySnapshot(Base):
    """Representa a melhor configuração de estratégia encontrada em um ciclo."""

    __tablename__ = "strategy_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("market_cycles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Hiperparâmetros
    tenkan: Mapped[int] = mapped_column(Integer, nullable=False)
    kijun: Mapped[int] = mapped_column(Integer, nullable=False)
    senkou_b: Mapped[int] = mapped_column(Integer, nullable=False)
    displacement: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ticks: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Métricas de Desempenho
    win_rate: Mapped[float] = mapped_column(Float, nullable=False)
    total_profit: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False)
    composite_score: Mapped[float] = mapped_column(Float, index=True, nullable=False)
    total_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    cycle: Mapped["MarketCycle"] = relationship(back_populates="snapshots")

    def __repr__(self) -> str:
        return (
            f"<StrategySnapshot(id={self.id}, cycle_id={self.cycle_id}, "
            f"params=({self.tenkan},{self.kijun},{self.senkou_b}), wr={self.win_rate}%, "
            f"score={self.composite_score})>"
        )
