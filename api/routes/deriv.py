"""Rotas da API para integração com a Deriv."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.deps import get_deriv_service
from deriv.analises_tecnicas import IchimokuIndicator
from deriv.backtesting import BacktestEngine
from services.deriv_service import DerivService

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_ICHIMOKU_GRID: list[dict[str, int]] = [
    {"tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52, "displacement": 26},
    {"tenkan_period": 5, "kijun_period": 15, "senkou_b_period": 30, "displacement": 15},
    {"tenkan_period": 7, "kijun_period": 22, "senkou_b_period": 44, "displacement": 22},
    {"tenkan_period": 6, "kijun_period": 18, "senkou_b_period": 36, "displacement": 18},
    {"tenkan_period": 12, "kijun_period": 30, "senkou_b_period": 60, "displacement": 30},
]


class IchimokuBacktestRequest(BaseModel):
    """Esquema de requisição para backtest e ranqueamento de estratégias Ichimoku."""

    symbol: str = Field(
        default="1HZ100V",
        description="Símbolo do ativo (ex: 1HZ100V, R_100)",
    )
    count: int = Field(
        default=1000,
        ge=1,
        le=5000,
        description="Quantidade de ticks históricos para simulação (1 a 5000)",
    )
    duration_ticks: int = Field(
        default=5,
        ge=1,
        le=3600,
        description="Duração de cada contrato em ticks",
    )
    stake: float = Field(
        default=1.0,
        gt=0.0,
        description="Valor apostado por contrato",
    )
    payout_rate: float = Field(
        default=0.95,
        gt=0.0,
        le=2.0,
        description="Taxa de payout do contrato (ex: 0.95 para 95%)",
    )
    allow_overlap: bool = Field(
        default=False,
        description="Permite abertura simultânea de contratos sobrepostos",
    )
    parameter_combinations: list[dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Variações de parâmetros para o Ichimoku. "
            "Se omitido, um grid calibrado ao redor de 9, 26, 52 é gerado automaticamente."
        ),
    )


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


@router.post(
    "/backtest/ichimoku",
    summary="Executar backtest e ranqueamento de estratégias Ichimoku",
)
async def backtest_ichimoku(
    payload: IchimokuBacktestRequest,
    service: DerivService = Depends(get_deriv_service),
):
    """Executa simulação quantitativa e ranqueamento de hiperparâmetros Ichimoku com ticks reais da Deriv.

    - Obtém a série histórica de ticks do ativo informado via Deriv API.
    - Executa simulação sem look-ahead bias calculando vitórias, derrotas, win rate, lucro e drawdown.
    - Classifica as estratégias pelo maior win rate e menor drawdown.
    """
    if payload.count <= 0 or payload.count > 5000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O parâmetro count deve estar entre 1 e 5000 ticks.",
        )

    try:
        # 1. Obter histórico real de ticks via service
        history = await service.get_ticks_history(
            symbol=payload.symbol,
            count=payload.count,
        )
        prices = history.get("prices", [])
        if not prices:
            raise ValueError(f"Nenhum tick retornado para o ativo '{payload.symbol}'.")

        # 2. Instanciar o motor de backtest
        engine = BacktestEngine(
            prices=prices,
            stake=payload.stake,
            payout_rate=payload.payout_rate,
        )

        # Grid de parâmetros fornecido ou padrão calibrado
        combos = payload.parameter_combinations or DEFAULT_ICHIMOKU_GRID

        # 3. Executar o ranqueamento em thread separada para não bloquear o loop de eventos
        ranked = await asyncio.to_thread(
            engine.rank_strategies,
            parameter_combinations=combos,
            duration_ticks=payload.duration_ticks,
            indicator_cls=IchimokuIndicator,
            allow_overlap=payload.allow_overlap,
        )

        # 4. Formatar e retornar resposta
        times = history.get("times", [])
        summary = {
            "symbol": payload.symbol,
            "ticks_count": len(prices),
            "start_time": times[0] if times else None,
            "end_time": times[-1] if times else None,
            "duration_ticks": payload.duration_ticks,
            "stake": payload.stake,
            "payout_rate": payload.payout_rate,
            "allow_overlap": payload.allow_overlap,
            "strategies_tested": len(ranked),
        }

        best_strategy = ranked[0] if ranked else None

        return {
            "status": "success",
            "summary": summary,
            "best_strategy": best_strategy,
            "ranked_strategies": ranked,
        }

    except ValueError as exc:
        logger.warning(f"Erro de validação no backtest: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except (RuntimeError, ConnectionError) as exc:
        logger.error(f"Erro de conexão com a Deriv API durante backtest: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Erro inesperado no endpoint de backtest: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço Deriv temporariamente indisponível.",
        )
