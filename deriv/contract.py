import pprint
import asyncio
from deriv.connection import connect, disconnect  # Importamos as funções de conexão
from deriv_api import DerivAPI  # Para compatibilidade com a chamada asset_index
from datetime import datetime

# Classes (mantidas intactas)
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
    
    def __init__(self, symbol_id, symbol_name):
        """Inicializa um símbolo válido após verificação em __new__."""
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
    
    def __init__(self, contract_type, contract_name):
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

class DurationContract:
    """Classe que representa e valida uma duração de contrato."""
    duration_sufix = {'ticks': 't', 'seconds': 's', 'minutes': 'm', 'hours': 'h', 'days': 'd'}
    instances = []  # Cache global de todas as instâncias criadas (agora público)
    
    def __new__(cls, duration):
        """Cria uma nova instância ou retorna uma existente se duplicada."""
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
            new_instance = object.__new__(cls)
            new_instance._duration = value
            new_instance._duration_type = duration[-1]
            # Compara diretamente os atributos para evitar erro em __eq__
            for instance in cls.instances:
                if (instance._duration == value and instance._duration_type == duration[-1]):
                    return instance
            return new_instance
    
    def __init__(self, duration):
        """Inicializa a duração após verificação em __new__."""
        # Compara diretamente os atributos para evitar erro em __eq__
        for instance in DurationContract.instances:
            if (instance._duration == self._duration and instance._duration_type == self._duration_type):
                return
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

class ContractTrade:
    """Classe que cria negociações para associação, cacheando instâncias com __new__."""
    
    trades = []  # Cache global de todas as instâncias de negociações
    
    def __new__(cls, symbol, contract, min_time, max_time):
        """Cria uma nova instância ou retorna uma existente se duplicada."""
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
    
    def __init__(self, symbol, contract, min_time, max_time):
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
        """Exibe um relatório organizado de todas as negociações em cache usando pprint, ordenado por symbol_id."""
        trades_data = {
            f"Trade {i}": {
                "symbol_id": trade.symbol.symbol_id,
                "symbol_name": trade.symbol.symbol_name,
                "contract_type": trade.contract.contract_type,
                "contract_name": trade.contract.contract_name,
                "min_time": trade.min_time,
                "max_time": trade.max_time
            } for i, trade in enumerate(sorted(cls.trades, key=lambda x: x.symbol.symbol_id))
        }
        pprint.pprint(trades_data)
    
    def __eq__(self, value):
        if not isinstance(value, ContractTrade):
            raise ValueError('Comparação inválida, deve ser com ContractTrade.')
        return (self.symbol == value.symbol and 
                self.contract == value.contract and 
                self.min_time == value.min_time and 
                self.max_time == value.max_time)

# Função para popular as negociações com dados reais da API
async def populate_contract_trade(connection):
    """Popula as instâncias de ContractTrade usando os dados obtidos via API."""
    assets_response = await connection.asset_index({"asset_index": 1})
    if not assets_response or 'asset_index' not in assets_response:
        raise ValueError("Nenhum dado de ativo retornado pela API.")
    
    assets = assets_response['asset_index']
    
    for asset in assets:
        symbol_id, symbol_name, contracts = asset
        symbol = ContractSymbol(symbol_id, symbol_name)
        
        for contract_data in contracts:
            contract_type, contract_name, min_time, max_time = contract_data
            contract = ContractType(contract_type, contract_name)
            
            # Cria DurationContract para min_time e max_time, tratando valores vazios
            min_time_obj = DurationContract(min_time) if min_time else None
            max_time_obj = DurationContract(max_time) if max_time else None
            
            # Cria a instância de ContractTrade
            trade = ContractTrade(symbol, contract, min_time_obj, max_time_obj)

if __name__ == "__main__":
    async def test_real_connection():
        """Testa a conexão real, busca os ativos e gera o relatório ordenado por symbol_id."""
        from deriv import connection as conn_module  # Importa o módulo connection para acessar _api e _is_alive

        start_time = datetime.now().strftime("%y/%m/%d %H:%M")
        print(f"Iniciando teste de conexão real {start_time}")
        status = "Sucesso"
        try:
            # Instancia um objeto Connection que usa a conexão de connection.py
            class ConnectionAdapter:
                def __init__(self):
                    self._api = None
                
                async def connect(self):
                    await connect()  # Usa a função connect de connection.py
                    self._api = conn_module._api  # Acessa a instância de DerivAPI
                    if self._api is None or not conn_module._is_alive:
                        raise ValueError("Falha ao estabelecer a conexão com a API Deriv.")
                
                async def disconnect(self):
                    await disconnect()  # Usa a função disconnect de connection.py
                    self._api = None
                
                async def asset_index(self, request):
                    if self._api is None or not conn_module._is_alive:
                        raise ValueError("Conexão não ativa. Chame connect() primeiro.")
                    return await self._api.asset_index(request)

            # Instancia o adaptador
            connection = ConnectionAdapter()
            await connection.connect()

            # Popula as negociações com dados reais
            await populate_contract_trade(connection)

            # Exibe o relatório ordenado por symbol_id
            ContractTrade.relatorio()

            # Desconecta após o teste
            await connection.disconnect()
            print(f"Estado da conexão após desconexão: {conn_module._is_alive}")
        
        except Exception as e:
            print(f"Erro durante o teste: {e}")
            status = "Falha"
        finally:
            end_time = datetime.now().strftime("%y/%m/%d %H:%M")
            print(f"Finalizando teste de conexão real - Status: {status} {end_time}")

    asyncio.run(test_real_connection())