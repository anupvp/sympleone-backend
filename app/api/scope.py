from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.permissions import accessible_seller_ids, user_policy_codes
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/scope", tags=["scope"])


@router.get("/me")
def my_scope(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """What this login can access — sellers and policy codes."""
    return {
        "user_id": user.id,
        "kind": user.kind.value,
        "policies": sorted(user_policy_codes(db, user)),
        "accessible_seller_ids": sorted(accessible_seller_ids(db, user)),
    }
