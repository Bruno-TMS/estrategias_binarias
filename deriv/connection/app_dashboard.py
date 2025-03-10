"""Módulo app_dashboard.py

Gerencia chaves de acesso a dashboards usando o padrão Singleton com recriação condicional.
Lê o arquivo CSV a cada operação para refletir mudanças em tempo real, garantindo unicidade
e segurança. Permite descartar a instância atual e criar uma nova se os parâmetros mudarem.
O CSV tem colunas 'key', 'name', 'value', onde 'key' diferencia 'app' e 'token'.
"""

from csv import DictReader
from pathlib import Path

# Caminho absoluto do arquivo CSV
KNV_FILE = Path('connection/secrets.csv').absolute()
"""Arquivo CSV com chaves de acesso no formato:
    key,name,value
    Exemplo: 'app','appteste','xxxx'
             'token','tkneste','yyyy'
    'key' diferencia 'app' e 'token'; 'value' é o dado associado ao 'name'.
"""

class AppDashboard:
    """Classe Singleton para gerenciar chaves de acesso a dashboards, com recriação condicional.

    Atributos:
        _instance: Instância única da classe (None até ser criada ou recriada).
        _app_id: ID do aplicativo (valor de 'value' onde 'key' é 'app').
        _token: Token de acesso (valor de 'value' onde 'key' é 'token').
        _app_name: Nome do aplicativo (valor de 'name' onde 'key' é 'app').
        _token_name: Nome do token (valor de 'name' onde 'key' é 'token').
    """

    _instance = None

    def __new__(cls, *, app_name: str, token_name: str) -> "AppDashboard":
        """Cria ou recria a instância única da classe, validando app e token.

        Se já existir uma instância e os parâmetros 'app_name' ou 'token_name' diferirem
        dos atuais, a instância existente é descartada e uma nova é criada.

        Args:
            app_name: Nome do aplicativo (corresponde a 'name' onde 'key' é 'app').
            token_name: Nome do token (corresponde a 'name' onde 'key' é 'token').

        Returns:
            Instância única de AppDashboard (nova ou existente).

        Raises:
            ValueError: Se app_name ou token_name não forem encontrados no CSV.
            FileNotFoundError: Se o arquivo CSV não existir.

        Nota:
            Os parâmetros são nomeados obrigatoriamente (keyword-only). O último valor
            encontrado no CSV é usado se houver duplicatas para o mesmo 'name' e 'key'.
        """
        # Verifica se a instância existe e se os parâmetros diferem
        if cls._instance and (
            cls._instance._app_name != app_name or cls._instance._token_name != token_name
        ):
            # Descarta a instância atual se os valores mudarem
            cls._instance = None

        if not cls._instance:
            app_id = None
            token = None

            # Lê o CSV, diferenciando app e token pelo 'key'
            with open(KNV_FILE, "r", encoding="utf-8") as csv_file:
                csv_reader = DictReader(csv_file)
                for row in csv_reader:
                    if row["key"] == "app" and row["name"] == app_name:
                        app_id = row["value"]
                    if row["key"] == "token" and row["name"] == token_name:
                        token = row["value"]

            # Valida se ambos foram encontrados
            if not (app_id and token):
                raise ValueError(
                    f"App '{app_name}' ou token '{token_name}' não encontrados no CSV."
                )

            # Cria a nova instância
            cls._instance = super().__new__(cls)
            cls._instance._app_id = app_id
            cls._instance._token = token
            cls._instance._app_name = app_name
            cls._instance._token_name = token_name

        return cls._instance

    @property
    def app_id(self) -> str:
        """Retorna o ID do aplicativo.

        Returns:
            O valor associado ao 'name' do app no CSV.
        """
        return self._app_id

    @property
    def token(self) -> str:
        """Retorna o token de acesso.

        Returns:
            O valor associado ao 'name' do token no CSV.
        """
        return self._token

    @property
    def app_name(self) -> str:
        """Retorna o nome do aplicativo.

        Returns:
            O 'name' do app usado na criação da instância.
        """
        return self._app_name

    @property
    def token_name(self) -> str:
        """Retorna o nome do token.

        Returns:
            O 'name' do token usado na criação da instância.
        """
        return self._token_name

    @classmethod
    def get_key_names(cls) -> dict:
        """Retorna um dicionário com os nomes disponíveis por tipo de chave.

        Returns:
            Dicionário no formato {key: [nomes]}.
            Exemplo: {'app': ['appteste'], 'token': ['tkneste']}

        Raises:
            FileNotFoundError: Se o arquivo CSV não existir.
        """
        key_names = {}
        with open(KNV_FILE, "r", encoding="utf-8") as csv_file:
            csv_reader = DictReader(csv_file)
            for row in csv_reader:
                key_names.setdefault(row["key"], []).append(row["name"])
        return key_names

if __name__ == "__main__":
    # Exemplo de uso
    print(f"Path do arquivo de chaves: {KNV_FILE}")
    print(f"Chaves disponíveis: {AppDashboard.get_key_names()}")

    # Criação da primeira instância
    try:
        dashboard1 = AppDashboard(app_name="appteste", token_name="tkneste")
        print(f"Instância 1 - App ID: {dashboard1.app_id}, Token: {dashboard1.token}")
    except (ValueError, FileNotFoundError) as e:
        print(f"Erro na instância 1: {e}")

    # Tentativa de criar uma nova instância com valores diferentes
    try:
        dashboard2 = AppDashboard(app_name="appteste2", token_name="tkneste2")
        print(f"Instância 2 - App ID: {dashboard2.app_id}, Token: {dashboard2.token}")
    except (ValueError, FileNotFoundError) as e:
        print(f"Erro na instância 2: {e}")