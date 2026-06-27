from fastapi import APIRouter, Depends
from app.api.deps import get_deriv_service
from app.deriv.deriv_service import DerivService

router = APIRouter()

@router.get("/balance")
async def get_balance(service: DerivService = Depends(get_deriv_service)):
    await service.connect()
    return await service.send({"balance": 1})