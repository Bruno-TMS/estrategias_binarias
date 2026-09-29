from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Configurações da Aplicação
    app_name: str = Field(
        default="Estratégias Binárias API",
        description="Nome da aplicação",
    )
    debug: bool = Field(
        default=False,
        description="Modo de depuração (debug)",
    )
    port: int = Field(
        default=8000,
        description="Porta de execução do servidor",
    )

    # Configurações da Deriv API
    deriv_app_id: str = Field(
        default="1089",
        description="ID do aplicativo registrado na Deriv API",
    )
    deriv_api_token: str = Field(
        default="",
        validation_alias=AliasChoices("DERIV_API_TOKEN", "DERIV_TOKEN"),
        description="Token de autenticação da Deriv API",
    )
    deriv_ws_url: str = Field(
        default="wss://api.derivws.com/trading/v1/options/ws/public",
        description="URL do WebSocket da Deriv API",
    )
    database_url: str = Field(
        default="sqlite:///./trading_memory.db",
        description="URL de conexão com o banco de dados SQLite local",
    )

    @property
    def deriv_token(self) -> str:
        """Alias para manter compatibilidade com chamadas legado a settings.deriv_token."""
        return self.deriv_api_token


settings = Settings()
