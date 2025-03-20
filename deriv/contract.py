import asyncio
import re
from pprint import pprint as pp
from util import check_str
from connection import ConnManager, AppDashboard
from request import asset_index

def line(value):
    ln = f'\n{"-"*100}'
    print(ln)
    print(f'{value}:\n')

    pp(eval(value))

class TradeParameter:
    _instances = []
    _instance = None

    def __new__(cls,*, group:str, modality:str, digit_min:str, unit_min:str, digit_max:str, unit_max:str):
        
        if (not check_str(group)) or (not check_str(modality)):
            raise ValueError(f'String(s) inválida(s) ou nula(s) para group:{group} e/ou modality:{modality}.')

        min_info = cls.get_info_duration(digit=digit_min, unit=unit_min)
        max_info = cls.get_info_duration(digit=digit_max, unit=unit_max)
        
        if min_info and max_info and min_info.get('key') > max_info.get('key'):
            raise ValueError(f'max_duration:{max_info.get("duration")} < min_duration:{min_info.get("duration")}')
        
        cls._instance = None
        cls._instance = TradeParameter.get_instance(
            group = group
            , modality = modality
            , digit_min = min_info.get('digit')
            , unit_min = min_info.get('unit')
            , digit_max = max_info.get('digit')
            , unit_max = max_info.get('unit')
            )
        
        if not cls._instance:
            cls._instance = super().__new__(cls)
            
            cls._instance._group = group
            cls._instance._modality = modality
            
            cls._instance._digit_min = min_info.get('digit')
            cls._instance._unit_min = min_info.get('unit')
            cls._instance._key_min = min_info.get('key')
            cls._instance._index_min = min_info.get('index')
            cls._instance._min_duration = min_info.get('duration')
            
            cls._instance._digit_max = max_info.get('digit')
            cls._instance._unit_max = max_info.get('unit')
            cls._instance._key_max = max_info.get('key')
            cls._instance._index_max = max_info.get('index')
            cls._instance._max_duration = max_info.get('duration')
            
            cls._instance._key = f'{group}{modality}{min_info.get("key")}'
            
            if min_info.get("duration"):
                cls._instance._str = f'{group:<12}  {modality:<26}   min:{min_info.get("duration"):>5}  max:{max_info.get("duration"):>5}'
            
            else:
                cls._instance._str = f'{group:<12}  {modality:<26}   min:" "  max:" "'
                
            cls._instance._symbols = set()
            cls._instances.append(cls._instance)

        return cls._instance

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
    def symbols(self):
        return tuple(self._symbols)
    
    def add_symbol(self, value:str):
        if not check_str(value):
            raise ValueError(f'String inválida ou nula para symbol:{value}.')
        self._symbols.add(value)
    
    def __str__(self):
        return self._str
    
    def __repr__(self):
        return self._str   
#endregion

#region TradeParameter_ClassMembers
    @classmethod
    def get_instance(cls,*, group:str, modality:str, digit_min:int, unit_min:str, digit_max:int, unit_max:str):
        instances = [inst for inst in cls._instances if (
            inst._group == group
            and inst._modality == modality
            and inst._digit_min == digit_min
            and inst._unit_min == unit_min
            and inst._digit_max == digit_max
            and inst._unit_max == unit_max)]

        if not instances:
            return None

        if len(instances) > 1:
            raise ValueError(f'Intances{instances} > TradeParameter _instances[] armazenou instâncias diferentes com mesmos valores.')

        return instances[0]

    @classmethod
    def get_instances(cls):
        return sorted(cls._instances, key=lambda x: x._key)

    @classmethod
    def get_instances_by_group(cls, group: str):
        pattern = re.compile(group, flags=re.I)
        return sorted([inst for inst in cls._instances if pattern.search(inst.group)], key=lambda x: x._key)

    @classmethod
    def get_instances_by_modality(cls, modality: str):
        pattern = re.compile(modality, flags=re.I)
        return sorted([inst for inst in cls._instances if pattern.search(inst.modality)], key=lambda x: x._key)

    @classmethod
    def get_instances_by_duration(cls, *, digit: str, unit: str, fit_in_units: bool = True):
        
        drt_info = cls.get_info_duration(digit=digit, unit=unit)
        
        if drt_info:
            if fit_in_units:
                instances = [inst for inst in cls._instances if inst._min_duration and inst._max_duration and inst._index_min == inst._index_max == drt_info.get('index') and inst._digit_min <= drt_info.get('digit') <= inst._digit_max]
            else:
                instances = [inst for inst in cls._instances if inst._min_duration and inst._max_duration and inst._key_min <= drt_info.get('key') <= inst._key_max]
            
            return sorted(instances, key= lambda x: x._key)
    
    @classmethod
    def get_instances_by_symbol(cls, symbol:str):
        return sorted([inst for inst in cls._instances if symbol  in inst._symbols], key= lambda x: x._key)
    
    @classmethod
    def get_groups(cls):
        return sorted({inst._group for inst in cls._instances})

    @classmethod
    def get_modalities(cls):
        return sorted({inst._modality for inst in cls._instances})
    
    @classmethod
    async def populate(cls, connection:ConnManager):
        cls._instances.clear()
        response = await connection.send_request(asset_index())

        assets = response.get('asset_index', False)

        if not assets:
            print(f'Valores inválidos para key "asset_index" em response.')
            return False
        
        pp(response)

        for asset in assets:
            symbol = asset[0]
            param_trades = asset[2]
            for trade_info in param_trades:
                tp = TradeParameter(
                    group = trade_info[0]
                    , modality = trade_info[1]
                    , digit_min = trade_info[2][:-1] if trade_info[2] else None
                    , unit_min = trade_info[2][-1] if trade_info[2] else None
                    , digit_max = trade_info[3][:-1] if trade_info[3] else None
                    , unit_max = trade_info[3][-1] if trade_info[3] else None                
                )
                tp.add_symbol(symbol)
                
        return True    
#endregion

#region TradeParameter_Static
    @staticmethod
    def get_info_duration(*, digit:str, unit:str)->{int,str}:
        if (not digit) and (not unit):
            return {}

        if (not check_str(digit)) or (not check_str(unit)):
            raise ValueError(f'{digit}{unit} não é um duration válido.')

        lst_units = ['t','s','m','h','d']
        if unit not in lst_units:
            raise ValueError(f'unit:{unit} não pertence a lista:{lst_units}.')

        try:
            digit = int(digit)

        except ValueError as e: 
            print(f'{e}:{e.args}')

        else:
            if digit <= 0:
                raise ValueError(f'{digit} <= 0.')

            duration = f'{digit}{unit}'
            index = lst_units.index(unit)
            key = f'{index}{str(digit).zfill(5)}'

            return {'digit':digit, 'unit':unit, 'duration':duration, 'index':index, 'key':key}
#endregion

def set_connection() -> ConnManager:
    app_name = AppDashboard.get_key_names().get('app')[0]
    token_name = AppDashboard.get_key_names().get('token')[0]
    if app_name and token_name:
        return ConnManager(app_name=app_name, token_name=token_name)
    else:
        raise ValueError(f'app_name:{app_name} ou token_name{token_name} inválido.')

def show_trade_parameters_methods():
    line('TradeParameter.get_instance(group="callput", modality="Higher/Lower", digit_min=5, unit_min="t", digit_max=1, unit_max="d")')
    line('TradeParameter.get_instances()')
    line('TradeParameter.get_instances_by_group("put")')
    line('TradeParameter.get_instances_by_modality("options")')
    line('TradeParameter.get_instances_by_symbol("WLDAUD")')
    line('TradeParameter.get_instances_by_duration(digit = "7", unit ="t")')
    line('TradeParameter.get_instances_by_duration(digit = "45", unit ="h", fit_in_units=False)')
    line('TradeParameter.get_groups()')
    line('TradeParameter.get_modalities()')
    print()

# def show_trade_symbol_methods():
#     line('TradeSymbol.get_instance("WLDAUD")')
#     line('TradeSymbol.get_instances()')
#     line('TradeSymbol.get_instances_full()')
#     line('TradeSymbol.get_instances_by_display_name("AUD")')

async def main():
    conn = set_connection()
    await conn.connect()
    await TradeParameter.populate(conn)
    show_trade_parameters_methods()
    #await TradeSymbol.populate(conn)
    #show_trade_symbol_methods()
    await conn.disconnect()


if __name__ == '__main__':
    asyncio.run(main())