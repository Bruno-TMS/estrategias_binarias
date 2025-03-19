import asyncio
import re
from pprint import pprint as pp
from util import check_str, check_duration
from connection import ConnManager, AppDashboard
from request import asset_index

def line(value):
    ln = f'\n{"-"*100}'
    print(ln)
    print(f'{value}:\n')

    pp(eval(value))

class TradeParameter:
    _instances = []
    _duration_units = ['t','s','m','h','d']
    _groups = set()
    _modalities = set()
    _instance = None

    def __new__(cls,*, group:str, modality:str, duration_min_digit: str = None, duration_min_unit: str = None, duration_max_digit: str = None, duration_max_unit: str = None):
        param_group = check_str(group)
        param_modality= check_str(modality)
        param_min_digit, param_min_unit = check_duration(duration_min_digit, duration_min_unit, TradeParameter._duration_units)
        param_max_digit, param_max_unit = check_duration(duration_max_digit, duration_max_unit, TradeParameter._duration_units)
        
        current_instance = cls.get_instance(
            group=param_group
            , modality = param_modality
            , duration_min_digit = param_min_digit
            , duration_min_unit = param_min_unit
            , duration_max_digit = param_max_digit
            , duration_max_unit = param_max_unit)
        
        if not current_instance:
            cls._instance = super().__new__(cls)
            cls._instance._group = param_group
            cls._instance._modality = param_modality
            cls._instance._duration_min_digit = param_min_digit
            cls._instance._duration_min_unit = param_min_unit
            cls._instance._duration_max_digit = param_max_digit
            cls._instance._duration_max_unit = param_max_unit
            
            cls._groups.add(param_group)
            cls._modalities.add(param_modality)
            cls._instances.append(cls._instance)
            
            return cls._instance

        return current_instance
    
    def get_key(self):
        if self.duration_min:
            idx = TradeParameter._duration_units.index(self.duration_min_unit) 
            return f'{self.group}{self.modality}{idx}{str(self.duration_min_digit).zfill(4)}'
        else:
            return f'{self.group}{self.modality}'

    @classmethod
    def get_groups(cls):
        return sorted(cls._groups)

    @classmethod
    def get_modalities(cls):
        return sorted(cls._modalities)

    @classmethod
    def get_instances(cls):
        return sorted(cls._instances, key = lambda x: x.get_key())

    @classmethod
    def get_instances_by_group(cls, group: str):
        pattern = re.compile(group, flags=re.I)
        return sorted([instance for instance in cls._instances if pattern.search(instance.group)], key= lambda x: x.get_key())

    @classmethod
    def get_instances_by_modality(cls, modality: str):
        pattern = re.compile(modality, flags=re.I)
        return sorted([instance for instance in cls._instances if pattern.search(instance.modality)], key= lambda x: x.get_key())

    @classmethod
    def get_instances_by_duration(cls, *, digit: int, unit: str, fit_in_units: bool = True):
        
        if unit not in cls._duration_units:
            raise ValueError(f'O valor de unit:{unit}, é inválido por não pertencer a lista:{cls._duration_units}')

        param_digit = digit
        param_index = cls._duration_units.index(unit)
        result = []

        for instance in cls._instances:
            if instance.duration_min and instance.duration_max:
                min_digit = instance.duration_min_digit
                max_digit = instance.duration_max_digit
                min_index = cls._duration_units.index(instance.duration_min_unit)
                max_index = cls._duration_units.index(instance.duration_max_unit)
                if fit_in_units:
                    if (min_index == param_index == max_index) and (min_digit <= param_digit <= max_digit):
                        result.append(instance)
                else:
                    if ((min_index < param_index < max_index) 
                        or (min_index == param_index and min_digit <= param_digit) 
                        or (max_index == param_index and param_digit <= max_digit)):
                        result.append(instance)

        return sorted(result, key = lambda x:  x.get_key())
    
    @classmethod
    def get_instance(cls,*, group:str, modality:str, duration_min_digit:int, duration_min_unit: str, duration_max_digit:int, duration_max_unit:str):
        instances = [inst for inst in cls._instances if (
            inst.group == group
            and inst.modality == modality
            and inst.duration_min_digit == duration_min_digit
            and inst.duration_min_unit == duration_min_unit
            and inst.duration_max_digit == duration_max_digit
            and inst.duration_max_unit == duration_max_unit)]
        
        if not instances:
            return None
        
        if len(instances) > 1:
            raise ValueError('Em cls._instances contém instâncias diferentes com propriedades iguais.')
        
        return instances[0]


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
            trade_parameters = asset[2]
            for trade_parameter in trade_parameters:
                group = trade_parameter[0]
                modality = trade_parameter[1]
                duration_min = trade_parameter[2]
                duration_max = trade_parameter[3]
                duration_min_digit = duration_min[:-1] if duration_min else None
                duration_min_unit = duration_min[-1] if duration_min else None
                duration_max_digit = duration_max[:-1] if duration_max else None
                duration_max_unit = duration_max[-1] if duration_max else None
                TradeParameter(
                    group=group,
                    modality=modality,
                    duration_min_digit=duration_min_digit,
                    duration_min_unit=duration_min_unit,
                    duration_max_digit=duration_max_digit,
                    duration_max_unit=duration_max_unit
                )
        return True        

    @property
    def group(self):
        return self._group

    @property
    def modality(self):
        return self._modality

    @property
    def duration_min_digit(self):
        return self._duration_min_digit

    @property
    def duration_min_unit(self):
        return self._duration_min_unit

    @property
    def duration_min(self):
        return f'{self._duration_min_digit}{self._duration_min_unit}' if self._duration_min_digit and self._duration_min_unit else ''

    @property
    def duration_max_digit(self):
        return self._duration_max_digit

    @property
    def duration_max_unit(self):
        return self._duration_max_unit

    @property
    def duration_max(self):
        return f'{self._duration_max_digit}{self._duration_max_unit}' if self._duration_max_digit and self._duration_max_unit else ''

    def __str__(self):
        return f"{self.group:<12}   {self.modality:<26}   min:{self.duration_min:>5}   max:{self.duration_max:>5}"
    
    def __repr__(self):
        return self.__str__()

def set_connection() -> ConnManager:
    app_name = AppDashboard.get_key_names().get('app')[0]
    token_name = AppDashboard.get_key_names().get('token')[0]
    if app_name and token_name:
        return ConnManager(app_name=app_name, token_name=token_name)
    else:
        raise ValueError(f'app_name:{app_name} ou token_name{token_name} inválido.')

def show_trade_parameters_methods():
    line('TradeParameter.get_groups()')
    line('TradeParameter.get_modalities()')
    line('TradeParameter.get_instances()')
    line('TradeParameter.get_instances_by_group("put")')
    line('TradeParameter.get_instances_by_modality("options")')
    line('TradeParameter.get_instances_by_duration(digit = 7, unit ="t")')
    line('TradeParameter.get_instances_by_duration(digit = 45, unit ="h", fit_in_units=False)')
    line('TradeParameter.get_instance(group="callput", modality="Higher/Lower", duration_min_digit=5, duration_min_unit="t", duration_max_digit=1, duration_max_unit="d")')
    print()


async def main():
    conn = set_connection()
    await conn.connect()
    await TradeParameter.populate(conn)
    show_trade_parameters_methods()
    await conn.disconnect()


if __name__ == '__main__':
    asyncio.run(main())