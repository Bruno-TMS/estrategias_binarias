from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

from api.deps import deriv_service
from api.routes import deriv
from core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Iniciando {settings.app_name} (debug={settings.debug})...")
    try:
        await deriv_service.connect()
        logger.info("Conexão com Deriv API estabelecida com sucesso.")
    except Exception as exc:
        logger.warning(f"Não foi possível conectar à Deriv API no startup: {exc}")

    yield

    logger.info(f"Encerrando {settings.app_name}...")
    try:
        await deriv_service.disconnect()
        logger.info("Conexão com Deriv API encerrada com sucesso.")
    except Exception as exc:
        logger.warning(f"Erro ao desconectar da Deriv API no shutdown: {exc}")


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)


@app.get("/", tags=["Health Check"])
async def health_check():
    """Rota de verificação de status e saúde da aplicação."""
    return {
        "status": "online",
        "app_name": settings.app_name,
        "debug": settings.debug,
        "deriv_connected": deriv_service.is_alive,
    }


app.include_router(deriv.router, prefix="/deriv", tags=["deriv"])
