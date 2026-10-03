from pydantic import AliasChoices, Field
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
    amazon_lwa_token_url: str = Field(
        default="https://api.amazon.com/auth/o2/token",
        validation_alias=AliasChoices("AMAZON_LWA_TOKEN_URL", "LWA_TOKEN_URL"),
    )
    # Render / Seller Central may use AMAZON_LOGIN_URI or AMAZON_REDIRECT_URI (same value).
    amazon_redirect_uri: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AMAZON_REDIRECT_URI", "AMAZON_LOGIN_URI"),
    )
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
    amazon_default_marketplace_id: str = Field(
        default="A21TJRUUN4KGV",
        validation_alias="AMAZON_DEFAULT_MARKETPLACE_ID",
    )
    # IAM user keys for SP-API SigV4 (separate from LWA CLIENT_ID / CLIENT_SECRET).
    amazon_sp_api_aws_access_key_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AMAZON_SP_API_AWS_ACCESS_KEY_ID",
            "AMAZON_AWS_ACCESS_KEY_ID",
            "AWS_ACCESS_KEY_ID",
        ),
    )
    amazon_sp_api_aws_secret_access_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AMAZON_SP_API_AWS_SECRET_ACCESS_KEY",
            "AMAZON_AWS_SECRET_ACCESS_KEY",
            "AWS_SECRET_ACCESS_KEY",
        ),
    )
    amazon_sp_api_aws_region: str = Field(
        default="eu-west-1",
        validation_alias=AliasChoices(
            "AMAZON_SP_API_AWS_REGION",
            "AMAZON_AWS_REGION",
            "AWS_DEFAULT_REGION",
        ),
    )


settings = Settings()
