import asyncio
from pprint import pprint as pp
from connection import ConnManager, AppDashboard
from request import Request
import re

class Asset:
    _instances = []
    _duration_suffixes = ['t', 's', 'm', 'h', 'd']

    def __init__(self, *, symbol_id: str, symbol_name: str, modality_group: str, modality_name: str, duration_min: str = None, duration_min_unit: str = None, duration_max: str = None, duration_max_unit: str = None):
        if not (symbol_id and symbol_name and modality_group and modality_name and isinstance(symbol_id, str) and isinstance(symbol_name, str) and isinstance(modality_group, str) and isinstance(modality_name, str)):
            raise ValueError('symbol_id, symbol_name, modality_group e modality_name devem ser strings não vazias.')

        if (duration_min and not duration_min_unit) or (not duration_min and duration_min_unit):
            raise ValueError('duration_min e duration_min_unit devem ser fornecidos juntos ou ambos omitidos.')

        if (duration_max and not duration_max_unit) or (not duration_max and duration_max_unit):
            raise ValueError('duration_max e duration_max_unit devem ser fornecidos juntos ou ambos omitidos.')

        if (duration_min) and (not isinstance(duration_min, str) or not isinstance(duration_min_unit, str)):
            raise ValueError('duration_min e duration_min_unit devem ser do tipo string.')

        if (duration_max) and (not isinstance(duration_max, str) or not isinstance(duration_max_unit, str)):
            raise ValueError('duration_max e duration_max_unit devem ser do tipo string.')

        if (duration_min) and (duration_min_unit not in self._duration_suffixes):
            raise ValueError(f'duration_min_unit {duration_min_unit} não está entre {self._duration_suffixes}')

        if (duration_max) and (duration_max_unit not in self._duration_suffixes):
            raise ValueError(f'duration_max_unit {duration_max_unit} não está entre {self._duration_suffixes}')

        try:
            if duration_min and int(duration_min) <= 0:
                raise ValueError(f'duration_min deve ser positivo, recebido: {duration_min}')
            
            if duration_max and int(duration_max) <= 0:
                raise ValueError(f'duration_max deve ser positivo, recebido: {duration_max}')
            
            self._symbol_id = symbol_id
            self._symbol_name = symbol_name
            self._modality_group = modality_group
            self._modality_name = modality_name
            self._duration_min = duration_min
            self._duration_min_unit = duration_min_unit  # Corrigido
            self._duration_max = duration_max  # Corrigido
            self._duration_max_unit = duration_max_unit

        except ValueError as e:
            raise ValueError(f'Erro ao criar Asset: {str(e)}') from e

        else:
            Asset._instances.append(self)

    @property
    def symbol_id(self):
        return self._symbol_id

    @property
    def symbol_name(self):
        return self._symbol_name

    @property
    def modality_group(self):
        return self._modality_group

    @property
    def modality_name(self):
        return self._modality_name

    @property
    def duration_min(self):
        return self._duration_min

    @property
    def duration_min_unit(self):
        return self._duration_min_unit

    @property
    def duration_max(self):
        return self._duration_max

    @property
    def duration_max_unit(self):
        return self._duration_max_unit

    @classmethod
    def get_items(cls):
        """Returns a list of all Asset instances."""
        return [instance for instance in cls._instances]
    
    @classmethod
    def get_items_by_symbol_id(cls, symbol_id: str):
        """Returns a list of Asset instances matching the exact symbol_id."""
        return [instance for instance in cls._instances if instance.symbol_id == symbol_id]
    
    @classmethod
    def get_items_by_symbol_name(cls, symbol_name: str):
        """Returns a list of Asset instances where symbol_name matches the pattern (case-sensitive)."""
        pattern = re.compile(symbol_name)
        return [instance for instance in cls._instances if pattern.search(instance.symbol_name)]

    @classmethod
    def get_items_by_modality_group(cls, modality_group: str):
        """Returns a list of Asset instances where modality_group matches the pattern (case-insensitive)."""
        pattern = re.compile(modality_group, flags=re.I)
        return [instance for instance in cls._instances if pattern.search(instance.modality_group)]

    @classmethod
    def get_items_by_modality_name(cls, modality_name: str):
        """Returns a list of Asset instances where modality_name matches the pattern (case-insensitive)."""
        pattern = re.compile(modality_name, flags=re.I)
        return [instance for instance in cls._instances if pattern.search(instance.modality_name)]

    @classmethod
    def get_items_by_duration(cls, *, duration: str, duration_unit: str, fit_in_units: bool = True):
        """Returns a list of Asset instances where the duration fits within min and max, optionally matching the unit."""
        if duration_unit not in cls._duration_suffixes:
            raise ValueError(f'Valor de duration_unit:{duration_unit} não pertence a lista:{cls._duration_suffixes}.')
        
        try:
            param_duration = int(duration)
            param_index = cls._duration_suffixes.index(duration_unit)
            result = []
            
            for instance in cls._instances:
                if instance.duration_min and instance.duration_max:  # Só compara se ambos existem
                    min_duration = int(instance.duration_min)
                    max_duration = int(instance.duration_max)
                    min_index = cls._duration_suffixes.index(instance.duration_min_unit)
                    max_index = cls._duration_suffixes.index(instance.duration_max_unit)
                    
                    if fit_in_units:
                        # Só considera itens com a mesma unidade e dentro do intervalo
                        if min_index == param_index == max_index and min_duration <= param_duration <= max_duration:
                            result.append(instance)
                    else:
                        # Considera intervalo entre unidades diferentes, ajustando a ordem
                        if (min_index < param_index < max_index) or \
                           (min_index == param_index and min_duration <= param_duration) or \
                           (max_index == param_index and param_duration <= max_duration):
                            result.append(instance)
            
            return result
            
        except ValueError as e:
            raise ValueError(f'Valor de duration:{duration} inválido.') from e

    @staticmethod 
    def populate(response):
        """Populates Asset instances from the response data."""
        if response:
            assets = response['asset_index']
            for asset in assets:
                asset_id = asset[0]
                asset_name = asset[1]
                modalities = asset[2]
                for modality in modalities:
                    modality_group = modality[0]
                    modality_name = modality[1]
                    duration_min = modality[2]
                    duration_max = modality[3]
                    duration_min_value = duration_min[:-1] if duration_min else None
                    duration_min_unit = duration_min[-1] if duration_min else None
                    duration_max_value = duration_max[:-1] if duration_max else None
                    duration_max_unit = duration_max[-1] if duration_max else None
                    Asset(
                        symbol_id=asset_id,
                        symbol_name=asset_name,
                        modality_group=modality_group,
                        modality_name=modality_name,
                        duration_min=duration_min_value,
                        duration_min_unit=duration_min_unit,
                        duration_max=duration_max_value,
                        duration_max_unit=duration_max_unit
                    )

    def __str__(self):
        sy_id = self.symbol_id
        sy_nm = self.symbol_name
        mod_gp = self.modality_group
        mod_nm = self.modality_name 
        drt_min = self.duration_min if self.duration_min else ''
        drt_min_unt = self.duration_min_unit if self.duration_min_unit else ''
        drt_max = self.duration_max if self.duration_max else ''
        drt_max_unt = self.duration_max_unit if self.duration_max_unit else ''
        return f'{sy_id}:{sy_nm}   {mod_gp}:{mod_nm}   min:{drt_min}{drt_min_unt}  max:{drt_max}{drt_max_unt}'

    def __repr__(self):
        return self.__str__()

async def main():
    line = f'\n{100*"-"}\n'

    print('Iniciando conexão com o servidor DERIV:')
    dsb = AppDashboard.get_key_names()
    app_name = dsb.get('app')[0]
    token = dsb.get('token')[0]
    conn = ConnManager(app_name, token)
    req = Request()
    await conn.connect()

    print(line)
    print(f'Mensagem ao servidor: {req.asset_index}')
    response = await conn.send_request(req.asset_index)
    await conn.disconnect()  # Corrigido com await

    print('Resposta do servidor:')
    pp(response)

    Asset.populate(response)

    print(line)
    method_return = Asset.get_items()
    print('Printing all @classmethod from class Asset:')
    print()
    print(f'@classmethod Asset.get_items(): total {len(method_return)}')
    print()
    pp(method_return[:5])
    print('...')
    pp(method_return[-5:])

    print(line)
    sys_id = 'frxAUDJPY'
    method_return = Asset.get_items_by_symbol_id(sys_id)
    print(f'@classmethod Asset.get_items_by_symbol_id({sys_id}): total {len(method_return)}')
    print()
    pp(method_return)

    print(line)
    sys_name = 'AUD'
    method_return = Asset.get_items_by_symbol_name(sys_name)
    print(f'@classmethod Asset.get_items_by_symbol_name({sys_name}): total {len(method_return)}')
    print()
    pp(method_return[:5])
    print('...')

    print(line)
    modality_group = 'equal'
    method_return = Asset.get_items_by_modality_group(modality_group)
    print(f'@classmethod Asset.get_items_by_modality_group({modality_group}): total {len(method_return)}')
    print()
    pp(method_return[:5])
    print('...')

    print(line)
    modality_name = 'higher'
    method_return = Asset.get_items_by_modality_name(modality_name)
    print(f'@classmethod Asset.get_items_by_modality_name({modality_name}): total {len(method_return)}')
    print()
    pp(method_return[:5])
    print('...')

    print(line)
    duration = '7'
    duration_unit = 't'
    method_return = Asset.get_items_by_duration(duration=duration, duration_unit=duration_unit, fit_in_units=True)
    print(f'@classmethod Asset.get_items_by_duration(duration={duration}, duration_unit={duration_unit}, fit_in_units=True): total {len(method_return)}')
    print()
    pp(method_return)

if __name__ == "__main__":
    asyncio.run(main())