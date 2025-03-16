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
            raise ValueError('symbol_id, symbol_name, modality_group, and modality_name must be non-empty strings.')

        if (duration_min and not duration_min_unit) or (not duration_min and duration_min_unit):
            raise ValueError('duration_min and duration_min_unit must be provided together or both omitted.')

        if (duration_max and not duration_max_unit) or (not duration_max and duration_max_unit):
            raise ValueError('duration_max and duration_max_unit must be provided together or both omitted.')

        if (duration_min) and (not isinstance(duration_min, str) or not isinstance(duration_min_unit, str)):
            raise ValueError('duration_min and duration_min_unit must be strings.')

        if (duration_max) and (not isinstance(duration_max, str) or not isinstance(duration_max_unit, str)):
            raise ValueError('duration_max and duration_max_unit must be strings.')

        if (duration_min) and (duration_min_unit not in self._duration_suffixes):
            raise ValueError(f'duration_min_unit {duration_min_unit} is not in {self._duration_suffixes}')

        if (duration_max) and (duration_max_unit not in self._duration_suffixes):
            raise ValueError(f'duration_max_unit {duration_max_unit} is not in {self._duration_suffixes}')

        try:
            if duration_min and int(duration_min) <= 0:
                raise ValueError(f'duration_min must be positive, received: {duration_min}')
            
            if duration_max and int(duration_max) <= 0:
                raise ValueError(f'duration_max must be positive, received: {duration_max}')

            self._symbol_id = symbol_id
            self._symbol_name = symbol_name
            self._modality_group = modality_group
            self._modality_name = modality_name
            self._duration_min = duration_min
            self._duration_min_unit = duration_min_unit
            self._duration_max = duration_max
            self._duration_max_unit = duration_max_unit

        except ValueError as e:
            raise ValueError(f'Error creating Asset: {str(e)}') from e

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
        """Returns a list of Asset instances where symbol_name matches the pattern."""
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
        """Returns a list of Asset instances where the duration fits within min and max."""
        if duration_unit not in cls._duration_suffixes:
            raise ValueError(f'duration_unit value {duration_unit} is not in {self._duration_suffixes}.')
        
        try:
            param_duration = int(duration)
            param_index = cls._duration_suffixes.index(duration_unit)
            result = []
            
            for instance in cls._instances:
                if instance.duration_min and instance.duration_max:
                    min_duration = int(instance.duration_min)
                    max_duration = int(instance.duration_max)
                    min_index = cls._duration_suffixes.index(instance.duration_min_unit)
                    max_index = cls._duration_suffixes.index(instance.duration_max_unit)

                    if fit_in_units:
                        if min_index == param_index == max_index and min_duration <= param_duration <= max_duration:
                            result.append(instance)
                    else:
                        if ((min_index < param_index < max_index) 
                            or (min_index == param_index and min_duration <= param_duration) 
                            or (max_index == param_index and param_duration <= max_duration)):
                            result.append(instance)

            return result

        except ValueError as e:
            raise ValueError(f'Invalid duration value: {duration}') from e

    @staticmethod 
    def populate(response):
        """Populates Asset instances from the asset_index response, clearing previous data.
        Returns True if populated successfully, False otherwise."""
        Asset._instances.clear()  # Limpa os dados antigos
        if not response:
            return False
        assets = response.get('asset_index', False)
        if not assets:
            return False
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
        return True

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

class ActiveSymbol:
    _instances = []

    def __init__(self, *, symbol: str, display_name: str, exchange_is_open: int, is_trading_suspended: int, market: str, market_display_name: str, submarket_display_name: str):
        if not (symbol and display_name and market and market_display_name and submarket_display_name and isinstance(symbol, str) and isinstance(display_name, str) and isinstance(market, str) and isinstance(market_display_name, str) and isinstance(submarket_display_name, str)):
            raise ValueError('symbol, display_name, market, market_display_name, and submarket_display_name must be non-empty strings.')

        self._symbol = symbol
        self._display_name = display_name
        self._exchange_is_open = exchange_is_open
        self._is_trading_suspended = is_trading_suspended
        self._market = market
        self._market_display_name = market_display_name
        self._submarket_display_name = submarket_display_name
        
        ActiveSymbol._instances.append(self)

    @property
    def symbol(self):
        return self._symbol

    @property
    def display_name(self):
        return self._display_name

    @property
    def exchange_is_open(self):
        return self._exchange_is_open

    @property
    def is_trading_suspended(self):
        return self._is_trading_suspended

    @property
    def market(self):
        return self._market

    @property
    def market_display_name(self):
        return self._market_display_name

    @property
    def submarket_display_name(self):
        return self._submarket_display_name

    @classmethod
    def get_items(cls):
        """Returns a list of all ActiveSymbol instances."""
        return [instance for instance in cls._instances]

    @classmethod
    def get_items_by_symbol(cls, symbol: str):
        """Returns a list of ActiveSymbol instances matching the exact symbol."""
        return [instance for instance in cls._instances if instance.symbol == symbol]

    @classmethod
    def get_items_by_market(cls, market: str):
        """Returns a list of ActiveSymbol instances matching the market (case-insensitive)."""
        pattern = re.compile(market, flags=re.I)
        return [instance for instance in cls._instances if pattern.search(instance.market)]

    @classmethod
    def get_items_by_market_display_name(cls, market_display_name: str):
        """Returns a list of ActiveSymbol instances matching the market_display_name (case-insensitive)."""
        pattern = re.compile(market_display_name, flags=re.I)
        return [instance for instance in cls._instances if pattern.search(instance.market_display_name)]

    @classmethod
    def get_items_by_submarket_display_name(cls, submarket_display_name: str):
        """Returns a list of ActiveSymbol instances matching the submarket_display_name (case-insensitive)."""
        pattern = re.compile(submarket_display_name, flags=re.I)
        return [instance for instance in cls._instances if pattern.search(instance.submarket_display_name)]

    @classmethod
    def get_items_by_display_name(cls, display_name: str):
        """Returns a list of ActiveSymbol instances matching the display_name (case-insensitive)."""
        pattern = re.compile(display_name, flags=re.I)
        return [instance for instance in cls._instances if pattern.search(instance.display_name)]

    @classmethod
    def get_items_tradeable(cls):
        """Returns a list of ActiveSymbol instances that are tradeable (open and not suspended)."""
        return [instance for instance in cls._instances if instance.exchange_is_open == 1 and instance.is_trading_suspended == 0]

    @staticmethod
    def populate(response):
        """Populates ActiveSymbol instances from the active_symbols response, clearing previous data.
        Returns True if populated successfully, False otherwise."""
        ActiveSymbol._instances.clear()  # Limpa os dados antigos
        if not response:
            return False
        symbols = response.get('active_symbols', False)
        if not symbols:
            return False
        for symbol_data in symbols:
            ActiveSymbol(
                symbol=symbol_data['symbol'],
                display_name=symbol_data['display_name'],
                exchange_is_open=symbol_data['exchange_is_open'],
                is_trading_suspended=symbol_data['is_trading_suspended'],
                market=symbol_data['market'],
                market_display_name=symbol_data['market_display_name'],
                submarket_display_name=symbol_data['submarket_display_name']
            )
        return True

    def __str__(self):
        return f'{self.symbol}:{self.display_name}   Open:{self.exchange_is_open}   Suspended:{self.is_trading_suspended}   Market:{self.market_display_name} ({self.submarket_display_name})'

    def __repr__(self):
        return self.__str__()

class SymbolManager:
    _instance = None
    _assets = []
    _active_symbols = []

    def __new__(cls):
        """Implements Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._assets = Asset.get_items()  # Inicializa com dados existentes
            cls._active_symbols = ActiveSymbol.get_items()  # Inicializa com dados existentes
        return cls._instance

    @classmethod
    def populate_assets(cls, asset_response):
        """Populates Asset instances with the latest server data."""
        Asset.populate(asset_response)
        cls._assets = Asset.get_items()  # Atualiza referência com os novos dados

    @classmethod
    def populate_active_symbols(cls, active_response):
        """Populates ActiveSymbol instances with the latest server data."""
        ActiveSymbol.populate(active_response)
        cls._active_symbols = ActiveSymbol.get_items()  # Atualiza referência com os novos dados

    @classmethod
    def get_available_contracts(cls):
        """Returns a list of (ActiveSymbol, Asset) tuples for tradeable contracts."""
        tradeable_symbols = ActiveSymbol.get_items_tradeable()
        available_contracts = []
        for symbol in tradeable_symbols:
            assets = Asset.get_items_by_symbol_id(symbol.symbol)
            for asset in assets:
                available_contracts.append((symbol, asset))
        return available_contracts

    @classmethod
    def get_by_market_display_name(cls, market_display_name: str):
        """Returns a list of (ActiveSymbol, Asset) tuples for a specific market_display_name."""
        market_symbols = ActiveSymbol.get_items_by_market_display_name(market_display_name)
        market_contracts = []
        for symbol in market_symbols:
            assets = Asset.get_items_by_symbol_id(symbol.symbol)
            for asset in assets:
                market_contracts.append((symbol, asset))
        return market_contracts

    @classmethod
    def get_by_submarket_display_name(cls, submarket_display_name: str):
        """Returns a list of (ActiveSymbol, Asset) tuples for a specific submarket_display_name."""
        submarket_symbols = ActiveSymbol.get_items_by_submarket_display_name(submarket_display_name)
        submarket_contracts = []
        for symbol in submarket_symbols:
            assets = Asset.get_items_by_symbol_id(symbol.symbol)
            for asset in assets:
                submarket_contracts.append((symbol, asset))
        return submarket_contracts

    @classmethod
    def get_by_display_name(cls, display_name: str):
        """Returns a list of (ActiveSymbol, Asset) tuples for a specific display_name."""
        display_symbols = ActiveSymbol.get_items_by_display_name(display_name)
        display_contracts = []
        for symbol in display_symbols:
            assets = Asset.get_items_by_symbol_id(symbol.symbol)
            for asset in assets:
                display_contracts.append((symbol, asset))
        return display_contracts

    @classmethod
    def get_by_duration(cls, duration: str, duration_unit: str, fit_in_units: bool = True):
        """Returns a list of (ActiveSymbol, Asset) tuples for a specific duration."""
        duration_assets = Asset.get_items_by_duration(duration=duration, duration_unit=duration_unit, fit_in_units=fit_in_units)
        duration_contracts = []
        for asset in duration_assets:
            symbols = ActiveSymbol.get_items_by_symbol(asset.symbol_id)
            for symbol in symbols:
                duration_contracts.append((symbol, asset))
        return duration_contracts

    @classmethod
    def get_trade_parameters(cls, asset_response, active_response):
        """Interactively guides the user to select a trade parameter, listing all markets with (closed) for closed ones.
        Allows 'exit' at any step to cancel and return empty fields."""
        # Atualiza os dados com as respostas mais recentes do servidor
        cls.populate_assets(asset_response)
        cls.populate_active_symbols(active_response)

        # Obtém todos os símbolos (abertos e fechados)
        all_symbols = ActiveSymbol.get_items()
        if not all_symbols:
            print("Nenhum símbolo disponível no momento.")
            return ["symbol: , market: , submarket: , display_name: , modality: , modality_name: "]

        # Passo 1: Seleção de Mercado
        markets = sorted(set(symbol.market_display_name for symbol in all_symbols))
        market_status = {}
        for market in markets:
            # Verifica se pelo menos um símbolo do mercado está aberto
            is_open = any(symbol.exchange_is_open == 1 and symbol.is_trading_suspended == 0 
                          for symbol in all_symbols if symbol.market_display_name == market)
            market_status[market] = "" if is_open else " (closed)"
        
        print("\nMercados disponíveis:")
        for i, market in enumerate(markets, 1):
            print(f"{i} - {market}{market_status[market]}")
        while True:
            selected_market_input = input("Dos mercados apresentados, selecione uma opção (número) ou 'exit' para sair: ").strip().lower()
            if selected_market_input == "exit":
                confirm = input("Deseja realmente sair? (y/n): ").strip().lower()
                if confirm == "y":
                    return ["symbol: , market: , submarket: , display_name: , modality: , modality_name: "]
                print("Continuando...")
                continue
            try:
                selected_market_idx = int(selected_market_input) - 1
                if 0 <= selected_market_idx < len(markets):
                    selected_market = markets[selected_market_idx]
                    break
                print("Opção inválida. Tente novamente.")
            except ValueError:
                print("Digite um número válido ou 'exit'.")

        # Passo 2: Seleção de Submercado
        submarkets = sorted(set(symbol.submarket_display_name for symbol in all_symbols 
                                if symbol.market_display_name == selected_market))
        print(f"\nSubmercados disponíveis para {selected_market}{market_status[selected_market]}:")
        for i, submarket in enumerate(submarkets, 1):
            print(f"{i} - {submarket}")
        while True:
            selected_submarket_input = input("Dos submercados apresentados, selecione uma opção (número) ou 'exit' para sair: ").strip().lower()
            if selected_submarket_input == "exit":
                confirm = input("Deseja realmente sair? (y/n): ").strip().lower()
                if confirm == "y":
                    return ["symbol: , market: , submarket: , display_name: , modality: , modality_name: "]
                print("Continuando...")
                continue
            try:
                selected_submarket_idx = int(selected_submarket_input) - 1
                if 0 <= selected_submarket_idx < len(submarkets):
                    selected_submarket = submarkets[selected_submarket_idx]
                    break
                print("Opção inválida. Tente novamente.")
            except ValueError:
                print("Digite um número válido ou 'exit'.")

        # Passo 3: Seleção de Símbolo
        symbols = [(symbol.symbol, symbol.display_name) for symbol in all_symbols 
                   if symbol.market_display_name == selected_market and symbol.submarket_display_name == selected_submarket]
        print(f"\nSímbolos disponíveis para {selected_submarket}:")
        for i, (symbol_id, display_name) in enumerate(symbols, 1):
            print(f"{i} - {symbol_id} ({display_name})")
        while True:
            selected_symbol_input = input("Dos símbolos apresentados, selecione uma opção (número) ou 'exit' para sair: ").strip().lower()
            if selected_symbol_input == "exit":
                confirm = input("Deseja realmente sair? (y/n): ").strip().lower()
                if confirm == "y":
                    return ["symbol: , market: , submarket: , display_name: , modality: , modality_name: "]
                print("Continuando...")
                continue
            try:
                selected_symbol_idx = int(selected_symbol_input) - 1
                if 0 <= selected_symbol_idx < len(symbols):
                    selected_symbol_id, selected_symbol_name = symbols[selected_symbol_idx]
                    break
                print("Opção inválida. Tente novamente.")
            except ValueError:
                print("Digite um número válido ou 'exit'.")

        # Passo 4: Seleção de Modalidade (Grupo)
        assets = Asset.get_items_by_symbol_id(selected_symbol_id)
        modality_groups = sorted(set(asset.modality_group for asset in assets))
        print(f"\nGrupos de modalidade disponíveis para {selected_symbol_name}:")
        for i, modality_group in enumerate(modality_groups, 1):
            print(f"{i} - {modality_group}")
        while True:
            selected_modality_group_input = input("Dos grupos de modalidade apresentados, selecione uma opção (número) ou 'exit' para sair: ").strip().lower()
            if selected_modality_group_input == "exit":
                confirm = input("Deseja realmente sair? (y/n): ").strip().lower()
                if confirm == "y":
                    return ["symbol: , market: , submarket: , display_name: , modality: , modality_name: "]
                print("Continuando...")
                continue
            try:
                selected_modality_group_idx = int(selected_modality_group_input) - 1
                if 0 <= selected_modality_group_idx < len(modality_groups):
                    selected_modality_group = modality_groups[selected_modality_group_idx]
                    break
                print("Opção inválida. Tente novamente.")
            except ValueError:
                print("Digite um número válido ou 'exit'.")

        # Passo 5: Seleção de Nome da Modalidade
        modality_names = sorted(set(asset.modality_name for asset in assets 
                                    if asset.modality_group == selected_modality_group))
        print(f"\nNomes de modalidade disponíveis para {selected_modality_group}:")
        for i, modality_name in enumerate(modality_names, 1):
            print(f"{i} - {modality_name}")
        while True:
            selected_modality_name_input = input("Dos nomes de modalidade apresentados, selecione uma opção (número) ou 'exit' para sair: ").strip().lower()
            if selected_modality_name_input == "exit":
                confirm = input("Deseja realmente sair? (y/n): ").strip().lower()
                if confirm == "y":
                    return ["symbol: , market: , submarket: , display_name: , modality: , modality_name: "]
                print("Continuando...")
                continue
            try:
                selected_modality_name_idx = int(selected_modality_name_input) - 1
                if 0 <= selected_modality_name_idx < len(modality_names):
                    selected_modality_name = modality_names[selected_modality_name_idx]
                    break
                print("Opção inválida. Tente novamente.")
            except ValueError:
                print("Digite um número válido ou 'exit'.")

        # Formata o contrato final na ordem solicitada
        trade_parameter = (
            f"symbol: {selected_symbol_id}, "
            f"market: {selected_market}, "
            f"submarket: {selected_submarket}, "
            f"display_name: {selected_symbol_name}, "
            f"modality: {selected_modality_group}, "
            f"modality_name: {selected_modality_name}"
        )
        return [trade_parameter]

async def test_connection_and_requests():
    """Tests connection and sends requests for asset_index and active_symbols."""
    line = f'\n{100*"-"}\n'
    print('Starting connection to DERIV server:')
    dsb = AppDashboard.get_key_names()
    app_name = dsb.get('app')[0]
    token = dsb.get('token')[0]
    conn = ConnManager(app_name, token)
    req = Request()
    await conn.connect()

    print(line)
    print(f'Sending request to server for asset_index: {req.asset_index}')
    asset_response = await conn.send_request(req.asset_index)
    print('Server response (asset_index):')
    pp(asset_response)

    print(line)
    print(f'Sending request to server for active_symbols: {req.active_symbols}')
    active_response = await conn.send_request(req.active_symbols)
    print('Server response (active_symbols):')
    pp(active_response)

    return conn, asset_response, active_response

# async def test_assets(asset_response):
#     """Tests Asset class population and filtering."""
#     line = f'\n{100*"-"}\n'
#     success = Asset.populate(asset_response)
#     print(f"Asset population successful: {success}")
#
#     print(line)
#     print('All assets (Asset):')
#     assets = Asset.get_items()
#     print(f'Total: {len(assets)}')
#     pp(assets[:5])
#     print('...')
#     
#     print(line)
#     print('Assets by symbol_id "frxAUDJPY" (Asset):')
#     audjpy_assets = Asset.get_items_by_symbol_id('frxAUDJPY')
#     print(f'Total: {len(audjpy_assets)}')
#     pp(audjpy_assets)

# async def test_active_symbols(active_response):
#     """Tests ActiveSymbol class population and filtering."""
#     line = f'\n{100*"-"}\n'
#     success = ActiveSymbol.populate(active_response)
#     print(f"ActiveSymbol population successful: {success}")
#
#     print(line)
#     print('All active symbols (ActiveSymbol):')
#     active_symbols = ActiveSymbol.get_items()
#     print(f'Total: {len(active_symbols)}')
#     pp(active_symbols[:5])
#     print('...')
#
#     print(line)
#     print('Tradeable symbols (ActiveSymbol):')
#     tradeable_symbols = ActiveSymbol.get_items_tradeable()
#     print(f'Total: {len(tradeable_symbols)}')
#     pp(tradeable_symbols[:5])
#     print('...')
#
#     print(line)
#     print('Active symbols by market_display_name "Forex" (ActiveSymbol):')
#     forex_symbols = ActiveSymbol.get_items_by_market_display_name('Forex')
#     print(f'Total: {len(forex_symbols)}')
#     pp(forex_symbols[:5])
#     print('...')
#
#     print(line)
#     print('Active symbols by submarket_display_name "Major Pairs" (ActiveSymbol):')
#     major_pairs = ActiveSymbol.get_items_by_submarket_display_name('Major Pairs')
#     print(f'Total: {len(major_pairs)}')
#     pp(major_pairs[:5])
#     print('...')
#
#     print(line)
#     print('Active symbols by display_name "USD/JPY" (ActiveSymbol):')
#     usdjpy_symbols = ActiveSymbol.get_items_by_display_name('USD/JPY')
#     print(f'Total: {len(usdjpy_symbols)}')
#     pp(usdjpy_symbols)

async def test_symbol_manager(asset_response, active_response):
    """Tests SymbolManager class functionality."""
    line = f'\n{100*"-"}\n'

    print(line)
    print('Available contracts (SymbolManager):')
    available_contracts = SymbolManager.get_available_contracts()
    print(f'Total: {len(available_contracts)}')
    pp(available_contracts[:5])
    print('...')

    print(line)
    print('Contracts by market_display_name "Derived" (SymbolManager):')
    derived_contracts = SymbolManager.get_by_market_display_name('Derived')
    print(f'Total: {len(derived_contracts)}')
    pp(derived_contracts[:5])
    print('...')

    print(line)
    print('Contracts by submarket_display_name "Continuous Indices" (SymbolManager):')
    continuous_contracts = SymbolManager.get_by_submarket_display_name('Continuous Indices')
    print(f'Total: {len(continuous_contracts)}')
    pp(continuous_contracts[:5])
    print('...')

    print(line)
    print('Contracts by display_name "Volatility 10 Index" (SymbolManager):')
    vol10_contracts = SymbolManager.get_by_display_name('Volatility 10 Index')
    print(f'Total: {len(vol10_contracts)}')
    pp(vol10_contracts)
    print('...')

    print(line)
    print('Contracts by duration "7t" with fit_in_units=True (SymbolManager):')
    duration_contracts = SymbolManager.get_by_duration(duration='7', duration_unit='t', fit_in_units=True)
    print(f'Total: {len(duration_contracts)}')
    pp(duration_contracts[:5])
    print('...')

    print(line)
    print('Trade Parameters (SymbolManager):')
    trade_parameters = SymbolManager.get_trade_parameters(asset_response, active_response)
    print(f'\nResultado:')
    pp(trade_parameters)

async def main():
    """Integrates connection and class tests."""
    conn, asset_response, active_response = await test_connection_and_requests()
    # await test_assets(asset_response)
    # await test_active_symbols(active_response)
    await test_symbol_manager(asset_response, active_response)
    await conn.disconnect()

if __name__ == "__main__":
    asyncio.run(main())