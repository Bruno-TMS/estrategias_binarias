"""Rotas da API para integração com a Deriv."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.deps import get_deriv_service, get_memory_service
from deriv.ai_optimizer import AIOptimizer
from deriv.analises_tecnicas import IchimokuIndicator
from deriv.backtesting import BacktestEngine
from deriv.trader_bot import DerivedBot
from services.deriv_service import DerivService
from services.memory_service import MemoryService

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


class AutoRunRequest(BaseModel):
    """Esquema de requisição para calibração retrospectiva e execução autônoma do robô."""

    symbol: str = Field(
        default="1HZ100V",
        description="Símbolo do ativo (ex: 1HZ100V, R_100)",
    )
    count: int = Field(
        default=1000,
        ge=1,
        le=5000,
        description="Quantidade de ticks históricos para calibração (1 a 5000)",
    )
    duration_ticks: int = Field(
        default=5,
        ge=1,
        le=3600,
        description="Duração do contrato em ticks",
    )
    duration_unit: str = Field(
        default="t",
        description="Unidade de duração ('t' para ticks, 's' para segundos, 'm' para minutos)",
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
        description="Taxa de retorno do payout esperado",
    )
    min_win_rate: float = Field(
        default=55.0,
        ge=0.0,
        le=100.0,
        description="Limiar mínimo de taxa de acerto (%) para autorizar a operação",
    )
    max_drawdown_limit: float = Field(
        default=5.0,
        ge=0.0,
        description="Teto máximo de drawdown aceitável para aprovação",
    )
    stop_loss: float = Field(
        default=10.0,
        ge=0.0,
        description="Limite de perda acumulada (Stop Loss)",
    )
    stop_win: float = Field(
        default=25.0,
        ge=0.0,
        description="Meta de lucro acumulado (Stop Win)",
    )
    currency: str = Field(
        default="USD",
        description="Moeda da conta para cotação e negociação",
    )
    dry_run: bool = Field(
        default=True,
        description="Se True, apenas cota e simula a proposta sem disparar compra real",
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


@router.post(
    "/bot/auto-run",
    summary="Ciclo autônomo de calibração quantitativa e execução do robô",
)
async def auto_run_bot(
    payload: AutoRunRequest,
    service: DerivService = Depends(get_deriv_service),
    memory_service: MemoryService = Depends(get_memory_service),
):
    """Executa o ciclo autônomo completo:

    1. Obtém ticks históricos reais do ativo via Deriv API.
    2. Gera grid de 100 variações harmônicas via AIOptimizer e executa backtests em thread separada.
    3. Avalia resultados com função objetivo multivariável e determina regime de mercado.
    4. Persiste a recomendação do ciclo na memória histórica (SQLite).
    5. Valida os filtros de risco (min_win_rate e max_drawdown_limit) na melhor estratégia.
    6. Se aprovada pelo risco:
       - Instancia o DerivedBot com as travas de stop_loss e stop_win.
       - Calcula o sinal atual do mercado com a calibração vencedora.
       - Dispara proposta (dry_run=True) ou compra real (dry_run=False).
    """
    from fastapi.params import Depends as DependsType

    if isinstance(service, DependsType) or service is None:
        service = get_deriv_service()
    if isinstance(memory_service, DependsType) or memory_service is None:
        memory_service = get_memory_service()

    if payload.count <= 0 or payload.count > 5000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O parâmetro count deve estar entre 1 e 5000 ticks.",
        )

    try:
        # 1. Validar e obter histórico de ticks
        history = await service.get_ticks_history(
            symbol=payload.symbol,
            count=payload.count,
        )
        prices = history.get("prices", [])
        if not prices:
            raise ValueError(f"Nenhum tick retornado para o ativo '{payload.symbol}'.")

        # 2. Gerar grid de 100 variações com física do Ichimoku e executar simulações
        grid = AIOptimizer.generate_grid(max_combinations=100)

        engine = BacktestEngine(
            prices=prices,
            stake=payload.stake,
            payout_rate=payload.payout_rate,
        )

        ranked = await asyncio.to_thread(
            engine.rank_strategies,
            parameter_combinations=grid,
            duration_ticks=payload.duration_ticks,
            indicator_cls=IchimokuIndicator,
            allow_overlap=False,
        )

        if not ranked:
            return {
                "status": "skipped",
                "message": "Nenhuma estratégia pôde ser calibrada no backtest.",
                "best_strategy": None,
                "composite_score": 0.0,
                "regime_diagnosis": None,
                "top_historical_strategies": [],
                "market_signal": None,
                "execution": None,
            }

        # 3. Avaliação multivariável e diagnóstico de regime de mercado
        recommendation = AIOptimizer.evaluate_and_recommend(ranked, min_trades=10)
        best_strategy = recommendation["strategy"] or ranked[0]
        score = float(recommendation.get("score", 0.0))
        regime_diagnosis = recommendation.get("regime_diagnosis", {})

        best_strategy_summary = {
            "win_rate": best_strategy["win_rate"],
            "max_drawdown": best_strategy["max_drawdown"],
            "total_profit": best_strategy["total_profit"],
            "total_trades": best_strategy["total_trades"],
            "wins": best_strategy["wins"],
            "losses": best_strategy["losses"],
            "parameters": best_strategy["parameters"],
        }

        # 4. Salvar recomendação do ciclo na base SQLite de forma segura
        try:
            memory_service.save_cycle_recommendation(
                symbol=payload.symbol,
                regime_diagnosis=regime_diagnosis,
                best_strategy=best_strategy,
                score=score,
                ticks_count=len(prices),
            )
        except Exception as exc:
            logger.warning("Falha ao salvar ciclo na memória SQLite: %s", exc)

        # 5. Consultar histórico recente de estratégias vencedoras para o mesmo regime
        top_historical: list[dict[str, Any]] = []
        try:
            current_regime = regime_diagnosis.get("regime", "")
            if current_regime:
                top_historical = memory_service.get_top_strategies_by_regime(
                    symbol=payload.symbol,
                    regime=current_regime,
                    limit=5,
                )
        except Exception as exc:
            logger.warning(
                "Falha ao consultar histórico de estratégias para o regime %s: %s",
                regime_diagnosis.get("regime"),
                exc,
            )

        # 6. Inspecionar a melhor estratégia contra os filtros de risco
        if (
            best_strategy["win_rate"] < payload.min_win_rate
            or best_strategy["max_drawdown"] > payload.max_drawdown_limit
        ):
            return {
                "status": "skipped",
                "message": (
                    f"Estratégia rejeitada pelos filtros de risco: "
                    f"Win Rate={best_strategy['win_rate']:.2f}% (mínimo exigido: {payload.min_win_rate:.2f}%), "
                    f"Drawdown={best_strategy['max_drawdown']:.2f} (máximo tolerado: {payload.max_drawdown_limit:.2f})."
                ),
                "best_strategy": best_strategy_summary,
                "composite_score": score,
                "regime_diagnosis": regime_diagnosis,
                "top_historical_strategies": top_historical,
                "market_signal": None,
                "execution": None,
            }

        # 7. Estratégia aprovada pelo ranking de risco
        # Instanciar DerivedBot com travas de risco
        bot = DerivedBot(
            service=service,
            stake=payload.stake,
            duration=payload.duration_ticks,
            duration_unit=payload.duration_unit,
            symbol=payload.symbol,
            currency=payload.currency,
            stop_loss=payload.stop_loss,
            stop_win=payload.stop_win,
        )

        # Calcular sinal atual com os parâmetros da estratégia vencedora
        params = best_strategy["parameters"]
        indicator = IchimokuIndicator(
            tenkan_period=params.get("tenkan_period", 9),
            kijun_period=params.get("kijun_period", 26),
            senkou_b_period=params.get("senkou_b_period", 52),
            displacement=params.get("displacement", 26),
        )
        signal_data = indicator.get_signal(prices)
        current_signal = signal_data.get("signal", "NEUTRO")

        if current_signal in ("CALL", "PUT"):
            if payload.dry_run:
                # Disparo de proposta / simulação sem compra real
                proposal = await bot.get_proposal(
                    symbol=payload.symbol,
                    contract_type=current_signal,
                    duration=payload.duration_ticks,
                    duration_unit=payload.duration_unit,
                    stake=payload.stake,
                    currency=payload.currency,
                )
                return {
                    "status": "dry_run_success",
                    "message": f"Simulação de proposta aprovada para sinal {current_signal}.",
                    "dry_run": True,
                    "signal": current_signal,
                    "signal_metrics": signal_data.get("metrics"),
                    "best_strategy": best_strategy_summary,
                    "composite_score": score,
                    "regime_diagnosis": regime_diagnosis,
                    "top_historical_strategies": top_historical,
                    "proposal": proposal,
                    "execution": None,
                }
            else:
                # Disparo real
                trade_result = await bot.execute_trade(
                    symbol=payload.symbol,
                    contract_type=current_signal,
                    duration=payload.duration_ticks,
                    duration_unit=payload.duration_unit,
                    stake=payload.stake,
                    currency=payload.currency,
                )
                return {
                    "status": "executed",
                    "message": f"Ordem real {current_signal} executada com sucesso.",
                    "dry_run": False,
                    "signal": current_signal,
                    "signal_metrics": signal_data.get("metrics"),
                    "best_strategy": best_strategy_summary,
                    "composite_score": score,
                    "regime_diagnosis": regime_diagnosis,
                    "top_historical_strategies": top_historical,
                    "proposal": None,
                    "execution": trade_result,
                }
        else:
            # Sinal NEUTRO
            return {
                "status": "standby",
                "message": (
                    "Estratégia calibrada e aprovada pelo risco, porém mercado encontra-se em "
                    "estado NEUTRO (aguardando formação de sinal direcional)."
                ),
                "dry_run": payload.dry_run,
                "signal": "NEUTRO",
                "signal_metrics": signal_data.get("metrics"),
                "best_strategy": best_strategy_summary,
                "composite_score": score,
                "regime_diagnosis": regime_diagnosis,
                "top_historical_strategies": top_historical,
                "proposal": None,
                "execution": None,
            }

    except PermissionError as exc:
        logger.warning(f"Permissão negada ao executar robô: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )
    except ValueError as exc:
        logger.warning(f"Erro de validação no auto-run: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except (RuntimeError, ConnectionError) as exc:
        logger.error(f"Erro de conexão com a Deriv API no auto-run: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Erro inesperado no auto-run: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço Deriv temporariamente indisponível.",
        )
