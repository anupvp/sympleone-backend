from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SYMPLEONE_",
        extra="ignore",
        populate_by_name=True,
    )

    secret_key: str = "dev-secret-change-in-production"
    database_url: str = "sqlite:///./sympleone.db"
    access_token_expire_minutes: int = 480
    admin_email: str = "admin@sympleone.com"
    admin_password: str = "ChangeMeAdmin123!"
    api_prefix: str = "/api"

    # Amazon SP-API website authorization (Login with Amazon / Seller Central consent).
    amazon_app_id: str | None = Field(default=None, validation_alias="AMAZON_APP_ID")
    amazon_client_id: str | None = Field(default=None, validation_alias="AMAZON_CLIENT_ID")
    amazon_client_secret: str | None = Field(default=None, validation_alias="AMAZON_CLIENT_SECRET")
    amazon_redirect_uri: str | None = Field(default=None, validation_alias="AMAZON_REDIRECT_URI")
    amazon_authorize_version: str | None = Field(
        default="beta",
        validation_alias="AMAZON_AUTHORIZE_VERSION",
    )
    amazon_default_seller_central_url: str | None = Field(
        default=None,
        validation_alias="AMAZON_DEFAULT_SELLER_CENTRAL_URL",
    )
    amazon_oauth_state_ttl_minutes: int = Field(
        default=10,
        validation_alias="AMAZON_OAUTH_STATE_TTL_MINUTES",
    )
    amazon_oauth_success_redirect_url: str | None = Field(
        default=None,
        validation_alias="AMAZON_OAUTH_SUCCESS_REDIRECT_URL",
    )
    amazon_oauth_frontend_callback_url: str | None = Field(
        default=None,
        validation_alias="AMAZON_OAUTH_FRONTEND_CALLBACK_URL",
    )


settings = Settings()
