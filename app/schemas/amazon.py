import re

from pydantic import BaseModel, Field, field_validator

_AMAZON_MARKETPLACE_ID = re.compile(r"^A[A-Z0-9]{8,16}$")


class AmazonConnectRequest(BaseModel):
    marketplace_id: str = Field(
        ...,
        min_length=8,
        max_length=16,
        description="Amazon marketplace identifier (e.g. A21TJRUUN4KGV for Amazon.in).",
    )

    @field_validator("marketplace_id")
    @classmethod
    def validate_marketplace_id(cls, value: str) -> str:
        normalized = value.strip()
        if not _AMAZON_MARKETPLACE_ID.match(normalized):
            raise ValueError("Invalid marketplace_id format")
        return normalized


class AmazonConnectResponse(BaseModel):
    authorization_url: str


class AmazonCallbackCompleteRequest(BaseModel):
    spapi_oauth_code: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    selling_partner_id: str = Field(..., min_length=1)


class AmazonCallbackCompleteResponse(BaseModel):
    redirect_url: str
    success: bool = True
