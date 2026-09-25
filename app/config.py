from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SYMPLEONE_", extra="ignore")

    secret_key: str = "dev-secret-change-in-production"
    database_url: str = "sqlite:///./sympleone.db"
    access_token_expire_minutes: int = 480
    admin_email: str = "admin@sympleone.com"
    admin_password: str = "ChangeMeAdmin123!"
    api_prefix: str = "/api"


settings = Settings()
