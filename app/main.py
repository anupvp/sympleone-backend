import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import amazon, auth, dashboard, legal_pages, public_stats, scope
from app.api.admin import employees, groups, roles, sellers
from app.config import settings
from app.middleware.admin_auth import AdminAuthMiddleware
from app.seed import run_seed
from app.services.amazon.amazon_credentials import (
    amazon_oauth_configured,
    sp_api_iam_signing_configured,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_seed()
    logger.info(
        "Amazon config: oauth=%s lwa_token_url_set=%s iam_signing=%s",
        amazon_oauth_configured(),
        bool((settings.amazon_lwa_token_url or "").strip()),
        sp_api_iam_signing_configured(),
    )
    yield


app = FastAPI(
    title="SympleOne API",
    description="Auth, RBAC, employees, sellers, and groups for SympleOne.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AdminAuthMiddleware)

api = settings.api_prefix
app.include_router(auth.router, prefix=api)
app.include_router(public_stats.router, prefix=api)
app.include_router(dashboard.router, prefix=api)
app.include_router(amazon.router, prefix=api)
app.include_router(scope.router, prefix=api)
app.include_router(employees.router, prefix=api)
app.include_router(sellers.router, prefix=api)
app.include_router(groups.router, prefix=api)
app.include_router(roles.router, prefix=api)
app.include_router(legal_pages.router)


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": "sympleone",
        "amazonOAuthConfigured": amazon_oauth_configured(),
        "amazonIamSigningConfigured": sp_api_iam_signing_configured(),
    }
