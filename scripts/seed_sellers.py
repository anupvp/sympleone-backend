"""Create demo seller accounts (e.g. 150). Run: python -m scripts.seed_sellers"""

from sqlalchemy import select

from app.core.security import hash_password
from app.database import SessionLocal
from app.models import User, UserKind, UserStatus
from app.seed import run_seed


def main(count: int = 150) -> None:
    run_seed()
    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.kind == UserKind.SELLER)).scalars().all()
        start = len(existing) + 1
        for i in range(start, count + 1):
            email = f"seller{i:03d}@sympleone.com"
            if db.execute(select(User.id).where(User.email == email)).first():
                continue
            db.add(
                User(
                    email=email,
                    full_name=f"Seller {i:03d}",
                    hashed_password=hash_password("SellerPass123!"),
                    kind=UserKind.SELLER,
                    status=UserStatus.ACTIVE,
                )
            )
        db.commit()
        total = db.execute(select(User).where(User.kind == UserKind.SELLER)).scalars().all()
        print(f"Seller accounts in database: {len(total)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
