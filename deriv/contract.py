# contract.py
import asyncio
from deriv_api import DerivAPI
from deriv import connection


class Contract:
    """Classe que cria contratos para associação, só permitindo instâncias baseadas em tipos pré-configurados em contracts."""
    
    _contracts_info = {}  # Cache global de tipos e nomes de contratos
    contracts = []  # Lista global de instâncias de contratos
    
    def __init__(self, contract_type, contract_name):
        """Inicializa um contrato válido."""
        if contract_type not in Contract._contracts_info.keys() or contract_name not in Contract._contracts_info.get(contract_type, set()):
            raise ValueError(f'Contrato {contract_type}/{contract_name} inválido.')
        self._contract_type = contract_type
        self._contract_name = contract_name
        Contract.contracts.append(self)
    
    @classmethod
    def add_contracts(cls, contract_type, contract_name):
        """Adiciona contratos válidos ao cache global, verificando unicidade de contract_name."""
        for existing_type, names in cls._contracts_info.items():
            if contract_name in names and existing_type != contract_type:
                raise ValueError(f'Contract name {contract_name} já existe em {existing_type}.')
        cls._contracts_info.setdefault(contract_type, set()).add(contract_name)
    
    @classmethod
    def get_types(cls):
        """Retorna todos os contract_type da lista _contracts_info."""
        return list(cls._contracts_info.keys())
    
    @classmethod
    def get_names(cls):
        """Retorna todos os contract_name da lista _contracts_info."""
        return [name for names in cls._contracts_info.values() for name in names]
    
    @classmethod
    def get_type_by_name(cls, contract_name):
        """Retorna o contract_type associado a um contract_name único, ou False se não encontrado."""
        for contract_type, names in cls._contracts_info.items():
            if contract_name in names:
                return contract_type
        return False
    
    @classmethod
    def get_names_by_type(cls, contract_type):
        """Retorna a lista de contract_names associados a um contract_type, ou False se não encontrado."""
        return cls._contracts_info.get(contract_type, False)
    
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
        if contract_type not in cls._contracts_info:
            return False
        return [contract for contract in cls.contracts if contract.contract_type == contract_type]
    
    @property
    def contract_type(self):
        return self._contract_type
   
    @property
    def contract_name(self):
        return self._contract_name
        
    def __str__(self):
        return f'{self._contract_type}:{self.contract_name}'
    
    

class ContractTypes:
    symmbols = {}
    
    def __init__(self):
        self.symbols# ex: "R_10"
        self.name # ex: "Volatility 10 Index"
        self.min_time #

        
    

class Contracts:
    # Variável de classe para armazenar mercados, submercados e seus status
    available_markets = {}

    def __init__(self, conn):
        self.conn = conn  # Composição com connection

    async def fetch_instruments(self, market=None, submarket=None):
        """Busca todos os instrumentos de negociação disponíveis, com filtro opcional por mercado ou submercado.

        Atualiza available_markets com status open/close para mercados e submercados.

        Args:
            market (str, optional): Filtra por mercado (ex.: 'forex', 'synthetic_index').
            submarket (str, optional): Filtra por submercado (ex.: 'minor_pairs', 'forex_basket').

        Returns:
            list: Lista de símbolos dos instrumentos.
        """
        if not self.conn._is_alive:
            raise ValueError("Conexão não está ativa.")
        try:
            response = await self.conn._api.active_symbols({"active_symbols": "full"})
            instruments = response.get("active_symbols", [])

            # Inicializa available_markets
            self.available_markets = {}

            # Preenche available_markets com mercados, submercados e status
            for symbol in instruments:
                market_name = symbol.get("market")
                submarket_name = symbol.get("submarket")
                is_open = symbol.get("open", 0) == 1  # 1 para open, 0 para close

                if market_name and submarket_name:
                    # Inicializa o mercado, se não existir
                    if market_name not in self.available_markets:
                        self.available_markets[market_name] = {
                            "status": "close",
                            "submarkets": {}
                        }

                    # Inicializa o submercado, se não existir
                    if submarket_name not in self.available_markets[market_name]["submarkets"]:
                        self.available_markets[market_name]["submarkets"][submarket_name] = {
                            "status": "close"
                        }

                    # Atualiza o status do submercado para open se o instrumento estiver aberto
                    if is_open:
                        self.available_markets[market_name]["submarkets"][submarket_name]["status"] = "open"
                        self.available_markets[market_name]["status"] = "open"

            # Filtra por mercado e/ou submercado, se especificado
            filtered_instruments = []
            for symbol in instruments:
                if market and symbol.get("market") != market:
                    continue
                if submarket and symbol.get("submarket") != submarket:
                    continue
                filtered_instruments.append(symbol["symbol"])
            print(f"Instrumentos disponíveis (mercado={market}, submercado={submarket}): {filtered_instruments}")
            return filtered_instruments
        except Exception as e:
            print(f"Erro ao buscar instrumentos: {e}")
            raise

    async def get_contract_details(self, instrument):
        """Obtém os detalhes dos contratos para um instrumento específico."""
        if not self.conn._is_alive:
            raise ValueError("Conexão não está ativa.")
        try:
            response = await self.conn._api.contracts_for({"contracts_for": instrument})
            contracts = response.get("contracts_for", {}).get("available", [])
            if not contracts:
                raise ValueError(f"Nenhum contrato disponível para o instrumento {instrument}")
            print(f"Detalhes dos contratos para {instrument}: {contracts}")
            return contracts  # Retorna a lista de contratos disponíveis
        except KeyError as e:
            print(f"Erro de chave ao obter contratos para {instrument}: {e}")
            raise
        except Exception as e:
            print(f"Erro ao obter detalhes dos contratos para {instrument}: {e}")
            raise

    async def get_asset_index(self):
        """Obtém o índice de ativos disponíveis na API Deriv.

        Returns:
            dict: Resposta da API com informações sobre os ativos.
        """
        if not self.conn._is_alive:
            raise ValueError("Conexão não está ativa.")
        try:
            response = await self.conn._api.asset_index({"asset_index": 1})
            print(f"Índice de ativos: {response}")
            return response
        except Exception as e:
            print(f"Erro ao obter índice de ativos: {e}")
            raise

    def format_contract_details(self, contracts):
        """Formata os detalhes dos contratos para uma saída mais legível.

        Args:
            contracts (list): Lista de contratos retornada por contracts_for["available"].

        Returns:
            dict: Dicionário organizado com os contratos.
        """
        if not isinstance(contracts, list):
            print(f"Erro: Contratos devem ser uma lista, recebido: {type(contracts)}")
            return {}
        formatted = {}
        for contract in contracts:
            contract_type = contract.get("contract_type", "unknown")
            formatted[contract_type] = {
                "display": contract.get("contract_display", "N/A"),
                "stake": contract.get("default_stake", 0),
                "duration": f"{contract.get('min_contract_duration', 'N/A')} a {contract.get('max_contract_duration', 'N/A')}",
                "sentiment": contract.get("sentiment", "N/A"),
                "barriers": contract.get("barriers", "N/A")
            }
        return formatted

if __name__ == "__main__":
    async def test_contracts():
        # Instancia a conexão
        conn = connection
        await conn.connect()
        try:
            contracts = Contracts(conn)
            # Testa o índice de ativos
            assets = await contracts.get_asset_index()
            # Testa com filtro por mercado e submercado
            instruments = await contracts.fetch_instruments(market="forex", submarket="minor_pairs")
            print(f"Mercados disponíveis e seus submercados com status: {Contracts.available_markets}")
            if instruments:
                for instrument in instruments[:3]:  # Testa os primeiros 3 instrumentos
                    try:
                        details = await contracts.get_contract_details(instrument)
                        formatted_details = contracts.format_contract_details(details)
                        print(f"Contratos formatados para {instrument}: {formatted_details}")
                    except ValueError as e:
                        print(f"Instrumento {instrument} indisponível: {e}")
        except Exception as e:
            print(f"Erro no teste: {e}")
        finally:
            await conn.disconnect()

    asyncio.run(test_contracts())