import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    PROJECT_NAME: str = "OLT Provisioning & Diagnostics API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Autenticação
    API_KEY: str = "oltapi_secret_default_key_change_me"

    # Armazenamento de Backups e Dados
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    BACKUP_DIR: Path = BASE_DIR / "backups"
    DATA_DIR: Path = BASE_DIR / "data"

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


settings = Settings()

# Garante que os diretórios necessários existem
settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
