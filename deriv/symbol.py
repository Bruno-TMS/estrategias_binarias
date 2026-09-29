"""Módulo de gerenciamento e cache de ativos e símbolos da Deriv API."""

import asyncio
import logging
import re
from functools import reduce
from typing import Any

try:
    from deriv.util import check_str
except ImportError:
    from util import check_str

logger = logging.getLogger(__name__)


class Asset:
    """Representa um parâmetro/modalidade de contrato negociável para um ativo."""

    _instances: list["Asset"] = []

    def __new__(cls, *, group, modality, digit_min, unit_min, digit_max, unit_max):
        if (not check_str(group)) or (not check_str(modality)):
            raise ValueError(
                f"String(s) inválida(s) ou nula(s) para group:{group} e/ou modality:{modality}."
            )

        min_max_info = cls.get_min_max_info(
            digit_min=digit_min,
            unit_min=unit_min,
            digit_max=digit_max,
            unit_max=unit_max,
        )

        digit_min = None
        unit_min = None
        key_min = None
        index_min = None
        min_duration = None

        digit_max = None
        unit_max = None
        key_max = None
        index_max = None
        max_duration = None

        key = f"{group}{modality}"
        srt_repr = f"{group:>12} — {modality:<26}"
        has_duration = False

        if min_max_info:
            digit_min = min_max_info.get("min_info").get("digit")
            unit_min = min_max_info.get("min_info").get("unit")
            key_min = min_max_info.get("min_info").get("key")
            index_min = min_max_info.get("min_info").get("index")
            min_duration = min_max_info.get("min_info").get("duration")

            digit_max = min_max_info.get("max_info").get("digit")
            unit_max = min_max_info.get("max_info").get("unit")
            key_max = min_max_info.get("max_info").get("key")
            index_max = min_max_info.get("max_info").get("index")
            max_duration = min_max_info.get("max_info").get("duration")

            key = key + key_min + key_max
            srt_repr = srt_repr + f" {min_duration:>3} {max_duration:>4}"
            has_duration = True

        instance = Asset.find(value=key, only_key=True)

        if not instance:
            instance = super().__new__(cls)
            instance._group = group
            instance._modality = modality
            instance._digit_min = digit_min
            instance._unit_min = unit_min
            instance._key_min = key_min
            instance._index_min = index_min
            instance._min_duration = min_duration
            instance._digit_max = digit_max
            instance._unit_max = unit_max
            instance._key_max = key_max
            instance._index_max = index_max
            instance._max_duration = max_duration
            instance._key = key
            instance._str_repr = srt_repr
            instance._has_duration = has_duration
            cls._instances.append(instance)

        return instance

    # region TradeParameter_InstancesMembers
    @property
    def group(self):
        return self._group

    @property
    def modality(self):
        return self._modality

    @property
    def min_duration(self):
        return self._min_duration

    @property
    def max_duration(self):
        return self._max_duration

    @property
    def key(self):
        return self._key

    def __str__(self):
        return self._str_repr

    def __repr__(self):
        return self._str_repr

    # endregion

    # region TradeParameter_ClassMembers
    @classmethod
    def clear(cls):
        cls._instances.clear()

    @classmethod
    def find(cls, value, only_key=True):
        if only_key:
            insts = [inst for inst in cls._instances if inst._key == value]
            if not insts:
                return None
            if len(insts) > 1:
                raise ValueError(
                    f"Múltiplas instâncias encontradas para a chave fornecida: {insts}"
                )
            return insts[0]
        else:
            insts = [inst for inst in cls._instances if inst._key == value]
            if not insts:
                pattern = re.compile(value, re.I)
                insts = [
                    inst for inst in cls._instances if pattern.search(inst._str_repr)
                ]
            if not insts:
                insts = [
                    inst
                    for inst in cls._instances
                    if value in inst._group or value in inst._modality
                ]
            return insts

    @classmethod
    def get_all(cls):
        return sorted(cls._instances, key=lambda x: x._key)

    @classmethod
    def get_all_keys(cls):
        return [inst._key for inst in sorted(cls._instances, key=lambda x: x._key)]

    @classmethod
    def get_by_group(cls, group, *, restrict=False):
        pattern = re.compile(group, flags=re.I)
        return sorted(
            [
                inst
                for inst in cls._instances
                if (
                    pattern.search(inst._group)
                    if not restrict
                    else pattern.fullmatch(inst._group)
                )
            ],
            key=lambda x: x._key,
        )

    @classmethod
    def get_by_modality(cls, modality, *, restrict=False):
        pattern = re.compile(modality, flags=re.I)
        return sorted(
            [
                inst
                for inst in cls._instances
                if (
                    pattern.search(inst.modality)
                    if not restrict
                    else pattern.fullmatch(inst.modality)
                )
            ],
            key=lambda x: x._key,
        )

    @classmethod
    def get_by_duration(cls, *, digit, unit, fit_in_units=True):
        drt_info = cls.get_info_duration(digit=digit, unit=unit)
        if drt_info:
            if fit_in_units:
                instances = [
                    inst
                    for inst in cls._instances
                    if inst._has_duration
                    and inst._index_min == inst._index_max == drt_info.get("index")
                    and inst._digit_min <= drt_info.get("digit") <= inst._digit_max
                ]
            else:
                instances = [
                    inst
                    for inst in cls._instances
                    if inst._has_duration
                    and inst._key_min <= drt_info.get("key") <= inst._key_max
                ]
            return sorted(instances, key=lambda x: x._key)
        return []

    @classmethod
    def get_groups(cls):
        return sorted({inst._group for inst in cls._instances})

    @classmethod
    def get_modalities(cls):
        return sorted({inst._modality for inst in cls._instances})

    # endregion

    # region TradeParameter_Static
    @staticmethod
    def get_info_duration(*, digit, unit):
        if (digit is None or digit == "") and (unit is None or unit == ""):
            return {}

        digit_str = str(digit).strip() if digit is not None else ""
        unit_str = str(unit).strip() if unit is not None else ""

        # Extrai unidade caso o dígito já a contenha embutida (ex: '10t')
        if not unit_str and digit_str:
            if match := re.match(r"^(\d+)([a-zA-Z]*)$", digit_str):
                digit_str, unit_str = match.group(1), match.group(2)

        if not digit_str and not unit_str:
            return {}

        # Unidades reconhecidas em ordem cronológica (ticks, seconds, minutes, hours, days, weeks, months, years)
        known_units = ["t", "s", "m", "h", "d", "w", "M", "y"]

        if unit_str in known_units:
            index = known_units.index(unit_str)
        elif unit_str.lower() in [u.lower() for u in known_units]:
            index = [u.lower() for u in known_units].index(unit_str.lower())
        elif not unit_str:
            index = 0
        else:
            # Unidade desconhecida: atribui índice ordinal após as conhecidas de forma resiliente
            index = len(known_units)

        int_digit = int(digit_str) if digit_str.isdigit() else 0
        duration = f"{digit_str}{unit_str}"
        key = f"{index}{digit_str.zfill(5)}"

        return {
            "digit": int_digit,
            "unit": unit_str,
            "duration": duration,
            "index": index,
            "key": key,
        }

    @staticmethod
    def get_min_max_info(*, digit_min, unit_min, digit_max, unit_max):
        if (not digit_min) and (not unit_min) and (not digit_max) and (not unit_max):
            return {}
        min_info = Asset.get_info_duration(digit=digit_min, unit=unit_min)
        max_info = Asset.get_info_duration(digit=digit_max, unit=unit_max)
        if (min_info and not max_info) or (max_info and not min_info):
            return {"min_info": min_info or max_info, "max_info": max_info or min_info}
        if min_info and max_info and min_info.get("key") > max_info.get("key"):
            return {"min_info": min_info, "max_info": max_info}
        return {"min_info": min_info, "max_info": max_info}

    # endregion


class ActiveSymbol:
    """Representa um ativo financeiro disponível na Deriv API."""

    _instances: list["ActiveSymbol"] = []

    def __new__(
        cls,
        *,
        symbol,
        display_name,
        assets,
        exchange_is_open,
        is_trading_suspended,
        market,
        market_display_name,
        sub_market,
        submarket_display_name,
    ):
        if not check_str(symbol):
            raise ValueError(f"String(s) inválida(s) ou nula(s) para symbol:{symbol}")

        key = f"{not is_trading_suspended}{not exchange_is_open}{market}{sub_market}{symbol}"
        existing = cls.find(key=key)
        if existing:
            return existing[0]

        instance = super().__new__(cls)
        srt_repr = f'{market_display_name if market_display_name else "":<16} {submarket_display_name if submarket_display_name else "":<19} {display_name}{"(XX)" if is_trading_suspended else ""} {"" if exchange_is_open else " — closed":>10}'
        instance._symbol = symbol
        instance._display_name = display_name
        instance._assets = [p for p in sorted(assets, key=lambda x: x.key)]
        instance._exchange_is_open = exchange_is_open
        instance._is_trading_suspended = is_trading_suspended
        instance._market = market
        instance._market_display_name = market_display_name
        instance._sub_market = sub_market
        instance._submarket_display_name = submarket_display_name
        instance._key = key
        instance._str_repr = srt_repr
        cls._instances.append(instance)

        return instance

    # region ActiveSymbol_InstancesMembers
    @property
    def symbol(self):
        return self._symbol

    @property
    def display_name(self):
        return self._display_name

    @property
    def exchange_is_open(self):
        return self._exchange_is_open

    @property
    def is_trading_suspended(self):
        return self._is_trading_suspended

    @property
    def market(self):
        return self._market

    @property
    def market_display_name(self):
        return self._market_display_name

    @property
    def sub_market(self):
        return self._sub_market

    @property
    def submarket_display_name(self):
        return self._submarket_display_name

    def __str__(self):
        return self._str_repr

    def __repr__(self):
        return self._str_repr

    def __iter__(self):
        return iter(self._assets)

    # endregion

    # region ActiveSymbol_ClassMembers
    @classmethod
    def clear(cls):
        cls._instances.clear()

    @classmethod
    def get_all(cls) -> list["ActiveSymbol"]:
        return sorted(cls._instances, key=lambda x: x._key)

    @classmethod
    def find(cls, **kwargs):
        kw_research = ["restrict"]
        kw_filter = ["assets", "exchange_is_open", "is_trading_suspended"]
        kw_prop = [
            "key",
            "symbol",
            "display_name",
            "market",
            "market_display_name",
            "sub_market",
            "submarket_display_name",
        ]

        instances = sorted(cls._instances, key=lambda x: x._key)

        if not kwargs:
            return instances

        if kw_out := {
            kw: value
            for kw, value in kwargs.items()
            if kw not in kw_research + kw_filter + kw_prop
        }:
            raise ValueError(f"Argumentos inválidos: {kw_out}")

        args_research = {kw: value for kw, value in kwargs.items() if kw in kw_research}
        args_filters = {kw: value for kw, value in kwargs.items() if kw in kw_filter}
        args_props = {kw: value for kw, value in kwargs.items() if kw in kw_prop}

        if args_research and any(
            value for value in args_research.values() if not isinstance(value, bool)
        ):
            raise ValueError(
                f"Valores inválidos para pesquisa: {args_research}, deve ser booleano."
            )

        if args_filters and any(
            value for value in args_filters.values() if not isinstance(value, bool)
        ):
            raise ValueError(
                f"Valores inválidos para filtro: {args_filters}, deve ser booleano."
            )

        if args_props and any(not check_str(value) for value in args_props.values()):
            raise ValueError(
                f"Valores inválidos para propriedades: {args_props}, deve ser string."
            )

        if values_as_all := {k: v for k, v in args_props.items() if v == "all"}:
            if (
                count_values_as_all := list(values_as_all.keys())
                and len(count_values_as_all) > 1
            ):
                raise ValueError(
                    f'A busca de instâncias como "all" deve ser definida apenas para uma propriedade: {count_values_as_all}'
                )
            if values_as_not_all := {v for v in args_props.values() if v != "all"}:
                raise ValueError(
                    f'Busca de instâncias como "all" não pode ser combinada com outras propriedades: {values_as_not_all}'
                )
            prop_key = list(values_as_all.keys())[0]
            instances = [getattr(inst, f"_{prop_key}") for inst in instances]
        else:
            research_arg = args_research.get("restrict", False)
            key_arg = args_props.get("key")

            if key_arg and any(k in args_props for k in kw_prop if k != "key"):
                raise ValueError(
                    f"Argumento key não pode ser combinado com outros argumentos de propriedades."
                )

            if key_arg:
                instances = [inst for inst in instances if inst._key == key_arg]
                if len(instances) > 1:
                    raise ValueError(
                        f"Múltiplas instâncias encontradas para a chave fornecida: {key_arg}"
                    )
            else:
                instances = reduce(
                    lambda acc, kv: [
                        inst
                        for inst in acc
                        if getattr(inst, f"_{kv[0]}")
                        and (
                            getattr(inst, f"_{kv[0]}") == kv[1]
                            if not research_arg
                            else re.search(kv[1], getattr(inst, f"_{kv[0]}"), re.I)
                        )
                    ],
                    args_props.items(),
                    instances,
                )

            for kw_filter, value in args_filters.items():
                if kw_filter == "is_trading_suspended":
                    instances = [
                        inst
                        for inst in instances
                        if inst._is_trading_suspended == value
                    ]
                if kw_filter == "exchange_is_open":
                    instances = [
                        inst for inst in instances if inst._exchange_is_open == value
                    ]
                if kw_filter == "assets":
                    instances = [(inst, inst._assets) for inst in instances]

            return instances

    @classmethod
    def get_available_symbols(cls) -> list["ActiveSymbol"]:
        """Retorna os símbolos atualmente abertos e disponíveis para negociação."""
        return sorted(
            [
                inst
                for inst in cls._instances
                if (inst._exchange_is_open and not inst._is_trading_suspended)
            ],
            key=lambda x: x._key,
        )

    @classmethod
    def get_assets_by_symbol(cls, symbol):
        return [
            [inst, inst._assets]
            for inst in cls._instances
            if inst._symbol == symbol
        ]

    @classmethod
    def filter_symbols_by_type(cls, contract_type, restrict=False):
        keys_from_assets = [
            asset_index.key
            for asset_index in Asset.get_by_modality(
                modality=contract_type, restrict=restrict
            )
        ]
        return [
            [inst, [asset for asset in inst if asset.key in keys_from_assets]]
            for inst in cls._instances
            if any(asset.key in keys_from_assets for asset in inst)
        ]

    @classmethod
    def get_symbols_by_duration(cls, digit, unit, fit_in_units=True):
        keys_from_assets = [
            asset_index.key
            for asset_index in Asset.get_by_duration(
                digit=digit, unit=unit, fit_in_units=fit_in_units
            )
        ]
        return [
            [inst, [asset for asset in inst if asset.key in keys_from_assets]]
            for inst in cls._instances
            if any(asset.key in keys_from_assets for asset in inst)
        ]

    # endregion


def populate(
    *, lst_active_symbols: list[dict], lst_asset_index: list[list] | None = None
) -> None:
    """Popula os caches de Asset e ActiveSymbol a partir das respostas da Deriv API."""
    symbols_dict: dict[str, dict[str, Any]] = {}
    lst_asset_index = lst_asset_index or []

    # 1. Processar matriz de parâmetros/contratos (asset_index) se disponível
    for asset_index in lst_asset_index:
        if not asset_index or len(asset_index) < 3:
            continue
        symbol = asset_index[0]
        display_name = asset_index[1]
        lst_assets = []
        for parameter in asset_index[2]:
            try:
                lst_assets.append(
                    Asset(
                        group=parameter[0],
                        modality=parameter[1],
                        digit_min=parameter[2][:-1] if parameter[2] else None,
                        unit_min=parameter[2][-1] if parameter[2] else None,
                        digit_max=parameter[3][:-1] if parameter[3] else None,
                        unit_max=parameter[3][-1] if parameter[3] else None,
                    )
                )
            except Exception as exc:
                logger.debug(f"Não foi possível criar Asset para {symbol}: {exc}")

        sym_value_dict = symbols_dict.setdefault(symbol, {})
        sym_value_dict["display_name"] = display_name
        sym_value_dict["assets_indexes"] = sorted(lst_assets, key=lambda x: x._key)

    # 2. Processar símbolos ativos (active_symbols)
    for act_sym in lst_active_symbols:
        symbol = act_sym.get("symbol") or act_sym.get("underlying_symbol")
        if not symbol:
            continue

        sym_value_dict = symbols_dict.setdefault(symbol, {})

        display_name = (
            act_sym.get("display_name")
            or act_sym.get("underlying_symbol_name")
            or sym_value_dict.get("display_name")
            or symbol
        )
        market = act_sym.get("market") or ""
        market_display_name = act_sym.get("market_display_name") or market.replace("_", " ").title()
        sub_market = act_sym.get("sub_market") or act_sym.get("submarket") or ""
        submarket_display_name = act_sym.get("submarket_display_name") or sub_market.replace("_", " ").title()

        sym_value_dict["display_name"] = display_name
        sym_value_dict["exchange_is_open"] = bool(act_sym.get("exchange_is_open", 1))
        sym_value_dict["is_trading_suspended"] = bool(act_sym.get("is_trading_suspended", 0))
        sym_value_dict["market"] = market
        sym_value_dict["market_display_name"] = market_display_name
        sym_value_dict["sub_market"] = sub_market
        sym_value_dict["submarket_display_name"] = submarket_display_name

    # 3. Instanciar ActiveSymbol no cache
    for symbol, value_dict in symbols_dict.items():
        ActiveSymbol(
            symbol=symbol,
            display_name=value_dict.get("display_name") or symbol,
            assets=value_dict.get("assets_indexes", []),
            exchange_is_open=value_dict.get("exchange_is_open", True),
            is_trading_suspended=value_dict.get("is_trading_suspended", False),
            market=value_dict.get("market", ""),
            market_display_name=value_dict.get("market_display_name", ""),
            sub_market=value_dict.get("sub_market", ""),
            submarket_display_name=value_dict.get("submarket_display_name", ""),
        )


async def sync_symbols_cache(service: Any) -> int:
    """Consulta active_symbols e asset_index via service.send() e popula as instâncias em memória."""
    logger.info("Iniciando sincronização do cache de símbolos da Deriv API...")

    resp_active_symbols = {}
    try:
        resp_active_symbols = await service.send({"active_symbols": "brief"})
    except Exception as exc:
        logger.error(f"Erro ao consultar active_symbols na Deriv API: {exc}")

    resp_asset_index = {}
    try:
        resp_asset_index = await service.send({"asset_index": 1})
        if "error" in resp_asset_index:
            logger.debug(
                f"asset_index não disponível no endpoint: {resp_asset_index['error'].get('message')}"
            )
            resp_asset_index = {}
    except Exception as exc:
        logger.debug(f"asset_index não disponível: {exc}")
        resp_asset_index = {}

    lst_active_symbols = resp_active_symbols.get("active_symbols", [])
    lst_asset_index = resp_asset_index.get("asset_index", [])

    if lst_active_symbols:
        Asset.clear()
        ActiveSymbol.clear()
        populate(
            lst_active_symbols=lst_active_symbols,
            lst_asset_index=lst_asset_index,
        )
        total = len(ActiveSymbol.get_all())
        logger.info(
            f"Cache de símbolos sincronizado com sucesso: {total} ativos carregados ({len(Asset.get_all())} modalidades)."
        )
        return total

    logger.warning("Nenhum símbolo retornado pela Deriv API para active_symbols.")
    return 0


def get_active_synthetic_symbols() -> list[dict[str, Any]]:
    """Retorna lista serializável de ativos sintéticos abertos para negociação."""
    available = ActiveSymbol.get_available_symbols()
    synthetic = [
        {
            "symbol": inst.symbol,
            "display_name": inst.display_name,
            "market": inst.market,
            "market_display_name": inst.market_display_name,
            "sub_market": inst.sub_market,
            "submarket_display_name": inst.submarket_display_name,
        }
        for inst in available
        if inst.market == "synthetic_index"
        or "synthetic" in (inst.market or "").lower()
    ]

    # Fallback caso os ativos estejam categorizados de forma ampla
    if not synthetic and available:
        synthetic = [
            {
                "symbol": inst.symbol,
                "display_name": inst.display_name,
                "market": inst.market,
                "market_display_name": inst.market_display_name,
                "sub_market": inst.sub_market,
                "submarket_display_name": inst.submarket_display_name,
            }
            for inst in available
        ]

    return sorted(synthetic, key=lambda x: x["symbol"])
