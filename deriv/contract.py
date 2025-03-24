import asyncio
import re
from pprint import pprint as pp
from util import check_str
from connection import ConnManager, AppDashboard
import request as req

def line(value: str):
    ln = f'\n{"-"*100}'
    print(ln)
    print(f'{value}:\n')

    pp(eval(value))

class AssetParameter:
    _instances = []

    def __new__(cls,*, group, modality, digit_min, unit_min, digit_max, unit_max):
        
        if (not check_str(group)) or (not check_str(modality)):
            raise ValueError(f'String(s) inválida(s) ou nula(s) para group:{group} e/ou modality:{modality}.')
    
        min_max_info = cls.get_min_max_info(digit_min= digit_min, unit_min= unit_min, digit_max= digit_max, unit_max= unit_max)
        
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
        
        instance = AssetParameter.find(key, only_key=True)

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
    def find(cls, value, only_key=False):
        if only_key:
            insts = [inst for inst in cls._instances if inst._key == value]
            if not insts:
                return None
            if len(insts) > 1:
                raise ValueError(f"Múltiplas instâncias encontradas para a chave fornecida: {insts}")
            return insts[0]
        else:
            # Tenta por key primeiro
            insts = [inst for inst in cls._instances if inst._key == value]
            if not insts:
                # Tenta por str_repr com regex
                pattern = re.compile(value, re.I)
                insts = [inst for inst in cls._instances if pattern.search(inst._str_repr)]
            if not insts:
                # Tenta por group ou modality
                insts = [inst for inst in cls._instances if value in inst._group or value in inst._modality]
            return insts  # Retorna a lista, mesmo que vazia ou com múltiplos itens

    @classmethod
    def get_all(cls):
        return sorted(cls._instances, key=lambda x: x._key)
    
    @classmethod
    def get_all_keys(cls):
        return [inst._key for inst in sorted(cls._instances, key= lambda x: x._key)]

    @classmethod
    def get_by_group(cls, group, *, restricted= False):
        pattern = re.compile(group, flags=re.I)
        return sorted([inst for inst in cls._instances if (pattern.search(inst._group) if not restricted else pattern.fullmatch(inst._group))], key=lambda x: x._key)

    @classmethod
    def get_by_modality(cls, modality, *, restricted= False):
        pattern = re.compile(modality, flags= re.I)
        return sorted([inst for inst in cls._instances if (pattern.search(inst.modality) if not restricted else pattern.fullmatch(inst.modality) )], key=lambda x: x._key)

    @classmethod
    def get_by_duration(cls, *, digit, unit, fit_in_units= True):
        
        drt_info = cls.get_info_duration(digit= digit, unit= unit)
        
        if drt_info:
            if fit_in_units:
                instances = [inst for inst in cls._instances if inst._has_duration and inst._index_min == inst._index_max == drt_info.get('index') and inst._digit_min <= drt_info.get('digit') <= inst._digit_max]
            else:
                instances = [inst for inst in cls._instances if inst._has_duration and inst._key_min <= drt_info.get('key') <= inst._key_max]
            
            return sorted(instances, key= lambda x: x._key)

    @classmethod
    def get_groups(cls):
        return sorted({inst._group for inst in cls._instances})

    @classmethod
    def get_modalities(cls):
        return sorted({inst._modality for inst in cls._instances})
    
    # @classmethod
    # def get_symbols(cls, *, display_name: bool= True):
    #     return [sym[2] if display_name else sym[0] for sym in sorted(cls._info_symbols.values(), key= lambda x: x[3])]

    # @classmethod
    # def get_by_symbol(cls, symbol: str):
    #     return sorted([inst for inst in cls._instances if symbol  in inst._symbols], key= lambda x: x._key)

    # @classmethod
    # def get_symbols_by_group(cls, group, *, display_name: bool= True, restricted: bool= True):
    #     instances = cls.get_by_group(group, restricted=restricted)
    #     symbols = {symbol for inst in instances for symbol in inst._symbols}
    #     return [(cls._info_symbols.get(sym)[2] if display_name else cls._info_symbols.get(sym)[0])  for sym in sorted(symbols)]

    # @classmethod
    # def get_symbols_by_modality(cls, modality: str, *, display_name: bool= True, restricted: bool= True):
    #     instances = cls.get_by_modality(modality= modality, restricted= restricted)
    #     symbols = {symbol for inst in instances for symbol in inst._symbols}
    #     return [(cls._info_symbols.get(sym)[2] if display_name else cls._info_symbols.get(sym)[0]) for sym in sorted(symbols, key= lambda x: str.lower(x))]

    # @classmethod
    # def get_symbols_by_display_name(cls, display_name: str):
    #     pattern = re.compile(display_name, flags= re.I)
    #     return [vlws[2] for vlws in sorted(cls._info_symbols.values(), key= lambda x: x[3]) if pattern.search(vlws[1])]
#endregion

#region TradeParameter_Static
    @staticmethod
    def get_info_duration(*, digit, unit):
        pattern = re.compile(r'^[123456789]+0*[tsmhd]{1}$', re.I)
            
        if not pattern.fullmatch(duration:=f'{digit}{unit}'):
            raise ValueError(f'{digit}{unit} não é um duration válido.')
            
        index = ['t','s','m','h','d'].index(unit)
        key = f'{index}{digit.zfill(5)}'
        digit = int(digit)

        return {'digit':digit, 'unit':unit, 'duration':duration, 'index':index, 'key':key}

    @staticmethod
    def get_min_max_info(*, digit_min, unit_min, digit_max, unit_max):

        if (not digit_min) and (not unit_min) and (not digit_max) and (not unit_max):
            return {}

        min_info = AssetParameter.get_info_duration(digit=digit_min, unit=unit_min)
        max_info = AssetParameter.get_info_duration(digit=digit_max, unit=unit_max)
        
        if (min_info and not max_info) or (max_info and not min_info):
            raise ValueError('Min e Max devem ter valores simultâneos válidos ou nulos.')
        
        if min_info.get('key') > max_info.get('key'):
            raise ValueError('Min apresenta duração maior que Max.')
        
        return {'min_info':min_info, 'max_info':max_info}
#endregion

class ActiveSymbol:
    _instances = []
    
    def __new__(cls, *
                , symbol
                , display_name
                , parameters
                , exchange_is_open
                , is_trading_suspended
                , market
                , market_display_name
                , sub_market
                , submarket_display_name):
        
        if (not check_str(symbol)):
            raise ValueError(f'String(s) inválida(s) ou nula(s) para symbol:{symbol}')
        
        key = f'{not is_trading_suspended}{not exchange_is_open}{market}{sub_market}{symbol}'
        instance = cls.find(key, only_key=True)
        srt_repr = f'{market_display_name if market_display_name else "":<16} {submarket_display_name if submarket_display_name else "":<19} {display_name}{"(XX)" if is_trading_suspended else ""} {"" if exchange_is_open else " — closed":>10}'
        
        if not instance:
            instance = super().__new__(cls)
            instance._symbol = symbol
            instance._display_name = display_name
            instance._parameters =  [p for p in sorted(parameters, key= lambda x: x.key)]
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
    def parameters(self):
        return self._parameters
    
    def __str__(self):
        return self._str_repr
    
    def __repr__(self):
        return self._str_repr
#endregion

#region ActiveSymbol_ClassMembers
    @classmethod
    def clear(cls):
        cls._instances.clear()
        
    @classmethod
    def find(cls, value, only_key=False):
        if only_key:
            insts = [inst for inst in cls._instances if inst._key == value]
            if not insts:
                return None
            if len(insts) > 1:
                raise ValueError(f"Múltiplas instâncias encontradas para a chave fornecida: {insts}")
            return insts[0]
        else:
            # Tenta por symbol primeiro
            insts = [inst for inst in cls._instances if inst._symbol == value]
            if not insts:
                # Tenta por str_repr com regex
                pattern = re.compile(value, re.I)
                insts = [inst for inst in cls._instances if pattern.search(inst._str_repr)]
            if not insts:
                # Tenta por market_display_name ou submarket_display_name
                insts = [inst for inst in cls._instances if value in (inst._market_display_name or '') or value in (inst._submarket_display_name or '')]
            if not insts:
                # Tenta por key por último
                insts = [inst for inst in cls._instances if inst._key == value]
            return insts  # Retorna a lista, mesmo que vazia ou com múltiplos itens
        
    @classmethod
    def get_all(cls,*, parameters = False):
        insts = sorted(cls._instances, key=lambda x: x._key)
        
        if parameters:
            return  [(inst, inst._parameters) for inst in insts]

        return insts

    @classmethod
    def get_parameters_by_symbol(cls, symbol):
        instances = cls.find(symbol, only_key=False)
        if not instances:
            return []
        if not isinstance(instances, list):
            instances = [instances]  # Se for uma única instância, converte para lista
        return [(inst._symbol, inst.parameters) for inst in instances]
#endregion

def populate(*, lst_active_symbols, lst_asset_index):
        
        symbols_dict = {}

        for asset_index in lst_asset_index:
            symbol = asset_index[0]
            display_name = asset_index[1]
            lst_parameters = [AssetParameter(
                group= parameter[0]
                , modality= parameter[1] 
                , digit_min= parameter[2][:-1] if parameter[2] else None
                , unit_min= parameter[2][-1] if parameter[2] else None
                , digit_max= parameter[3][:-1] if parameter[3] else None
                , unit_max = parameter[3][-1] if parameter[3] else None) for parameter in asset_index[2]]
            
            sym_value_dict = symbols_dict.setdefault(symbol, {})
            sym_value_dict.setdefault('display_name', display_name)
            sym_value_dict.setdefault('assets_indexes', sorted(lst_parameters, key= lambda x: x._key))

        for act_sym in lst_active_symbols:
            value_dict = symbols_dict.get(symbol)
            
            if not value_dict:
                raise ValueError(f'Não foi possível encontrar o symbol:{symbol} no dicionário de symbols_dict.')
            
            symbol = act_sym.get('symbol')
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
                symbol= symbol
                , display_name= value_dict.get('display_name')
                , parameters= value_dict.get('assets_indexes')
                , exchange_is_open= value_dict.get('exchange_is_open')
                , is_trading_suspended= value_dict.get('is_trading_suspended')
                , market= value_dict.get('market')
                , market_display_name= value_dict.get('market_display_name')
                , sub_market= value_dict.get('sub_market')
                , submarket_display_name= value_dict.get('submarket_display_name'))

def set_connection() -> ConnManager:
    app_name = AppDashboard.get_key_names().get('app')[0]
    token_name = AppDashboard.get_key_names().get('token')[0]
    if app_name and token_name:
        return ConnManager(app_name=app_name, token_name=token_name)
    else:
        raise ValueError(f'app_name:{app_name} ou token_name{token_name} inválido.')

def show_AssetParameter_methods():
    #line(Asset.find(group="callput", modality="Higher/Lower", min_max_info= Asset.get_min_max_info(digit_min='5', unit_min='t', digit_max='7' unit_max='d')))
    line('AssetParameter.get_all()')
    line('AssetParameter.find("callputHigher/Lower400001400365", only_key= True)')
    line('AssetParameter.find("put")')
    line('AssetParameter.find("fall")')
    line('AssetParameter.get_by_group("put")')
    line('AssetParameter.get_by_group("callput", restricted=True)')
    line('AssetParameter.get_by_modality("Rise/Fall")')
    line('AssetParameter.get_by_modality("Rise/Fall", restricted=True)')
    # line('AssetParameter.get_by_symbol("WLDAUD")')
    line('AssetParameter.get_by_duration(digit = "7", unit ="t")')
    line('AssetParameter.get_by_duration(digit = "45", unit ="h", fit_in_units=False)')
    line('AssetParameter.get_groups()')
    line('AssetParameter.get_modalities()')
    # line('AssetParameter.get_symbols()')
    # line('AssetParameter.get_symbols(display_name= False)')
    # line('AssetParameter.get_symbols_by_group("reset")')
    # line('AssetParameter.get_symbols_by_modality("equal")')
    # line('AssetParameter.get_symbols_by_modality("equal",restricted=False)')
    # line('AssetParameter.get_symbols_by_display_name("AUD")')
    print()

def show_ActiveSymbol_methods():
    line('ActiveSymbol.get_all(parameters= True)')
    line('ActiveSymbol.find("WLDAUD", only_key= False)')
    line('ActiveSymbol.find("AUD")')
    line('ActiveSymbol.get_parameters_by_symbol("WLDAUD")')
    line('ActiveSymbol.get_parameters_by_symbol("AUD")')

async def main():
    conn = set_connection()
    await conn.connect()
    resp_asset_index = await conn.send_request(req.ASSET_INDEX)
    resp_active_symbols = await conn.send_request(req.ACTIVE_SYMBOLS)
    
    if resp_asset_index and resp_active_symbols:
        lst_asset_index = resp_asset_index.get('asset_index')
        lst_active_symbols = resp_active_symbols.get('active_symbols')
        #pp(lst_asset_index)
        #pp(lst_active_symbols)
        if lst_asset_index and lst_active_symbols:
            AssetParameter.clear()
            ActiveSymbol.clear()
            populate(lst_active_symbols= lst_active_symbols, lst_asset_index= lst_asset_index)
            #show_AssetParameter_methods()
            show_ActiveSymbol_methods()
    await conn.disconnect()

if __name__ == '__main__':
    asyncio.run(main())