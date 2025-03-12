import asyncio
from connection import ConnManager
from request import Request

class DurationContract:
    _duration_sufix = {'ticks': ('t', 'o'), 'seconds': ('s', 'p'), 'minutes': ('m', 'q'), 'hours': ('h', 'r'), 'days': ('d', 's')}
    instances = []
    
    def __new__(cls, duration):
        if not duration:
            raise ValueError('Duração vazia.')
        
        try:
            if not isinstance(duration, str):
                raise ValueError(f'Duração deve ser string, recebido: {duration}')
            
            if len(duration) < 2:
                raise ValueError(f'Duração deve ter pelo menos 2 caracteres (ex.: "1t"), recebido: {duration}')
            
            if duration[-1] not in [sfx[0] for sfx in cls._duration_sufix.values()]:
                raise ValueError(f'Formato inválido: {duration}. Deve ser "número" seguido de um dos sufixos (t, s, m, h, d) (ex.: "15m").')
            
            value = int(duration[:-1])
            if value <= 0:
                raise ValueError(f'Duração deve ser positiva, recebido: {duration}')
        
        except ValueError as e:
            raise ValueError(f'Formato inválido: {duration}. Deve ser "número" seguido de um dos sufixos (t, s, m, h, d) (ex.: "15m").') from e
        
        else:
            new_instance = object.__new__(cls)
            new_instance._duration = value
            new_instance._duration_type = duration[-1]
            for instance in cls.instances:
                if (instance._duration == value and instance._duration_type == duration[-1]):
                    return instance
            return new_instance
    
    def __init__(self, duration):
        for instance in DurationContract.instances:
            if (instance._duration == self._duration and instance._duration_type == self._duration_type):
                return
        DurationContract.instances.append(self)
    
    def __eq__(self, value):
        if not DurationContract.is_equals_types(self.duration_type, value.duration_type):
            raise ValueError('Tipos de duração diferentes para __eq__.')
        return self.duration == value.duration
    
    def __lt__(self, value):
        if not DurationContract.is_equals_types(self.duration_type, value.duration_type):
            raise ValueError('Tipos de duração diferentes para __lt__.')
        return self.duration < value.duration
    
    def __le__(self, value):
        if not DurationContract.is_equals_types(self.duration_type, value.duration_type):
            raise ValueError('Tipos de duração diferentes para __le__.')
        return self.duration <= value.duration
    
    def __gt__(self, value):
        if not DurationContract.is_equals_types(self.duration_type, value.duration_type):
            raise ValueError('Tipos de duração diferentes para __gt__.')
        return self.duration > value.duration
    
    def __ge__(self, value):
        if not DurationContract.is_equals_types(self.duration_type, value.duration_type):
            raise ValueError('Tipos de duração diferentes para __ge__.')
        return self.duration >= value.duration
    
    def __str__(self):
        return f'{self._duration}{self._duration_type}'
    
    @property
    def duration_type(self):
        return self._duration_type
    
    @property
    def duration(self):
        return self._duration
    
    @staticmethod
    def is_equals_types(*args):
        if any(not isinstance(arg, DurationContract) for arg in args):
            raise ValueError('Argumentos inválidos para is_equals_types.')
        return all(arg.duration_type == args[0].duration_type for arg in args)
    
    @staticmethod
    def get_min_duration(*args):
        if not DurationContract.is_equals_types(*args):
            raise ValueError('Tipos de duração diferentes para get_min_duration.')
        return min(arg.duration for arg in args)
    
    @staticmethod
    def get_max_duration(*args):
        if not DurationContract.is_equals_types(*args):
            raise ValueError('Tipos de duração diferentes para get_max_duration.')
        return max(arg.duration for arg in args)
    
    @staticmethod
    def get_all_instances():
        def get_key(duration, duration_type):
            tempos_pesos = {k: v for k, v in DurationContract._duration_sufix.values()}
            peso = tempos_pesos.get(duration_type)
            return f"{peso}{duration:04d}"
        return sorted(DurationContract.instances, key=lambda x: get_key(x.duration, x.duration_type))
    
    def get_all_mins(self, *args, equals=True):
        if not args or not DurationContract.is_equals_types(self, *args):
            raise ValueError('Tipos de duração diferentes ou argumentos vazios para get_all_mins.')
        min_duration = DurationContract.get_min_duration(*args)
        if equals:
            return [arg for arg in args if arg.duration <= min_duration]
        return [arg for arg in args if arg.duration < min_duration]

    def get_all_maxs(self, *args, equals=True):
        if not args or not DurationContract.is_equals_types(self, *args):
            raise ValueError('Tipos de duração diferentes ou argumentos vazios para get_all_maxs.')
        max_duration = DurationContract.get_max_duration(*args)
        if equals:
            return [arg for arg in args if arg.duration >= max_duration]
        return [arg for arg in args if arg.duration > max_duration]

class ContractSymbol:
    symbols = []
    
    def __new__(cls, symbol_id, symbol_name):
        if not symbol_id or not symbol_name:
            raise ValueError('symbol_id e symbol_name não podem ser vazios.')
        
        try:
            if not isinstance(symbol_id, (str, int)) or not isinstance(symbol_name, str):
                raise ValueError(f'symbol_id deve ser str ou int, symbol_name deve ser str, recebido: {symbol_id}, {symbol_name}')
            
            if any(not isinstance(s._symbol_id, (str, int)) or not isinstance(s._symbol_name, str) for s in cls.symbols):
                raise ValueError('Símbolos existentes inválidos.')
        
        except ValueError as e:
            raise ValueError(f'Valores inválidos para symbol_id ou symbol_name: {symbol_id}, {symbol_name}') from e
        
        else:
            for symbol in cls.symbols:
                if symbol.symbol_id == symbol_id or symbol.symbol_name == symbol_name:
                    return symbol
            new_instance = super().__new__(cls)
            new_instance._symbol_id = symbol_id
            new_instance._symbol_name = symbol_name
            return new_instance
    
    def __init__(self, symbol_id, symbol_name):
        if self not in ContractSymbol.symbols:
            ContractSymbol.symbols.append(self)
    
    @classmethod
    def get_ids(cls):
        return [symbol.symbol_id for symbol in cls.symbols]
    
    @classmethod
    def get_names(cls):
        return [symbol.symbol_name for symbol in cls.symbols]
    
    @classmethod
    def get_symbol_by_name(cls, symbol_name):
        for symbol in cls.symbols:
            if symbol.symbol_name == symbol_name:
                return symbol
        return False
    
    @classmethod
    def get_symbol_by_id(cls, symbol_id):
        for symbol in cls.symbols:
            if symbol.symbol_id == symbol_id:
                return symbol
        return False
    
    @classmethod
    def get_all_instances(cls):
        return sorted(cls.symbols, key=lambda x: x.symbol_name)
    
    @property
    def symbol_id(self):
        return self._symbol_id
    
    @property
    def symbol_name(self):
        return self._symbol_name
        
    def __str__(self):
        return f'{self._symbol_id}:{self.symbol_name}'
    
    def __eq__(self, value):
        if not isinstance(value, ContractSymbol):
            raise ValueError('Comparação inválida, deve ser com ContractSymbol.')
        return self.symbol_id == value.symbol_id and self.symbol_name == value.symbol_name

class ContractType:
    contracts = []
    
    def __new__(cls, contract_type, contract_name):
        if not contract_type or not contract_name:
            raise ValueError('contract_type e contract_name não podem ser vazios.')
        
        try:
            if not isinstance(contract_type, str) or not isinstance(contract_name, str):
                raise ValueError(f'contract_type e contract_name devem ser strings, recebido: {contract_type}, {contract_name}')
            
            for contract in cls.contracts:
                if contract.contract_name == contract_name and contract.contract_type != contract_type:
                    raise ValueError(f'Contract name {contract_name} já existe em {contract.contract_type}.')
        
        except ValueError as e:
            raise ValueError(f'Valores inválidos para contract_type ou contract_name: {contract_type}, {contract_name}') from e
        
        else:
            for contract in cls.contracts:
                if contract.contract_type == contract_type and contract.contract_name == contract_name:
                    return contract
            new_instance = super().__new__(cls)
            new_instance._contract_type = contract_type
            new_instance._contract_name = contract_name
            return new_instance
    
    def __init__(self, contract_type, contract_name):
        if self not in ContractType.contracts:
            ContractType.contracts.append(self)
    
    @classmethod
    def get_types(cls):
        return list({contract.contract_type for contract in cls.contracts})
    
    @classmethod
    def get_names(cls):
        return [contract.contract_name for contract in cls.contracts]
    
    @classmethod
    def get_type_by_name(cls, contract_name):
        for contract in cls.contracts:
            if contract.contract_name == contract_name:
                return contract.contract_type
        return False
    
    @classmethod
    def get_contract_by_name(cls, contract_name):
        for contract in cls.contracts:
            if contract.contract_name == contract_name:
                return contract
        return False
    
    @classmethod
    def get_contracts_same_type_by_name(cls, contract_name):
        contract_type = cls.get_type_by_name(contract_name)
        if not contract_type:
            return False
        return [contract for contract in cls.contracts if contract.contract_type == contract_type]
    
    @classmethod
    def get_contracts_by_type(cls, contract_type):
        contracts = [contract for contract in cls.contracts if contract.contract_type == contract_type]
        return contracts if contracts else False
    
    @classmethod
    def get_all_instances(cls):
        return sorted(cls.contracts, key=lambda x: f"{x.contract_type}:{x.contract_name}")
    
    @property
    def contract_type(self):
        return self._contract_type
    
    @property
    def contract_name(self):
        return self._contract_name
        
    def __str__(self):
        return f'{self._contract_type}:{self.contract_name}'
    
    def __eq__(self, value):
        if not isinstance(value, ContractType):
            raise ValueError('Comparação inválida, deve ser com ContractType.')
        return self.contract_type == value.contract_type and self.contract_name == value.contract_name

class ContractTrade:
    trades = []
    
    def __new__(cls, symbol, contract, min_time, max_time):
        if not all([symbol, contract]):
            raise ValueError('symbol e contract devem ser fornecidos.')
        
        try:
            if not (isinstance(symbol, ContractSymbol) and isinstance(contract, ContractType)):
                raise ValueError('symbol deve ser ContractSymbol e contract deve ser ContractType.')
            if min_time is not None and not isinstance(min_time, DurationContract):
                raise ValueError('min_time deve ser DurationContract ou None.')
            if max_time is not None and not isinstance(max_time, DurationContract):
                raise ValueError('max_time deve ser DurationContract ou None.')
        
        except ValueError as e:
            raise ValueError(f'Valores inválidos para negociação: {symbol}, {contract}, {min_time}, {max_time}') from e
        
        else:
            for trade in cls.trades:
                if (trade.symbol == symbol and 
                    trade.contract == contract and 
                    trade._min_time is min_time and 
                    trade._max_time is max_time):
                    return trade
            new_instance = super().__new__(cls)
            new_instance._symbol = symbol
            new_instance._contract = contract
            new_instance._min_time = min_time
            new_instance._max_time = max_time
            return new_instance
    
    def __init__(self, symbol, contract, min_time, max_time):
        if self not in ContractTrade.trades:
            ContractTrade.trades.append(self)
    
    @property
    def symbol(self):
        return self._symbol
    
    @property
    def contract(self):
        return self._contract
    
    @property
    def min_time(self):
        if self._min_time is None:
            return (None, None)
        return (self._min_time.duration, self._min_time.duration_type)
    
    @property
    def max_time(self):
        if self._max_time is None:
            return (None, None)
        return (self._max_time.duration, self._max_time.duration_type)
    
    @classmethod
    def get_trades_by_symbol_id(cls, symbol_id):
        return [trade for trade in cls.trades if trade.symbol.symbol_id == symbol_id] or False
    
    @classmethod
    def get_trades_by_symbol_name(cls, symbol_name):
        return [trade for trade in cls.trades if trade.symbol.symbol_name == symbol_name] or False
    
    @classmethod
    def get_trades_by_contract_type(cls, contract_type):
        return [trade for trade in cls.trades if trade.contract.contract_type == contract_type] or False
    
    @classmethod
    def get_trades_by_contract_name(cls, contract_name):
        return [trade for trade in cls.trades if trade.contract.contract_name == contract_name] or False
    
    @classmethod
    def get_trades_by_min_time(cls, duration_value):
        return [trade for trade in cls.trades if trade.min_time[0] is not None and trade.min_time[0] == duration_value] or False
    
    @classmethod
    def get_trades_by_max_time(cls, duration_value):
        return [trade for trade in cls.trades if trade.max_time[0] is not None and trade.max_time[0] == duration_value] or False
    
    @classmethod
    def get_trades_with_min_below(cls, duration_value):
        return [trade for trade in cls.trades if trade.min_time[0] is not None and trade.min_time[0] < duration_value] or False
    
    @classmethod
    def get_trades_with_min_above(cls, duration_value):
        return [trade for trade in cls.trades if trade.min_time[0] is not None and trade.min_time[0] > duration_value] or False
    
    @classmethod
    def get_trades_with_max_below(cls, duration_value):
        return [trade for trade in cls.trades if trade.max_time[0] is not None and trade.max_time[0] < duration_value] or False
    
    @classmethod
    def get_trades_with_max_above(cls, duration_value):
        return [trade for trade in cls.trades if trade.max_time[0] is not None and trade.max_time[0] > duration_value] or False
    
    @classmethod
    def get_all_instances(cls):
        return sorted(cls.trades, key=lambda x: f"{x.symbol.symbol_name}:{x.contract.contract_type}")
    
    def __eq__(self, value):
        if not isinstance(value, ContractTrade):
            raise ValueError('Comparação inválida, deve ser com ContractTrade.')
        return (self.symbol == value.symbol and 
                self.contract == value.contract and 
                self._min_time == value._min_time and 
                self._max_time == value._max_time)

async def populate_contract_data(manager):
    req = Request()
    assets_response = await manager.send_request(req.asset_index)
    if not assets_response or 'asset_index' not in assets_response:
        print("Nenhum dado de ativo retornado pela API.")
        return
    
    assets = assets_response['asset_index']
    for asset in assets:
        symbol_id, symbol_name, contracts = asset
        symbol = ContractSymbol(symbol_id, symbol_name)
        for contract_data in contracts:
            contract_type, contract_name, min_time, max_time = contract_data
            contract = ContractType(contract_type, contract_name)
            min_time_obj = DurationContract(min_time) if min_time else None
            max_time_obj = DurationContract(max_time) if max_time else None
            ContractTrade(symbol, contract, min_time_obj, max_time_obj)

if __name__ == "__main__":
    async def test_contract():
        manager = ConnManager("app_demo", "token_demo")
        await manager.connect()
        await populate_contract_data(manager)
        print("Durações em cache:")
        for instance in DurationContract.get_all_instances():
            print(f"  {instance}")
        print("Símbolos em cache:")
        for symbol in ContractSymbol.get_all_instances():
            print(f"  {symbol}")
        print("Tipos de contrato em cache:")
        for contract in ContractType.get_all_instances():
            print(f"  {contract}")
        print("Negociações em cache:")
        for trade in ContractTrade.get_all_instances():
            print(f"  {trade.symbol} - {trade.contract} - Min: {trade.min_time[0]}{trade.min_time[1] or ''} - Max: {trade.max_time[0]}{trade.max_time[1] or ''}")
        await manager.disconnect()

    asyncio.run(test_contract())