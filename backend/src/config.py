from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Company Brain API"
    debug: bool = False
    database_url: str
    secret_key: str

    model_config = {"env_file": ".env"}


settings = Settings()
