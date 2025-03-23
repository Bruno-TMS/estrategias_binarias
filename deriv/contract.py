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

class AssetIndex:
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
        
        instance = AssetIndex.find(key)

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
    def find(cls, key):
        instances = [inst for inst in cls._instances if inst._key == key]

        if not instances:
            return None

        if 1 < len(instances):
            raise ValueError(f'instances{instances} > Asset_instances armazenou instâncias diferentes com mesmos valores.')

        return instances[0]

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
    
    @classmethod
    def clear(cls):
        cls._instances.clear()
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

    @classmethod
    async def populate(cls, connection:ConnManager):
        cls._instances.clear()
        response = await connection.send_request(req.ASSET_INDEX)

        assets = response.get('asset_index', False)

        if not assets:
            print(f'Valores inválidos para key "asset_index" em response.')
            return False

        pp(response)

        for asset in assets:
            symbol = asset[0]
            display_name = asset[1]
            param_trades = asset[2]
            for trade_info in param_trades:
                tp = AssetIndex(
                    group = trade_info[0]
                    , modality = trade_info[1]
                    , digit_min = trade_info[2][:-1] if trade_info[2] else None
                    , unit_min = trade_info[2][-1] if trade_info[2] else None
                    , digit_max = trade_info[3][:-1] if trade_info[3] else None
                    , unit_max = trade_info[3][-1] if trade_info[3] else None                
                )

        return True    
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

        min_info = AssetIndex.get_info_duration(digit=digit_min, unit=unit_min)
        max_info = AssetIndex.get_info_duration(digit=digit_max, unit=unit_max)
        
        if (min_info and not max_info) or (max_info and not min_info):
            raise ValueError('Min e Max devem ter valores simultâneos válidos ou nulos.')
        
        if min_info.get('key') > max_info.get('key'):
            raise ValueError('Min apresenta duração maior que Max.')
        
        if min_info and max_info:
            return {'min_info':min_info, 'max_info':max_info}
        
        raise ValueError(f'Erro não identificado para os valores de digit_min:{digit_min} unit_min:{unit_min} digit_max:{digit_max} unit_max:{unit_max}')
#endregion

class ActiveSymbol:
    _instances = []
    
    def __new__(cls
                , symbol
                , display_name
                , assets
                , exchange_is_open
                , is_trading_suspended
                , market
                , market_display_name
                , subgroup
                , subgroup_display_name
                , submarket
                , submarket_display_name):
        
        if (not check_str(symbol)):
            raise ValueError(f'String(s) inválida(s) ou nula(s) para symbol:{symbol}')
        
        key = symbol
        instance = cls.find(key)
        
        if not instance:
            instance = super().__new__(cls)
            instance._symbol = symbol
            instance._display_name = display_name
            instance._assets = assets
        return instance
    
    
    classmethod
    def find(cls, key):
        instances = [inst for inst in cls._instances if inst._key == key]

        if not instances:
            return None

        if 1 < len(instances):
            raise ValueError(f'instances{instances} > ActiveSymbol_instances armazenou instâncias diferentes com mesmos valores.')

        return instances[0]
    
    
    @classmethod
    def populate(cls, assets, symbols):
        cls._instances.clear()
        AssetIndex.clear()
        
        

        if not assets:
            print(f'Valores inválidos para key "asset_index" em response.')
            return False

        pp(response)

        for asset in assets:
            symbol = asset[0]
            display_name = asset[1]
            param_trades = asset[2]
            for trade_info in param_trades:
                tp = AssetIndex(
                    group = trade_info[0]
                    , modality = trade_info[1]
                    , digit_min = trade_info[2][:-1] if trade_info[2] else None
                    , unit_min = trade_info[2][-1] if trade_info[2] else None
                    , digit_max = trade_info[3][:-1] if trade_info[3] else None
                    , unit_max = trade_info[3][-1] if trade_info[3] else None                
                )

        return True    
    
def set_connection() -> ConnManager:
    app_name = AppDashboard.get_key_names().get('app')[0]
    token_name = AppDashboard.get_key_names().get('token')[0]
    if app_name and token_name:
        return ConnManager(app_name=app_name, token_name=token_name)
    else:
        raise ValueError(f'app_name:{app_name} ou token_name{token_name} inválido.')

def show_Asset_methods():
    #line(Asset.find(group="callput", modality="Higher/Lower", min_max_info= Asset.get_min_max_info(digit_min='5', unit_min='t', digit_max='7' unit_max='d')))
    line('AssetIndex.get_all()')
    line('AssetIndex.find("callputHigher/Lower400001400365")')
    line('AssetIndex.get_by_group("put")')
    line('AssetIndex.get_by_group("callput", restricted=True)')
    line('AssetIndex.get_by_modality("Rise/Fall")')
    line('AssetIndex.get_by_modality("Rise/Fall", restricted=True)')
    # line('AssetIndex.get_by_symbol("WLDAUD")')
    line('AssetIndex.get_by_duration(digit = "7", unit ="t")')
    line('AssetIndex.get_by_duration(digit = "45", unit ="h", fit_in_units=False)')
    line('AssetIndex.get_groups()')
    line('AssetIndex.get_modalities()')
    # line('AssetIndex.get_symbols()')
    # line('AssetIndex.get_symbols(display_name= False)')
    # line('AssetIndex.get_symbols_by_group("reset")')
    # line('AssetIndex.get_symbols_by_modality("equal")')
    # line('AssetIndex.get_symbols_by_modality("equal",restricted=False)')
    # line('AssetIndex.get_symbols_by_display_name("AUD")')
    print()

async def main():
    conn = set_connection()
    await conn.connect()
    response_asset_index = await conn.send_request(req.ASSET_INDEX)
    response_active_symbols = await conn.send_request(req.ACTIVE_SYMBOLS)
    
    if response_asset_index and response_active_symbols:
        assets = response_asset_index.get('asset_index')
        active_symbols = response_active_symbols.get('active_symbols')
        
        if assets and active_symbols:
            
        
    await AssetIndex.populate(conn)
    show_Asset_methods()
    await conn.disconnect()

if __name__ == '__main__':
    asyncio.run(main())