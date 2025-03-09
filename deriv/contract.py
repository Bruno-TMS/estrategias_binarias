import pprint

class ContractTrade:
    """Classe que cria negociações para associação, cacheando instâncias com __new__."""
    
    trades = []  # Cache global de todas as instâncias de negociações
    
    def __new__(cls, symbol, contract, min_time, max_time):
        """Cria uma nova instância ou retorna uma existente se duplicada."""
        if not all([symbol, contract]):
            raise ValueError('symbol e contract devem ser fornecidos.')
        
        # Normalizar min_time e max_time
        if min_time in [None, "", ("", "")]:
            min_time = None
        if max_time in [None, "", ("", "")]:
            max_time = None
        
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
            # Verifica duplicatas no cache
            key = (symbol.symbol_id, contract.contract_type, contract.contract_name, min_time, max_time)
            for trade in cls.trades:
                if (trade.symbol.symbol_id == symbol.symbol_id and 
                    trade.contract.contract_type == contract.contract_type and 
                    trade.contract.contract_name == contract.contract_name and 
                    trade._min_time == min_time and 
                    trade._max_time == max_time):
                    return trade
            new_instance = super().__new__(cls)
            new_instance._symbol = symbol
            new_instance._contract = contract
            new_instance._min_time = min_time
            new_instance._max_time = max_time
            return new_instance
    
    def __init__(self):
        """Inicializa a negociação após verificação em __new__."""
        if self not in ContractTrade.trades:
            ContractTrade.trades.append(self)
    
    @property
    def symbol(self):
        """Retorna o símbolo associado à negociação."""
        return self._symbol
    
    @property
    def contract(self):
        """Retorna o tipo de contrato associado à negociação."""
        return self._contract
    
    @property
    def min_time(self):
        """Retorna a duração mínima como tupla (duration, duration_type) ou (None, None) se nula."""
        if self._min_time is None:
            return (None, None)
        return (self._min_time.duration, self._min_time.duration_type)
    
    @property
    def max_time(self):
        """Retorna a duração máxima como tupla (duration, duration_type) ou (None, None) se nula."""
        if self._max_time is None:
            return (None, None)
        return (self._max_time.duration, self._max_time.duration_type)
    
    @classmethod
    def get_trades_by_symbol_id(cls, symbol_id):
        """Retorna todas as instâncias na lista trades com o mesmo symbol_id, ou False se não encontrada."""
        return [trade for trade in cls.trades if trade.symbol.symbol_id == symbol_id] or False
    
    @classmethod
    def get_trades_by_symbol_name(cls, symbol_name):
        """Retorna todas as instâncias na lista trades com o mesmo symbol_name, ou False se não encontrada."""
        return [trade for trade in cls.trades if trade.symbol.symbol_name == symbol_name] or False
    
    @classmethod
    def get_trades_by_contract_type(cls, contract_type):
        """Retorna todas as instâncias na lista trades com o mesmo contract_type, ou False se não encontrada."""
        return [trade for trade in cls.trades if trade.contract.contract_type == contract_type] or False
    
    @classmethod
    def get_trades_by_contract_name(cls, contract_name):
        """Retorna todas as instâncias na lista trades com o mesmo contract_name, ou False se não encontrada."""
        return [trade for trade in cls.trades if trade.contract.contract_name == contract_name] or False
    
    @classmethod
    def get_trades_by_min_time(cls, duration_value):
        """Retorna todas as instâncias na lista trades com min_time igual ao valor dado, ou False se não encontrada."""
        return [trade for trade in cls.trades if trade.min_time[0] == duration_value if trade.min_time[0] is not None] or False
    
    @classmethod
    def get_trades_by_max_time(cls, duration_value):
        """Retorna todas as instâncias na lista trades com max_time igual ao valor dado, ou False se não encontrada."""
        return [trade for trade in cls.trades if trade.max_time[0] == duration_value if trade.max_time[0] is not None] or False
    
    @classmethod
    def get_trades_with_min_below(cls, duration_value):
        """Retorna todas as instâncias na lista trades com min_time abaixo do valor dado, ou False se não encontrada."""
        return [trade for trade in cls.trades if trade.min_time[0] is not None and trade.min_time[0] < duration_value] or False
    
    @classmethod
    def get_trades_with_min_above(cls, duration_value):
        """Retorna todas as instâncias na lista trades com min_time acima do valor dado, ou False se não encontrada."""
        return [trade for trade in cls.trades if trade.min_time[0] is not None and trade.min_time[0] > duration_value] or False
    
    @classmethod
    def get_trades_with_max_below(cls, duration_value):
        """Retorna todas as instâncias na lista trades com max_time abaixo do valor dado, ou False se não encontrada."""
        return [trade for trade in cls.trades if trade.max_time[0] is not None and trade.max_time[0] < duration_value] or False
    
    @classmethod
    def get_trades_with_max_above(cls, duration_value):
        """Retorna todas as instâncias na lista trades com max_time acima do valor dado, ou False se não encontrada."""
        return [trade for trade in cls.trades if trade.max_time[0] is not None and trade.max_time[0] > duration_value] or False
    
    @classmethod
    def relatorio(cls):
        """Exibe um relatório organizado de todas as negociações em cache usando pprint."""
        trades_data = {
            f"Trade {i}": {
                "symbol_id": trade.symbol.symbol_id,
                "symbol_name": trade.symbol.symbol_name,
                "contract_type": trade.contract.contract_type,
                "contract_name": trade.contract.contract_name,
                "min_time": trade.min_time,
                "max_time": trade.max_time
            } for i, trade in enumerate(cls.trades)
        }
        pprint.pprint(trades_data)
    
    def __eq__(self, value):
        if not isinstance(value, ContractTrade):
            raise ValueError('Comparação inválida, deve ser com ContractTrade.')
        return (self.symbol == value.symbol and 
                self.contract == value.contract and 
                self.min_time == value.min_time and 
                self.max_time == value.max_time)

class ContractType:
    """Classe que cria contratos para associação, só permitindo instâncias baseadas em tipos pré-configurados em contracts."""
    
    contracts = []  # Lista global de instâncias de contratos (agora único ponto de cache)
    
    def __new__(cls, contract_type, contract_name):
        """Cria uma nova instância ou retorna uma existente se duplicada."""
        if not contract_type or not contract_name:
            raise ValueError('contract_type e contract_name não podem ser vazios.')
        
        try:
            if not isinstance(contract_type, str) or not isinstance(contract_name, str):
                raise ValueError(f'contract_type e contract_name devem ser strings, recebido: {contract_type}, {contract_name}')
            
            # Validação de unicidade (nome não pode existir em outro tipo)
            for contract in cls.contracts:
                if contract.contract_name == contract_name and contract.contract_type != contract_type:
                    raise ValueError(f'Contract name {contract_name} já existe em {contract.contract_type}.')
        
        except ValueError as e:
            raise ValueError(f'Valores inválidos para contract_type ou contract_name: {contract_type}, {contract_name}') from e
        
        else:
            # Verifica duplicatas no cache
            for contract in cls.contracts:
                if contract.contract_type == contract_type and contract.contract_name == contract_name:
                    return contract
            new_instance = super().__new__(cls)
            new_instance._contract_type = contract_type
            new_instance._contract_name = contract_name
            return new_instance
    
    def __init__(self):
        """Inicializa um contrato válido após verificação em __new__."""
        if self not in ContractType.contracts:
            ContractType.contracts.append(self)
    
    @classmethod
    def get_types(cls):
        """Retorna todos os contract_type da lista contracts."""
        return list({contract.contract_type for contract in cls.contracts})
    
    @classmethod
    def get_names(cls):
        """Retorna todos os contract_name da lista contracts."""
        return [contract.contract_name for contract in cls.contracts]
    
    @classmethod
    def get_type_by_name(cls, contract_name):
        """Retorna o contract_type associado a um contract_name único, ou False se não encontrado."""
        for contract in cls.contracts:
            if contract.contract_name == contract_name:
                return contract.contract_type
        return False
    
    @classmethod
    def get_contract_by_name(cls, contract_name):
        """Retorna a instância na lista contracts que tem o mesmo contract_name, ou False se não encontrada."""
        for contract in cls.contracts:
            if contract.contract_name == contract_name:
                return contract
        return False
    
    @classmethod
    def get_contracts_same_type_by_name(cls, contract_name):
        """Retorna todas as instâncias na lista contracts que têm o mesmo contract_type dado um contract_name, ou False se não encontrada."""
        contract_type = cls.get_type_by_name(contract_name)
        if not contract_type:
            return False
        return [contract for contract in cls.contracts if contract.contract_type == contract_type]
    
    @classmethod
    def get_contracts_by_type(cls, contract_type):
        """Retorna todas as instâncias na lista contracts que têm o mesmo contract_type, ou False se não encontrada."""
        contracts = [contract for contract in cls.contracts if contract.contract_type == contract_type]
        return contracts if contracts else False
    
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