"""Configuração de banco de dados SQLite local com SQLAlchemy 2.0."""

import logging
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import settings

logger = logging.getLogger(__name__)

# Configura o motor SQLite com verificação de thread desabilitada para FastAPI/threads
connect_args = (
    {"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.debug,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Classe base declarativa padrão do SQLAlchemy 2.0."""

    pass


def get_db() -> Generator[Session, None, None]:
    """Gerador de sessão de banco de dados para injeção de dependência no FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine=None) -> None:
    """Cria automaticamente todas as tabelas registradas nos metadados."""
    active_engine = target_engine or engine
    Base.metadata.create_all(bind=active_engine)
    logger.info("Tabelas do banco de dados inicializadas com sucesso.")
