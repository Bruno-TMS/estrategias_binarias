import logging
from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_deriv_service
from services.deriv_service import DerivService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/balance")
async def get_balance(service: DerivService = Depends(get_deriv_service)):
    """Retorna os dados de saldo da conta Deriv."""
    try:
        balance_data = await service.get_balance()
        return {
            "status": "success",
            "data": balance_data,
        }
    except RuntimeError as exc:
        logger.error(f"Erro ao obter saldo Deriv: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Erro inesperado no endpoint de saldo: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço Deriv temporariamente indisponível.",
        )
