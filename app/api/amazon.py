import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_optional_current_user, require_amazon_seller_connect
from app.models import User
from app.schemas.amazon import AmazonConnectRequest, AmazonConnectResponse
from app.services.amazon.appstore_login_service import (
    AppstoreLoginConfigurationError,
    AppstoreLoginValidationError,
    process_appstore_login,
)
from app.services.amazon.callback_service import (
    CallbackProcessingError,
    CallbackValidationError,
    error_redirect_url,
    process_amazon_oauth_callback,
)
from app.services.amazon.oauth_service import start_amazon_connect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/amazon", tags=["amazon"])


@router.get(
    "/login",
    response_class=RedirectResponse,
    status_code=status.HTTP_302_FOUND,
    summary="Amazon Selling Partner Appstore login",
    description="Initiates the Amazon Selling Partner Appstore authorization flow for Symple One.",
)
def amazon_appstore_login(
    amazon_callback_uri: str | None = Query(
        None,
        description="Amazon-provided callback URI (HTTPS, Amazon-operated host).",
    ),
    amazon_state: str | None = Query(
        None,
        description="Opaque state value supplied by Amazon; preserved on redirect.",
    ),
    selling_partner_id: str | None = Query(
        None,
        description="Amazon Selling Partner ID for the authorizing seller.",
    ),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
) -> RedirectResponse:
    if amazon_callback_uri is None or amazon_callback_uri == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="amazon_callback_uri is required",
        )
    if amazon_state is None or amazon_state == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="amazon_state is required",
        )
    if selling_partner_id is None or selling_partner_id == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="selling_partner_id is required",
        )
    try:
        redirect_url = process_appstore_login(
            db,
            amazon_callback_uri=amazon_callback_uri,
            amazon_state=amazon_state,
            selling_partner_id=selling_partner_id,
            user=user,
        )
    except AppstoreLoginValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except AppstoreLoginConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("Failed to persist Amazon Appstore OAuth session")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not start Amazon authorization session",
        ) from exc

    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/callback",
    response_class=RedirectResponse,
    status_code=status.HTTP_302_FOUND,
    summary="Amazon SP-API OAuth callback",
    description="Completes Amazon Selling Partner Appstore authorization after seller consent.",
)
def amazon_oauth_callback(
    spapi_oauth_code: str | None = Query(None, description="Authorization code from Amazon."),
    state: str | None = Query(None, description="Symple One OAuth state from the login flow."),
    selling_partner_id: str | None = Query(None, description="Amazon Selling Partner ID."),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if spapi_oauth_code is None or spapi_oauth_code == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="spapi_oauth_code is required",
        )
    if state is None or state == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="state is required",
        )
    if selling_partner_id is None or selling_partner_id == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="selling_partner_id is required",
        )
    try:
        success_url = process_amazon_oauth_callback(
            db,
            spapi_oauth_code=spapi_oauth_code,
            state=state,
            selling_partner_id=selling_partner_id,
        )
    except CallbackValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except CallbackProcessingError:
        return RedirectResponse(url=error_redirect_url(), status_code=status.HTTP_302_FOUND)
    except SQLAlchemyError:
        logger.exception("Failed to persist Amazon seller authorization")
        return RedirectResponse(url=error_redirect_url(), status_code=status.HTTP_302_FOUND)

    return RedirectResponse(url=success_url, status_code=status.HTTP_302_FOUND)


@router.post("/connect", response_model=AmazonConnectResponse)
def connect_amazon_seller(
    body: AmazonConnectRequest,
    user: User = Depends(require_amazon_seller_connect),
    db: Session = Depends(get_db),
) -> AmazonConnectResponse:
    authorization_url = start_amazon_connect(db, user, body.marketplace_id)
    return AmazonConnectResponse(authorization_url=authorization_url)
