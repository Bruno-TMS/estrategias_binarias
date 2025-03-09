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
    
    symbols = []  # Lista global de instâncias de símbolos (agora único ponto de cache)
    
    def __new__(cls, symbol_id, symbol_name):
        """Cria uma nova instância ou retorna uma existente se duplicada."""
        if not symbol_id or not symbol_name:
            raise ValueError('symbol_id e symbol_name não podem ser vazios.')
        
        try:
            if not isinstance(symbol_id, (str, int)) or not isinstance(symbol_name, str):
                raise ValueError(f'symbol_id deve ser str ou int, symbol_name deve ser str, recebido: {symbol_id}, {symbol_name}')
            
            # Validação simples (unicidade será verificada pelo cache)
            if any(not isinstance(s._symbol_id, (str, int)) or not isinstance(s._symbol_name, str) for s in cls.symbols):
                raise ValueError('Símbolos existentes inválidos.')
        
        except ValueError as e:
            raise ValueError(f'Valores inválidos para symbol_id ou symbol_name: {symbol_id}, {symbol_name}') from e
        
        else:
            # Verifica duplicatas no cache
            for symbol in cls.symbols:
                if symbol.symbol_id == symbol_id or symbol.symbol_name == symbol_name:
                    return symbol
            new_instance = super().__new__(cls)
            new_instance._symbol_id = symbol_id
            new_instance._symbol_name = symbol_name
            return new_instance
    
    def __init__(self):
        """Inicializa um símbolo válido após verificação em __new__."""
        # Adiciona ao cache se não for duplicata (já verificado em __new__)
        if self not in ContractSymbol.symbols:
            ContractSymbol.symbols.append(self)
    
    @classmethod
    def get_ids(cls):
        """Retorna todos os symbol_id da lista symbols."""
        return [symbol.symbol_id for symbol in cls.symbols]
    
    @classmethod
    def get_names(cls):
        """Retorna todos os symbol_name da lista symbols."""
        return [symbol.symbol_name for symbol in cls.symbols]
    
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
    
    def __eq__(self, value):
        if not isinstance(value, ContractSymbol):
            raise ValueError('Comparação inválida, deve ser com ContractSymbol.')
        return self.symbol_id == value.symbol_id and self.symbol_name == value.symbol_name
    
    
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
    
    def __init__(self):
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