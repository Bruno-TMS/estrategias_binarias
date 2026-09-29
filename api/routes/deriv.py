"""Rotas da API para integração com a Deriv."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_deriv_service
from services.deriv_service import DerivService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/balance", summary="Consultar saldo da conta")
async def get_balance(service: DerivService = Depends(get_deriv_service)):
    """Retorna os dados de saldo da conta Deriv."""
    try:
        balance_data = await service.get_balance()
        return {
            "status": "success",
            "data": balance_data,
        }
    except ValueError as exc:
        logger.warning(f"Erro de validação ao consultar saldo: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except (RuntimeError, ConnectionError) as exc:
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


@router.get("/symbols", summary="Listar ativos disponíveis")
async def get_symbols(
    synthetic_only: bool = Query(
        True,
        description="Filtrar apenas ativos sintéticos abertos para negociação",
    ),
    service: DerivService = Depends(get_deriv_service),
):
    """Retorna lista de ativos formatados a partir do cache em memória.

    Caso o cache esteja vazio, executa automaticamente a sincronização.
    """
    try:
        symbols_data = await service.get_symbols(synthetic_only=synthetic_only)
        return {
            "status": "success",
            "total": len(symbols_data),
            "data": symbols_data,
        }
    except ValueError as exc:
        logger.warning(f"Erro de validação ao consultar símbolos: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except (RuntimeError, ConnectionError) as exc:
        logger.error(f"Erro de conexão ao consultar símbolos: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Erro inesperado no endpoint de símbolos: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço Deriv temporariamente indisponível.",
        )


@router.get("/ticks/{symbol}", summary="Obter cotação mais recente de um ativo")
async def get_tick(
    symbol: str,
    service: DerivService = Depends(get_deriv_service),
):
    """Retorna o preço mais recente (quote, epoch e symbol) para o ativo informado."""
    try:
        tick_data = await service.get_latest_tick(symbol=symbol)
        return {
            "status": "success",
            "data": tick_data,
        }
    except ValueError as exc:
        logger.warning(f"Ativo inválido ou não encontrado '{symbol}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except (RuntimeError, ConnectionError) as exc:
        logger.error(f"Erro de conexão ao obter tick para '{symbol}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Erro inesperado no endpoint de tick para '{symbol}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço Deriv temporariamente indisponível.",
        )


@router.post("/symbols/sync", summary="Forçar sincronização do cache de símbolos")
async def sync_symbols(
    service: DerivService = Depends(get_deriv_service),
):
    """Força a sincronização do cache de símbolos e modalidades com a Deriv API."""
    try:
        total = await service.sync_symbols()
        return {
            "status": "success",
            "message": f"Cache de símbolos sincronizado com sucesso: {total} ativos carregados.",
            "total": total,
        }
    except ValueError as exc:
        logger.warning(f"Erro de validação ao sincronizar símbolos: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except (RuntimeError, ConnectionError) as exc:
        logger.error(f"Erro de conexão ao sincronizar símbolos: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Erro inesperado no endpoint de sincronização de símbolos: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço Deriv temporariamente indisponível.",
        )


@router.get(
    "/contracts/{symbol}",
    summary="Listar contratos e durações disponíveis para um ativo",
)
async def get_contracts(
    symbol: str,
    service: DerivService = Depends(get_deriv_service),
):
    """Retorna os tipos de contratos e intervalos de duração permitidos para o ativo informado."""
    try:
        contracts_data = await service.get_contracts_for(symbol=symbol)
        return {
            "status": "success",
            "symbol": symbol,
            "total": len(contracts_data),
            "data": contracts_data,
        }
    except ValueError as exc:
        logger.warning(f"Ativo inválido ou não encontrado '{symbol}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except (RuntimeError, ConnectionError) as exc:
        logger.error(f"Erro de conexão ao obter contratos para '{symbol}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Erro inesperado no endpoint de contratos para '{symbol}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço Deriv temporariamente indisponível.",
        )
