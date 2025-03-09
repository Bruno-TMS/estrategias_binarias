class ContractTrade:
    """Classe que cria negociações para associação, só permitindo instâncias baseadas em tipos pré-configurados em trades."""
    
    _trades_info = {}  # Cache global de tipos e nomes de negociações
    trades = []  # Lista global de instâncias de negociações
    
    def __init__(self, symbol, contract, min_time, max_time):
        """Inicializa uma negociação válida, verificando unicidade e validade."""
        # Verifica se symbol e contract são instâncias válidas
        if not isinstance(symbol, ContractSymbol):
            raise ValueError(f'Symbol {symbol} deve ser uma instância de ContractSymbol.')
        if not isinstance(contract, ContractType):
            raise ValueError(f'Contract {contract} deve ser uma instância de ContractType.')
        if not isinstance(min_time, DurationContract) or not isinstance(max_time, DurationContract):
            raise ValueError(f'min_time e max_time devem ser instâncias de ContractDuration.')
        
        # Verifica se a combinação symbol/contract já existe
        symbol_id = symbol.symbol_id
        contract_type = contract.contract_type
        contract_name = contract.contract_name
        key = (symbol_id, contract_type, contract_name)
        if key in ContractTrade._trades_info:
            raise ValueError(f'Combinação {symbol_id}/{contract_type}:{contract_name} já existe.')
        
        # Armazena os valores
        self._symbol = symbol
        self._contract = contract
        self._min_time = min_time
        self._max_time = max_time
        ContractTrade._trades_info[key] = (min_time, max_time)
        ContractTrade.trades.append(self)
    
    @classmethod
    def add_trade(cls, symbol, contract, min_time, max_time):
        """Adiciona uma combinação válida de símbolo/contrato ao cache global, verificando unicidade."""
        if not isinstance(symbol, ContractSymbol):
            raise ValueError(f'Symbol {symbol} deve ser uma instância de ContractSymbol.')
        if not isinstance(contract, ContractType):
            raise ValueError(f'Contract {contract} deve ser uma instância de ContractType.')
        if not isinstance(min_time, DurationContract) or not isinstance(max_time, DurationContract):
            raise ValueError(f'min_time e max_time devem ser instâncias de ContractDuration.')
        
        symbol_id = symbol.symbol_id
        contract_type = contract.contract_type
        contract_name = contract.contract_name
        key = (symbol_id, contract_type, contract_name)
        if key in cls._trades_info:
            raise ValueError(f'Combinação {symbol_id}/{contract_type}:{contract_name} já existe.')
        
        cls._trades_info[key] = (min_time, max_time)
    
    @classmethod
    def get_trades_by_symbol(cls, symbol):
        """Retorna todas as instâncias na lista trades que têm o mesmo symbol, ou False se não encontrada."""
        if not isinstance(symbol, ContractSymbol):
            return False
        return [trade for trade in cls.trades if trade.symbol == symbol] or False
    
    @property
    def symbol(self):
        return self._symbol
    
    @property
    def contract(self):
        return self._contract
    
    @property
    def min_time(self):
        return self._min_time
    
    @property
    def max_time(self):
        return self._max_time
    
    def __str__(self):
        return f'{self._symbol.symbol_id}/{self._contract.contract_type}:{self._contract.contract_name} ({self._min_time}-{self._max_time})'


class ContractSymbol:
    """Classe que cria símbolos para associação, só permitindo instâncias baseadas em tipos pré-configurados em symbols."""
    
    _symbols_info = {}  # Cache global de tipos e nomes de símbolos
    symbols = []  # Lista global de instâncias de símbolos
    
    def __init__(self, symbol_id, symbol_name):
        """Inicializa um símbolo válido. Verificando a unicidade de symbol_name e lançando erro caso já exista."""
        # Verifica se symbol_name já existe em outro symbol_id
        for existing_id, name in ContractSymbol._symbols_info.items():
            if symbol_name == name and existing_id != symbol_id:
                raise ValueError(f'Symbol name {symbol_name} já existe em {existing_id}.')
        if symbol_id not in ContractSymbol._symbols_info or symbol_name != ContractSymbol._symbols_info.get(symbol_id):
            raise ValueError(f'Símbolo {symbol_id}/{symbol_name} inválido.')
        self._symbol_id = symbol_id
        self._symbol_name = symbol_name
        ContractSymbol.symbols.append(self)
    
    @classmethod
    def add_symbols(cls, symbol_id, symbol_name):
        """Adiciona símbolos válidos ao cache global, verificando unicidade de symbol_name."""
        # Verifica unicidade de symbol_name entre todos os symbol_id
        for existing_id, name in cls._symbols_info.items():
            if symbol_name == name and existing_id != symbol_id:
                raise ValueError(f'Symbol name {symbol_name} já existe em {existing_id}.')
        cls._symbols_info[symbol_id] = symbol_name
    
    @classmethod
    def get_ids(cls):
        """Retorna todos os symbol_id da lista _symbols_info."""
        return list(cls._symbols_info.keys())
    
    @classmethod
    def get_names(cls):
        """Retorna todos os symbol_name da lista _symbols_info."""
        return list(cls._symbols_info.values())
    
    @classmethod
    def get_symbol_by_name(cls, symbol_name):
        """Retorna a instância na lista symbols que tem o mesmo symbol_name, ou False se não encontrada."""
        for symbol in cls.symbols:
            if symbol.symbol_name == symbol_name:
                return symbol
        return False
    
    @classmethod
    def get_symbol_by_id(cls, symbol_id):
        """Retorna a instância na lista symbols que tem o mesmo symbol_id, ou False se não encontrada."""
        for symbol in cls.symbols:
            if symbol.symbol_id == symbol_id:
                return symbol
        return False
    
    @property
    def symbol_id(self):
        return self._symbol_id
    
    @property
    def symbol_name(self):
        return self._symbol_name
        
    def __str__(self):
        return f'{self._symbol_id}:{self.symbol_name}'
    
class DurationContract:
    """Classe que representa e valida uma duração de contrato."""
    duration_sufix = {'ticks': 't', 'seconds': 's', 'minutes': 'm', 'hours': 'h', 'days': 'd'}
    instances = []  # Cache global de todas as instâncias criadas (agora público)
    
    def __new__(cls, duration):
        """Cria uma nova instância ou retorna uma existente se duplicada.
        
        Retorna uma instância existente se já criada com os mesmos duração e tipo.
        """
        if not duration:
            raise ValueError('Duração vazia.')
        
        try:
            if not isinstance(duration, str):
                raise ValueError(f'Duração deve ser string, recebido: {duration}')
            
            if len(duration) < 2:
                raise ValueError(f'Duração deve ter pelo menos 2 caracteres (ex.: "1t"), recebido: {duration}')
            
            if duration[-1] not in list(cls.duration_sufix.values()):
                raise ValueError(f'Formato inválido: {duration}. Deve ser "número" seguido de um dos sufixos (t, s, m, h, d) (ex.: "15m").')
            
            value = int(duration[:-1])
            if value <= 0:
                raise ValueError(f'Duração deve ser positiva, recebido: {duration}')
        
        except ValueError as e:
            raise ValueError(f'Formato inválido: {duration}. Deve ser "número" seguido de um dos sufixos (t, s, m, h, d) (ex.: "15m").') from e
        
        else:
            # Define atributos temporariamente para comparação
            new_instance = object.__new__(cls)
            new_instance._duration = value
            new_instance._duration_type = duration[-1]
            # Verifica duplicatas
            for instance in cls.instances:
                if new_instance == instance:
                    return instance
            return new_instance
    
    def __init__(self, duration):
        """Inicializa a duração após verificação em __new__."""
        # Os atributos já foram definidos em __new__, então só adiciona ao cache
        if self not in DurationContract.instances:
            DurationContract.instances.append(self)
    
    def __eq__(self, value):
        if not DurationContract.is_equals_types(self.duration_type, value.duration_type):
            raise ValueError('Tipos de duração diferentes.')
        return self.duration == value.duration
    
    def __lt__(self, value):
        if not DurationContract.is_equals_types(self.duration_type, value.duration_type):
            raise ValueError('Tipos de duração diferentes.')
        return self.duration < value.duration
    
    def __le__(self, value):
        if not DurationContract.is_equals_types(self.duration_type, value.duration_type):
            raise ValueError('Tipos de duração diferentes.')
        return self.duration <= value.duration
    
    def __gt__(self, value):
        if not DurationContract.is_equals_types(self.duration_type, value.duration_type):
            raise ValueError('Tipos de duração diferentes.')
        return self.duration > value.duration
    
    def __ge__(self, value):
        if not DurationContract.is_equals_types(self.duration_type, value.duration_type):
            raise ValueError('Tipos de duração diferentes.')
        return self.duration >= value.duration
    
    def __str__(self):
        return f'{self._duration}{self._duration_type}'
    
    @property
    def duration_type(self):
        """Retorna o tipo da duração."""
        return self._duration_type
    
    @property
    def duration(self):
        """Retorna o valor numérico da duração."""
        return self._duration
    
    @staticmethod
    def is_equals_types(*args):
        if any(not isinstance(arg, DurationContract) for arg in args):
            raise ValueError('Argumentos inválidos.')
        return all(arg.duration_type == args[0].duration_type for arg in args)
    
    @staticmethod
    def get_min_duration(*args):
        if not DurationContract.is_equals_types(*args):
            raise ValueError('Tipos de duração diferentes.')
        return min(arg.duration for arg in args)
    
    @staticmethod
    def get_max_duration(*args):
        if not DurationContract.is_equals_types(*args):
            raise ValueError('Tipos de duração diferentes.')
        return max(arg.duration for arg in args)
    
    def get_all_mins(self, *args, equals=True):
        """Retorna uma lista de instâncias de args com duração menor ou igual ao menor valor, com mesmo tipo."""
        if not args or not DurationContract.is_equals_types(self, *args):
            raise ValueError('Tipos de duração diferentes ou argumentos vazios.')
        min_duration = DurationContract.get_min_duration(*args)
        if equals:
            return [arg for arg in args if arg.duration <= min_duration]
        return [arg for arg in args if arg.duration < min_duration]

    def get_all_maxs(self, *args, equals=True):
        """Retorna uma lista de instâncias de args com duração maior ou igual ao maior valor, com mesmo tipo."""
        if not args or not DurationContract.is_equals_types(self, *args):
            raise ValueError('Tipos de duração diferentes ou argumentos vazios.')
        max_duration = DurationContract.get_max_duration(*args)
        if equals:
            return [arg for arg in args if arg.duration >= max_duration]
        return [arg for arg in args if arg.duration > max_duration]