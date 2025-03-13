import asyncio
from pprint import pprint as pp
from connection import ConnManager, AppDashboard
from request import Request

class Symbol:
    _symbols = []
    _instance = None
    
    def __new__(cls, *, symbol_id, symbol_name):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        
        if not symbol_id or not symbol_name:
            raise ValueError('symbol_id e symbol_name devem ser fornecidos.')
        
        try:
            if not isinstance(symbol_id, str) or not isinstance(symbol_name, str):
                raise ValueError(f'symbol_id e symbol_name devem ser strings, recebido: {symbol_id}, {symbol_name}')
            
            symbol_tuple = (symbol_id, symbol_name)
            if symbol_tuple not in cls._symbols:
                cls._symbols.append(symbol_tuple)
        
        except ValueError as e:
            raise ValueError(f'Valores inválidos: symbol_id={symbol_id}, symbol_name={symbol_name}') from e
        
        return cls._instance
    
    def __init__(self, *, symbol_id, symbol_name):
        pass
    
    @classmethod
    def get_items(cls):
        """Returns a list of all concatenated symbols, sorted by symbol_name."""
        def get_key(item):
            _, symbol_name = item
            return symbol_name
        return [f"{symbol_id}:{symbol_name}" for symbol_id, symbol_name in sorted(cls._symbols, key=get_key)]
    
    @classmethod
    def get_name_by_id(cls, symbol_id):
        """Returns a list of concatenated symbols for the specified symbol_id, sorted by symbol_name."""
        if not isinstance(symbol_id, str):
            raise ValueError(f'symbol_id deve ser string, recebido: {symbol_id}')
        
        def get_key(item):
            _, symbol_name = item
            return symbol_name
        filtered_items = [(sid, sname) for sid, sname in cls._symbols if sid == symbol_id]
        return [f"{sname}" for _,sname in sorted(filtered_items, key=get_key)]
    
    @classmethod
    def get_id_by_name(cls, symbol_name):
        """Returns a list of concatenated symbols for the specified symbol_name, sorted by symbol_id."""
        if not isinstance(symbol_name, str):
            raise ValueError(f'symbol_name deve ser string, recebido: {symbol_name}')
        
        def get_key(item):
            symbol_id, _ = item
            return symbol_id
        filtered_items = [(sid, sname) for sid, sname in cls._symbols if sname == symbol_name]
        return [f"{sid}" for sid,_ in sorted(filtered_items, key=get_key)]
    
    @classmethod
    def get_ids(cls):
        """Returns a list of all symbol_ids, sorted alphabetically."""
        return sorted([symbol_id for symbol_id, _ in cls._symbols])
    
    @classmethod
    def get_names(cls):
        """Returns a list of all symbol_names, sorted alphabetically."""
        return sorted([symbol_name for _, symbol_name in cls._symbols])

class Modality:
    _modalities = []
    _instance = None
    
    def __new__(cls, *, modality_group, modality_name):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        
        if not modality_group or not modality_name:
            raise ValueError('modality_group e modality_name devem ser fornecidos.')
        
        try:
            if not isinstance(modality_group, str) or not isinstance(modality_name, str):
                raise ValueError(f'modality_group e modality_name devem ser strings, recebido: {modality_group}, {modality_name}')
            
            modality_tuple = (modality_group, modality_name)
            if modality_tuple not in cls._modalities:
                cls._modalities.append(modality_tuple)
        
        except ValueError as e:
            raise ValueError(f'Valores inválidos: modality_group={modality_group}, modality_name={modality_name}') from e
        
        return cls._instance
    
    def __init__(self, *, modality_group, modality_name):
        pass
    
    @classmethod
    def get_items(cls):
        """Returns a list of all concatenated modalities, sorted by modality_name."""
        def get_key(item):
            _, modality_name = item
            return modality_name
        return [f"{modality_group}:{modality_name}" for modality_group, modality_name in sorted(cls._modalities, key=get_key)]
    
    @classmethod
    def get_names_by_group(cls, modality_group):
        """Returns a list of concatenated modalities for the specified modality_group, sorted by modality_name."""
        if not isinstance(modality_group, str):
            raise ValueError(f'modality_group deve ser string, recebido: {modality_group}')
        
        def get_key(item):
            _, modality_name = item
            return modality_name
        filtered_items = [(mg, mn) for mg, mn in cls._modalities if mg == modality_group]
        return [f"{mn}" for _, mn in sorted(filtered_items, key=get_key)]
    
    @classmethod
    def get_group_by_name(cls, modality_name):
        """Returns a list of concatenated modalities for the specified modality_name, sorted by modality_group."""
        if not isinstance(modality_name, str):
            raise ValueError(f'modality_name deve ser string, recebido: {modality_name}')
        
        def get_key(item):
            modality_group, _ = item
            return modality_group
        filtered_items = [(mg, mn) for mg, mn in cls._modalities if mn == modality_name]
        return [f"{mg}" for mg, _ in sorted(filtered_items, key=get_key)]
    
    @classmethod
    def get_groups(cls):
        """Returns a list of all modality_groups, sorted alphabetically."""
        return sorted([modality_group for modality_group, _ in cls._modalities])
    
    @classmethod
    def get_names(cls):
        """Returns a list of all modality_names, sorted alphabetically."""
        return sorted([modality_name for _, modality_name in cls._modalities])

class Duration:
    _duration_suffixes = {'ticks': ('t', 'o'), 'seconds': ('s', 'p'), 'minutes': ('m', 'q'), 'hours': ('h', 'r'), 'days': ('d', 's')}
    _durations = []
    _instance = None
    
    def __new__(cls, *, duration, duration_unit):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        
        if not (duration and duration_unit):
            raise ValueError('Duração e unidade devem ser fornecidas.')
        
        try:
            if not (isinstance(duration, str) and isinstance(duration_unit, str)):
                raise ValueError(f'Duração e unidade devem ser strings, recebido: {duration}, {duration_unit}')
            
            suffixes = [sfx[0] for sfx in cls._duration_suffixes.values()]
            if duration_unit not in suffixes:
                raise ValueError(f'Unidade inválida: {duration_unit}. Deve ser um dos sufixos {suffixes}.')
            
            value = int(duration)
            if value <= 0:
                raise ValueError(f'Duração deve ser positiva, recebido: {duration}')
            
            duration_tuple = (duration, duration_unit)
            if duration_tuple not in cls._durations:
                cls._durations.append(duration_tuple)
        
        except ValueError as e:
            raise ValueError(f'Formato inválido: duration={duration}, duration_unit={duration_unit}.') from e
        
        return cls._instance
    
    def __init__(self, *, duration, duration_unit):
        pass
    
    @classmethod
    def get_items(cls):
        """Returns a list of concatenated durations, sorted by _duration_suffixes weight."""
        def get_key(item):
            duration, unit = item
            peso = cls._duration_suffixes[[k for k, v in cls._duration_suffixes.items() if v[0] == unit][0]][1]
            return (peso, int(duration))
        return [f"{duration}{unit}" for duration, unit in sorted(cls._durations, key=get_key)]
    
    @classmethod
    def get_by_unit(cls, unit):
        """Returns a list of concatenated durations for the specified duration_unit, sorted by value."""
        suffixes = [sfx[0] for sfx in cls._duration_suffixes.values()]
        if unit not in suffixes:
            raise ValueError(f'Unidade inválida: {unit}. Deve ser um dos sufixos {suffixes}.')
        
        def get_key(item):
            duration, _ = item
            return int(duration)
        filtered_items = [(duration, u) for duration, u in cls._durations if u == unit]
        return [f"{duration}{u}" for duration, u in sorted(filtered_items, key=get_key)]

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
    
    if response and testes_classes_individuais:
        print('*'*100)
        print('Class Symbol:')
        print()
        for asset in assets:
            asset_id = asset[0]
            asset_name = asset[1]
            Symbol(symbol_id=asset_id, symbol_name=asset_name)
        
        print('Symbol.get_items():')
        pp(Symbol.get_items())
        print()
        print('Symbol.get_name_by_id("frxEURUSD"):')
        pp(Symbol.get_name_by_id('frxEURUSD'))
        print()
        print('Symbol.get_id_by_name("EUR/USD"):')
        pp(Symbol.get_id_by_name('EUR/USD'))
        print()
        print('Symbol.get_ids():')
        pp(Symbol.get_ids())
        print()
        print('Symbol.get_names():')
        pp(Symbol.get_names())
        print('*'*100)
        
        print('*'*100)
        print('Class Modality:')
        print()
        for asset in assets:
            asset_id = asset[0]
            asset_name = asset[1]
            modalities = asset[2]
            
            for modality in modalities:
                modality_group = modality[0]
                modality_name = modality[1]
                Modality(modality_group=modality_group, modality_name=modality_name)
                
        print('Modality.get_items():')
        pp(Modality.get_items())
        print()
        print('Modality.get_names_by_group("callput"):')
        pp(Modality.get_names_by_group('callput'))
        print()
        print('Modality.get_group_by_name("Rise/Fall"):')
        pp(Modality.get_group_by_name('Rise/Fall'))
        print()
        print('Modality.get_groups():')
        pp(Modality.get_groups())
        print()
        print('Modality.get_names():')
        pp(Modality.get_names())
        print('*'*100)
        
        print('*'*100)
        print('Class Duration:')
        print()
        for asset in assets:
            asset_id = asset[0]
            asset_name = asset[1]
            modalities = asset[2]
            
            for modality in modalities:
                modality_group = modality[0]
                modality_name = modality[1]
                modality_min_duration = modality[2]
                modality_max_duration = modality[3]
                
                if modality_min_duration:
                    Duration(duration=modality_min_duration[:-1], duration_unit=modality_min_duration[-1])
                
                if modality_max_duration:
                    Duration(duration=modality_max_duration[:-1], duration_unit=modality_max_duration[-1])
        
        print('Duration.get_items():')
        pp(Duration.get_items())
        print()
        print('Duration.get_by_unit("t"):')
        pp(Duration.get_by_unit('t'))
        print('*'*100)

if __name__ == "__main__":
    asyncio.run(main())