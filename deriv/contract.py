import asyncio
from pprint import pprint as pp
from connection import ConnManager, AppDashboard
from request import Request

class Asset:
    _instances = []
    _duration_suffixes = {'ticks': 't', 'seconds': 's', 'minutes': 'm', 'hours': 'h', 'days': 'd'}

    def __init__(self, *, symbol_id, symbol_name, modality_group, modality_name, duration_min=None, duration_min_unit=None, duration_max=None, duration_max_unit=None):
        if not (symbol_id and symbol_name and modality_group and modality_name and isinstance(symbol_id, str) and isinstance(symbol_name, str) and isinstance(modality_group, str) and isinstance(modality_name, str)):
            raise ValueError('symbol_id, symbol_name, modality_group e modality_name devem ser strings não vazias.')
        
        if (duration_min and not duration_min_unit) or (not duration_min and duration_min_unit):
            raise ValueError('duration_min e duration_min_unit devem ser fornecidos juntos ou ambos omitidos.')
        
        if (duration_max and not duration_max_unit) or (not duration_max and duration_max_unit):
            raise ValueError('duration_max e duration_max_unit devem ser fornecidos juntos ou ambos omitidos.')
        
        try:
            self._symbol_id = symbol_id
            self._symbol_name = symbol_name
            self._modality_group = modality_group
            self._modality_name = modality_name
            
            if duration_min and duration_min_unit:
                if not isinstance(duration_min, str) or not isinstance(duration_min_unit, str):
                    raise ValueError('duration_min e duration_min_unit devem ser strings.')
                if duration_min_unit not in self._duration_suffixes.values():
                    raise ValueError(f'duration_min_unit inválido: {duration_min_unit}. Deve ser um dos sufixos {list(self._duration_suffixes.values())}.')
                value = int(duration_min)
                if value <= 0:
                    raise ValueError(f'duration_min deve ser positivo, recebido: {duration_min}')
                self._duration_min = duration_min
                self._duration_min_unit = duration_min_unit
            else:
                self._duration_min = None
                self._duration_min_unit = None
            
            if duration_max and duration_max_unit:
                if not isinstance(duration_max, str) or not isinstance(duration_max_unit, str):
                    raise ValueError('duration_max e duration_max_unit devem ser strings.')
                if duration_max_unit not in self._duration_suffixes.values():
                    raise ValueError(f'duration_max_unit inválido: {duration_max_unit}. Deve ser um dos sufixos {list(self._duration_suffixes.values())}.')
                value = int(duration_max)
                if value <= 0:
                    raise ValueError(f'duration_max deve ser positivo, recebido: {duration_max}')
                self._duration_max = duration_max
                self._duration_max_unit = duration_max_unit
            else:
                self._duration_max = None
                self._duration_max_unit = None
    
        except ValueError as e:
            raise ValueError(f'Erro ao criar Asset: {str(e)}') from e
        
        Asset._instances.append(self)
    
    def __str__(self):
        sy_id = self.symbol_id
        sy_nm = self.symbol_name
        mod_gp = self.modality_group
        mod_nm = self.modality_name 
        drt_min = self.duration_min if self.duration_min else ''
        drt_min_unt = self.duration_min_unit if self.duration_min_unit else ''
        drt_max = self.duration_max if self.duration_max else ''
        drt_max_unt = self.duration_max_unit if self.duration_max_unit else ''
        return f'{sy_id}:{sy_nm}  {mod_gp}:{mod_nm}  min:{drt_min}{drt_min_unt} max:{drt_max}{drt_max_unt}'
    
    def __repr__(self):
        return self.__str__()  # Faz pprint usar o mesmo formato de __str__
    
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
        return [asset for asset in cls._instances]  # Já usa __repr__
    
    @classmethod
    def get_item_by_symbol_id(cls, symbol_id):
        """Returns a list of formatted strings for all Asset instances with the specified symbol_id."""
        if not isinstance(symbol_id, str):
            raise ValueError(f'symbol_id deve ser string, recebido: {symbol_id}')
        return [str(asset) for asset in cls._instances if asset.symbol_id == symbol_id]
    
    @classmethod
    def get_symbols_ids(cls):
        """Returns a list of unique symbol_ids, sorted alphabetically."""
        return sorted({x.symbol_id for x in cls._instances})
    
    @classmethod
    def get_symbols_names(cls):
        """Returns a list of unique symbol_names, sorted alphabetically."""
        return sorted({x.symbol_name for x in cls._instances})
    
    @classmethod
    def get_symbols_ids_names(cls):
        """Returns a list of unique 'symbol_id:symbol_name' strings, sorted alphabetically."""
        return sorted({f'{x.symbol_id}:{x.symbol_name}' for x in cls._instances})
    
    @classmethod
    def get_by_symbol_id(cls, symbol_id):
        """Returns a list of Asset instances for the specified symbol_id."""
        if not isinstance(symbol_id, str):
            raise ValueError(f'symbol_id deve ser string, recebido: {symbol_id}')
        return [asset for asset in cls._instances if asset.symbol_id == symbol_id]
    
    @classmethod
    def get_by_symbol_name(cls, symbol_name):
        """Returns a list of Asset instances for the specified symbol_name."""
        if not isinstance(symbol_name, str):
            raise ValueError(f'symbol_name deve ser string, recebido: {symbol_name}')
        return [asset for asset in cls._instances if asset.symbol_name == symbol_name]
    
    @classmethod
    def get_by_modality_group(cls, modality_group):
        """Returns a list of Asset instances for the specified modality_group."""
        if not isinstance(modality_group, str):
            raise ValueError(f'modality_group deve ser string, recebido: {modality_group}')
        return [asset for asset in cls._instances if asset.modality_group == modality_group]
    
    @classmethod
    def get_by_modality_name(cls, modality_name):
        """Returns a list of Asset instances for the specified modality_name."""
        if not isinstance(modality_name, str):
            raise ValueError(f'modality_name deve ser string, recebido: {modality_name}')
        return [asset for asset in cls._instances if asset.modality_name == modality_name]
    
    @classmethod
    def get_groups(cls):
        """Returns a list of all modality_groups, sorted alphabetically."""
        return sorted({asset.modality_group for asset in cls._instances})
    
    @classmethod
    def get_modality_names(cls):
        """Returns a list of all modality_names, sorted alphabetically."""
        return sorted({asset.modality_name for asset in cls._instances})

async def main(testes_classes_individuais=True):
    print('Iniciando conexão com o servidor DERIV:')
    
    dsb = AppDashboard.get_key_names()
    app_name = dsb.get('app')[0]
    token = dsb.get('token')[0]
    conn = ConnManager(app_name, token)
    req = Request()
    
    await conn.connect()
    print()
    print(f'Mensagem ao servidor: {req.asset_index}')
    response = await conn.send_request(req.asset_index)
    print('Resposta do servidor:')
    pp(response)
    assets = response['asset_index']
    
    if response:
        # Popula Asset com os dados do asset_index
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
                
        print('Asset.get_items() (first 5):')
        pp(Asset.get_items()[:5])  # Usa __repr__ automaticamente com pprint
        print('*'*80)
        
        print('Asset.get_item_by_symbol_id("frxAUDCHF"):')
        pp(Asset.get_item_by_symbol_id('frxAUDCHF'))  # Retorna lista de strings
        print('*'*80)
        
        print('Asset.get_symbols_ids():')
        pp(Asset.get_symbols_ids())
        print('*'*80)
        
        print('Asset.get_symbols_names():')
        pp(Asset.get_symbols_names())
        print('*'*80)
        
        print('Asset.get_symbols_ids_names():')
        pp(Asset.get_symbols_ids_names())
        print('*'*80)
        
        # Testes adicionais para outros métodos
        print('Asset.get_by_symbol_id("frxEURUSD") (first 5):')
        pp(Asset.get_by_symbol_id('frxEURUSD')[:5])
        print('*'*80)
        
        print('Asset.get_by_symbol_name("EUR/USD") (first 5):')
        pp(Asset.get_by_symbol_name('EUR/USD')[:5])
        print('*'*80)
        
        print('Asset.get_by_modality_group("callput") (first 5):')
        pp(Asset.get_by_modality_group('callput')[:5])
        print('*'*80)
        
        print('Asset.get_by_modality_name("Rise/Fall") (first 5):')
        pp(Asset.get_by_modality_name('Rise/Fall')[:5])
        print('*'*80)
        
        print('Asset.get_groups():')
        pp(Asset.get_groups())
        print('*'*80)
        
        print('Asset.get_modality_names():')
        pp(Asset.get_modality_names())
        print('*'*80)

if __name__ == "__main__":
    asyncio.run(main())