from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import decode_access_token
from app.database import SessionLocal
from app.models import User, UserKind, UserStatus

API_PREFIX = "/api"


def _requires_admin(path: str, method: str) -> bool:
    """Admin-only admin API routes (employees, groups, roles/policies; seller mutations)."""
    if path.startswith(f"{API_PREFIX}/admin/employees"):
        return True
    if path.startswith(f"{API_PREFIX}/admin/groups"):
        return True
    if path.startswith(f"{API_PREFIX}/admin/roles") or path.startswith(
        f"{API_PREFIX}/admin/policies"
    ):
        return True
    if path.startswith(f"{API_PREFIX}/admin/sellers") and method.upper() != "GET":
        return True
    return False


class AdminAuthMiddleware(BaseHTTPMiddleware):
    """Validate Bearer JWT and admin role before admin management handlers run."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if request.method == "OPTIONS" or not _requires_admin(path, request.method):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": (
                        "Authentication required. Send header "
                        "Authorization: Bearer <accessToken> from POST /api/auth/login."
                    )
                },
            )

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid Authorization header. Use: Bearer <accessToken>."},
            )

        token = parts[1].strip()
        if token.startswith("relaxed."):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": (
                        "Development mock token cannot call the API. "
                        "Set VITE_AUTH_RELAXED=false in the frontend, sign out, and log in again."
                    )
                },
            )

        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired access token."},
            )

        db = SessionLocal()
        try:
            user = db.get(User, payload["sub"])
            if not user:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "User not found for this token."},
                )
            if user.status == UserStatus.SUSPENDED:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Account suspended."},
                )
            if user.kind != UserKind.ADMIN:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": (
                            "Admin access required. Only Symple owner (admin) accounts "
                            "can manage employees, sellers, and groups."
                        )
                    },
                )
            request.state.auth_user = user
        finally:
            db.close()

        return await call_next(request)
