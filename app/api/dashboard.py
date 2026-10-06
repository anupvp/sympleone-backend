import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User, UserKind
from app.services.dashboard.context import resolve_dashboard_seller
from app.schemas.dashboard import (
    AccountHealthOut,
    AlertActionItemOut,
    MarketplaceRowOut,
    ProfitabilityOut,
    ProfitabilityNetProfitOut,
    SalesTrendOut,
    StatCardOut,
)
from app.services.dashboard.account_health_service import build_account_health_for_user
from app.services.dashboard.sales_trend_service import SalesTrendError, build_sales_trend_for_user
from app.services.dashboard.alerts_service import build_dashboard_alerts
from app.services.dashboard.stats_service import DashboardStatsError, build_dashboard_stats_for_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _empty_profitability() -> ProfitabilityOut:
    return ProfitabilityOut(
        centerLabel="Net Profit",
        centerValue="—",
        segments=[],
        netProfit=ProfitabilityNetProfitOut(label="Net Profit", amount="—", percent=0.0),
    )


def _dashboard_seller(
    user: User,
    db: Session,
    sellerId: str | None,
) -> User | None:
    if user.kind == UserKind.SELLER:
        return None
    return resolve_dashboard_seller(db, user, sellerId)


@router.get("/sales-trend", response_model=SalesTrendOut)
def get_sales_trend(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    accountId: str = Query(default="all"),
    marketplaceId: str = Query(default="all"),
    dateFrom: str | None = Query(default=None),
    dateTo: str | None = Query(default=None),
    sellerId: str | None = Query(default=None),
) -> SalesTrendOut:
    del accountId  # reserved for multi-account sellers
    try:
        payload = build_sales_trend_for_user(
            db,
            user,
            marketplace_id=marketplaceId,
            date_from=dateFrom,
            date_to=dateTo,
            seller=_dashboard_seller(user, db, sellerId),
        )
        return SalesTrendOut(**payload)
    except SalesTrendError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Failed to build sales trend for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not load sales trend from Amazon",
        ) from None


@router.get("/stats", response_model=list[StatCardOut])
def get_dashboard_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    accountId: str = Query(default="all"),
    marketplaceId: str = Query(default="all"),
    dateFrom: str | None = Query(default=None),
    dateTo: str | None = Query(default=None),
    sellerId: str | None = Query(default=None),
) -> list[StatCardOut]:
    del accountId  # reserved for multi-account sellers
    try:
        cards = build_dashboard_stats_for_user(
            db,
            user,
            marketplace_id=marketplaceId,
            date_from=dateFrom,
            date_to=dateTo,
            seller=_dashboard_seller(user, db, sellerId),
        )
        return [StatCardOut(**card) for card in cards]
    except DashboardStatsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Failed to build dashboard stats for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not load dashboard stats from Amazon",
        ) from None


@router.get("/profitability", response_model=ProfitabilityOut)
def get_profitability(
    _: User = Depends(get_current_user),
) -> ProfitabilityOut:
    return _empty_profitability()


@router.get("/account-health", response_model=AccountHealthOut)
def get_account_health(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountHealthOut:
    payload = build_account_health_for_user(db, user)
    return AccountHealthOut(**payload)


@router.get("/alerts", response_model=list[AlertActionItemOut])
def get_alerts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AlertActionItemOut]:
    items = build_dashboard_alerts(db, user)
    return [AlertActionItemOut(**item) for item in items]


@router.get("/marketplaces", response_model=list[MarketplaceRowOut])
def get_marketplaces(
    _: User = Depends(get_current_user),
) -> list[MarketplaceRowOut]:
    return []
