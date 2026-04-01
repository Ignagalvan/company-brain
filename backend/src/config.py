from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    app_name: str = "Company Brain API"
    debug: bool = False
    database_url: str
    secret_key: str

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env"
    )

settings = Settings()