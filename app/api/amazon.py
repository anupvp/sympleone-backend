from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_amazon_seller_connect
from app.models import User
from app.schemas.amazon import AmazonConnectRequest, AmazonConnectResponse
from app.services.amazon.oauth_service import start_amazon_connect

router = APIRouter(prefix="/amazon", tags=["amazon"])


@router.post("/connect", response_model=AmazonConnectResponse)
def connect_amazon_seller(
    body: AmazonConnectRequest,
    user: User = Depends(require_amazon_seller_connect),
    db: Session = Depends(get_db),
) -> AmazonConnectResponse:
    authorization_url = start_amazon_connect(db, user, body.marketplace_id)
    return AmazonConnectResponse(authorization_url=authorization_url)
