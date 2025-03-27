import asyncio
import re
from functools import reduce
from pprint import pprint as pp
from util import check_str
from connection import ConnManager, AppDashboard
import request as req

def line(value: str):
    ln = f'\n{"-"*100}'
    print(ln)
    result = eval(value)

    if isinstance(result, list):
        ln = len(result)
        print(f'{value} - show {5 if ln >=5 else ln} from: {ln}\n')
        pp(result[:5])
    else:
        print(f'{value}:\n')
        pp(result)

class Asset:
    _instances = []

    def __new__(cls, *, group, modality, digit_min, unit_min, digit_max, unit_max):
        if (not check_str(group)) or (not check_str(modality)):
            raise ValueError(f'String(s) inválida(s) ou nula(s) para group:{group} e/ou modality:{modality}.')
    
        min_max_info = cls.get_min_max_info(digit_min=digit_min, unit_min=unit_min, digit_max=digit_max, unit_max=unit_max)
        
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
        
        key = f'{group}{modality}'
        srt_repr = f'{group:>12} — {modality:<26}'
        has_duration = False
        
        if min_max_info:
            digit_min = min_max_info.get('min_info').get('digit')
            unit_min = min_max_info.get('min_info').get('unit')
            key_min = min_max_info.get('min_info').get('key')
            index_min = min_max_info.get('min_info').get('index')
            min_duration = min_max_info.get('min_info').get('duration')
            
            digit_max = min_max_info.get('max_info').get('digit')
            unit_max = min_max_info.get('max_info').get('unit')
            key_max = min_max_info.get('max_info').get('key')
            index_max = min_max_info.get('max_info').get('index')
            max_duration = min_max_info.get('max_info').get('duration')
            
            key = key + key_min + key_max
            srt_repr = srt_repr + f' {min_duration:>3} {max_duration:>4}'
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

    #region TradeParameter_InstancesMembers
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
    #endregion

    #region TradeParameter_ClassMembers
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
                raise ValueError(f"Múltiplas instâncias encontradas para a chave fornecida: {insts}")
            return insts[0]
        else:
            insts = [inst for inst in cls._instances if inst._key == value]
            if not insts:
                pattern = re.compile(value, re.I)
                insts = [inst for inst in cls._instances if pattern.search(inst._str_repr)]
            if not insts:
                insts = [inst for inst in cls._instances if value in inst._group or value in inst._modality]
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
        return sorted([inst for inst in cls._instances if (pattern.search(inst._group) if not restrict else pattern.fullmatch(inst._group))], key=lambda x: x._key)

    @classmethod
    def get_by_modality(cls, modality, *, restrict=False):
        pattern = re.compile(modality, flags=re.I)
        return sorted([inst for inst in cls._instances if (pattern.search(inst.modality) if not restrict else pattern.fullmatch(inst.modality))], key=lambda x: x._key)

    @classmethod
    def get_by_duration(cls, *, digit, unit, fit_in_units=True):
        drt_info = cls.get_info_duration(digit=digit, unit=unit)
        if drt_info:
            if fit_in_units:
                instances = [inst for inst in cls._instances if inst._has_duration and inst._index_min == inst._index_max == drt_info.get('index') and inst._digit_min <= drt_info.get('digit') <= inst._digit_max]
            else:
                instances = [inst for inst in cls._instances if inst._has_duration and inst._key_min <= drt_info.get('key') <= inst._key_max]
            return sorted(instances, key=lambda x: x._key)
        return []

    @classmethod
    def get_groups(cls):
        return sorted({inst._group for inst in cls._instances})

    @classmethod
    def get_modalities(cls):
        return sorted({inst._modality for inst in cls._instances})
    #endregion

    #region TradeParameter_Static
    @staticmethod
    def get_info_duration(*, digit, unit):
        if digit is None and unit is None:
            return {}
        
        pattern = re.compile(r'^[123456789]+0*[tsmhd]{1}$', re.I)
        if not pattern.fullmatch(duration := f'{digit}{unit}'):
            raise ValueError(f'{digit}{unit} não é um duration válido.')
        
        index = ['t', 's', 'm', 'h', 'd'].index(unit)
        key = f'{index}{digit.zfill(5)}'
        digit = int(digit)
        return {'digit': digit, 'unit': unit, 'duration': duration, 'index': index, 'key': key}

    @staticmethod
    def get_min_max_info(*, digit_min, unit_min, digit_max, unit_max):
        if (not digit_min) and (not unit_min) and (not digit_max) and (not unit_max):
            return {}
        min_info = Asset.get_info_duration(digit=digit_min, unit=unit_min)
        max_info = Asset.get_info_duration(digit=digit_max, unit=unit_max)
        if (min_info and not max_info) or (max_info and not min_info):
            raise ValueError('Min e Max devem ter valores simultâneos válidos ou nulos.')
        if min_info.get('key') > max_info.get('key'):
            raise ValueError('Min apresenta duração maior que Max.')
        return {'min_info': min_info, 'max_info': max_info}
    #endregion

class ActiveSymbol:
    _instances = []

    def __new__(cls, *, symbol, display_name, assets, exchange_is_open, is_trading_suspended, market, market_display_name, sub_market, submarket_display_name):
        if not check_str(symbol):
            raise ValueError(f'String(s) inválida(s) ou nula(s) para symbol:{symbol}')
        
        key = f'{not is_trading_suspended}{not exchange_is_open}{market}{sub_market}{symbol}'
        instance = cls.find(key=key)
        srt_repr = f'{market_display_name if market_display_name else "":<16} {submarket_display_name if submarket_display_name else "":<19} {display_name}{"(XX)" if is_trading_suspended else ""} {"" if exchange_is_open else " — closed":>10}'
        
        if not instance:
            instance = super().__new__(cls)
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

    #region ActiveSymbol_InstancesMembers
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
    #endregion

    #region ActiveSymbol_ClassMembers
    @classmethod
    def clear(cls):
        cls._instances.clear()

    @classmethod
    def find(cls, **kwargs):
        kw_research = ['restrict']
        kw_filter = ['assets', 'exchange_is_open', 'is_trading_suspended']
        kw_prop = ['key', 'symbol', 'display_name', 'market', 'market_display_name', 'sub_market', 'submarket_display_name']

        instances = sorted(cls._instances, key=lambda x: x._key)

        if not kwargs:
            return instances

        if kw_out := {kw: value for kw, value in kwargs.items() if kw not in kw_research + kw_filter + kw_prop}:
            raise ValueError(f'Argumentos inválidos: {kw_out}')

        args_research = {kw: value for kw, value in kwargs.items() if kw in kw_research}
        args_filters = {kw: value for kw, value in kwargs.items() if kw in kw_filter}
        args_props = {kw: value for kw, value in kwargs.items() if kw in kw_prop}

        if args_research and any(value for value in args_research.values() if not isinstance(value, bool)):
            raise ValueError(f'Valores inválidos para pesquisa: {args_research}, deve ser booleano.')

        if args_filters and any(value for value in args_filters.values() if not isinstance(value, bool)):
            raise ValueError(f'Valores inválidos para filtro: {args_filters}, deve ser booleano.')

        if args_props and any(not check_str(value) for value in args_props.values()):
            raise ValueError(f'Valores inválidos para propriedades: {args_props}, deve ser string.')

        if values_as_all := {k: v for k, v in args_props.items() if v == 'all'}:
            if count_values_as_all := list(values_as_all.keys()) and len(count_values_as_all) > 1:
                raise ValueError(f'A busca de instâncias como "all" deve ser definida apenas para uma propriedade: {count_values_as_all}')
            if values_as_not_all := {v for v in args_props.values() if v != 'all'}:
                raise ValueError(f'Busca de instâncias como "all" não pode ser combinada com outras propriedades: {values_as_not_all}')
            prop_key = list(values_as_all.keys())[0]
            instances = [getattr(inst, f'_{prop_key}') for inst in instances]
        else:
            research_arg = args_research.get('restrict', False)
            key_arg = args_props.get('key')

            if key_arg and any(k in args_props for k in kw_prop if k != 'key'):
                raise ValueError(f'Argumento key não pode ser combinado com outros argumentos de propriedades.')

            if key_arg:
                instances = [inst for inst in instances if inst._key == key_arg]
                if len(instances) > 1:
                    raise ValueError(f'Múltiplas instâncias encontradas para a chave fornecida: {key_arg}')
            else:
                instances = reduce(
                    lambda acc, kv: [
                        inst for inst in acc 
                        if getattr(inst, f'_{kv[0]}') and (
                            getattr(inst, f'_{kv[0]}') == kv[1] if not research_arg 
                            else re.search(kv[1], getattr(inst, f'_{kv[0]}'), re.I)
                        )
                    ],
                    args_props.items(),
                    instances
                )
                
            for kw_filter, value in args_filters.items():
                if kw_filter == 'is_trading_suspended':
                    instances = [inst for inst in instances if inst._is_trading_suspended == value]
                if kw_filter == 'exchange_is_open':
                    instances = [inst for inst in instances if inst._exchange_is_open == value]
                if kw_filter == 'assets':
                    instances = [(inst, inst._assets) for inst in instances]

            return instances

    @classmethod
    def get_available_symbols(cls):
        return sorted([inst for inst in cls._instances if (inst._exchange_is_open and not inst._is_trading_suspended)], key=lambda x: x._key)
    
    @classmethod
    def get_assets_by_symbol(cls, symbol):
        return [[inst, inst._assets] for inst in cls._instances if inst._symbol == symbol]

    @classmethod
    def filter_symbols_by_type(cls, contract_type, restrict=False):
        keys_from_assets = [asset_index.key for asset_index in Asset.get_by_modality(modality=contract_type, restrict=restrict)]
        return [[inst, [asset for asset in inst if asset.key in keys_from_assets]] for inst in cls._instances if any(asset.key in keys_from_assets for asset in inst)]

    @classmethod
    def get_symbols_by_duration(cls, digit, unit, fit_in_units=True):
        keys_from_assets = [asset_index.key for asset_index in Asset.get_by_duration(digit=digit, unit=unit, fit_in_units=fit_in_units)]
        return [[inst, [asset for asset in inst if asset.key in keys_from_assets]] for inst in cls._instances if any(asset.key in keys_from_assets for asset in inst)]
    #endregion

def populate(*, lst_active_symbols, lst_asset_index):
    symbols_dict = {}
    for asset_index in lst_asset_index:
        symbol = asset_index[0]
        display_name = asset_index[1]
        lst_assets = [Asset(
            group=parameter[0],
            modality=parameter[1],
            digit_min=parameter[2][:-1] if parameter[2] else None,
            unit_min=parameter[2][-1] if parameter[2] else None,
            digit_max=parameter[3][:-1] if parameter[3] else None,
            unit_max=parameter[3][-1] if parameter[3] else None) for parameter in asset_index[2]]

        sym_value_dict = symbols_dict.setdefault(symbol, {})
        sym_value_dict.setdefault('display_name', display_name)
        sym_value_dict.setdefault('assets_indexes', sorted(lst_assets, key=lambda x: x._key))

    for act_sym in lst_active_symbols:
        symbol = act_sym.get('symbol')
        value_dict = symbols_dict.get(symbol)
        if not value_dict:
            raise ValueError(f'Não foi possível encontrar o symbol:{symbol} no dicionário de symbols_dict.')

        exchange_is_open = act_sym.get('exchange_is_open')
        is_trading_suspended = act_sym.get('is_trading_suspended')
        market = act_sym.get('market')
        market_display_name = act_sym.get('market_display_name')
        sub_market = act_sym.get('sub_market')
        submarket_display_name = act_sym.get('submarket_display_name')

        value_dict.setdefault('exchange_is_open', exchange_is_open)
        value_dict.setdefault('is_trading_suspended', is_trading_suspended)
        value_dict.setdefault('market', market)
        value_dict.setdefault('market_display_name', market_display_name)
        value_dict.setdefault('sub_market', sub_market)
        value_dict.setdefault('submarket_display_name', submarket_display_name)

    for symbol, value_dict in symbols_dict.items():
        ActiveSymbol(
            symbol=symbol,
            display_name=value_dict.get('display_name'),
            assets=value_dict.get('assets_indexes'),
            exchange_is_open=value_dict.get('exchange_is_open'),
            is_trading_suspended=value_dict.get('is_trading_suspended'),
            market=value_dict.get('market'),
            market_display_name=value_dict.get('market_display_name'),
            sub_market=value_dict.get('sub_market'),
            submarket_display_name=value_dict.get('submarket_display_name'))

def set_connection() -> ConnManager:
    app_name = AppDashboard.get_key_names().get('app')[0]
    token_name = AppDashboard.get_key_names().get('token')[0]
    if app_name and token_name:
        return ConnManager(app_name=app_name, token_name=token_name)
    else:
        raise ValueError(f'app_name:{app_name} ou token_name{token_name} inválido.')

def show_Asset_methods():
    line('Asset.get_all()')
    line('Asset.find("callputHigher/Lower400001400365", only_key=True)')
    line('Asset.find("put")')
    line('Asset.find("fall")')
    line('Asset.get_by_group("put")')
    line('Asset.get_by_group("callput", restrict=True)')
    line('Asset.get_by_modality("Rise/Fall")')
    line('Asset.get_by_modality("Rise/Fall", restrict=True)')
    line('Asset.get_by_duration(digit="7", unit="t")')
    line('Asset.get_by_duration(digit="45", unit="h", fit_in_units=False)')
    line('Asset.get_groups()')
    line('Asset.get_modalities()')
    print()

def show_ActiveSymbol_methods():
    line('ActiveSymbol.find()')
    line('ActiveSymbol.find(symbol="WLDAUD")')
    line('ActiveSymbol.find(market_display_name="Forex", restrict=False)')
    line('ActiveSymbol.find(symbol="WLDAUD", assets=True)')
    line('ActiveSymbol.find(exchange_is_open=True, is_trading_suspended=False, assets=True)')
    line('ActiveSymbol.filter_symbols_by_type("fall")')
    line('ActiveSymbol.get_symbols_by_duration("5", "t", fit_in_units=True)')
    line('ActiveSymbol.get_symbols_by_duration("1", "d", fit_in_units=False)')

async def main():
    conn = set_connection()
    await conn.connect()
    resp_asset_index = await conn.send_request(req.ASSET_INDEX)
    resp_active_symbols = await conn.send_request(req.ACTIVE_SYMBOLS)
    
    if resp_asset_index and resp_active_symbols:
        lst_asset_index = resp_asset_index.get('asset_index')
        lst_active_symbols = resp_active_symbols.get('active_symbols')
        if lst_asset_index and lst_active_symbols:
            Asset.clear()
            ActiveSymbol.clear()
            populate(lst_active_symbols=lst_active_symbols, lst_asset_index=lst_asset_index)
            show_ActiveSymbol_methods()
            # show_Asset_methods()
    await conn.disconnect()

if __name__ == '__main__':
    asyncio.run(main())