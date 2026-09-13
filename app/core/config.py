import os
from pathlib import Path
from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    PROJECT_NAME: str = "OLT Provisioning & Diagnostics API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Autenticação
    API_KEY: str = "oltapi_secret_default_key_change_me"
    JWT_SECRET: str = "oltapi_jwt_secret_key_change_me_in_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 horas por padrão

    # Armazenamento de Backups e Dados
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    BACKUP_DIR: Path = BASE_DIR / "backups"
    DATA_DIR: Path = BASE_DIR / "data"

    # Configurações do Banco de Dados Relacional
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: Optional[int] = 5432
    POSTGRES_DB: Optional[str] = None

    DATABASE_URL: Optional[str] = None
    DATABASE_ECHO: bool = False

    @model_validator(mode="after")
    def assemble_database_url(self) -> "Settings":
        if not self.DATABASE_URL or self.DATABASE_URL.strip() == "":
            if self.POSTGRES_USER and self.POSTGRES_PASSWORD and self.POSTGRES_HOST and self.POSTGRES_DB:
                port = self.POSTGRES_PORT or 5432
                self.DATABASE_URL = (
                    f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
                    f"{self.POSTGRES_HOST}:{port}/{self.POSTGRES_DB}"
                )
            else:
                self.DATABASE_URL = "sqlite:///./data/oltapi.db"
        return self

    # Configuração de Conexão com OLTs
    DEFAULT_SSH_TIMEOUT: int = 15  # segundos

    # Políticas de Backup e Retenção Padrão
    BACKUP_RETENTION_MAX: int = 30
    BACKUP_RETENTION_DAYS: int = 60

    # Configurações do Autofind Scanner em Segundo Plano
    SCANNER_ENABLED_ON_STARTUP: bool = False
    SCANNER_INTERVAL_SECONDS: int = 60
    SCANNER_MIN_INTERVAL_SECONDS: int = 10

    # Nível de Log
    LOG_LEVEL: str = "INFO"

    # Configurações Padrão de Bancada / Homologação (lidas do .env)
    OLT_DEFAULT_NAME: Optional[str] = None
    OLT_DEFAULT_VENDOR: Optional[str] = None
    OLT_DEFAULT_MODEL: Optional[str] = None
    OLT_DEFAULT_HOST: Optional[str] = None
    OLT_DEFAULT_PORT: int = 23
    OLT_DEFAULT_PROTOCOL: str = "telnet"
    OLT_DEFAULT_USER: Optional[str] = None
    OLT_DEFAULT_PASS: Optional[str] = None

    # Servidor FTP Central de Backup (lido do .env)
    FTP_DEFAULT_NAME: Optional[str] = None
    FTP_DEFAULT_HOST: Optional[str] = None
    FTP_DEFAULT_PORT: int = 21
    FTP_DEFAULT_USER: Optional[str] = None
    FTP_DEFAULT_PASS: Optional[str] = None
    FTP_DEFAULT_BASE_PATH: str = "/"
    FTP_DEFAULT_IS_GLOBAL: bool = True


settings = Settings()

# Garante que os diretórios necessários existem
settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
