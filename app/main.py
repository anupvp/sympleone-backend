from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import amazon, auth, dashboard, legal_pages, scope
from app.api.admin import employees, groups, roles, sellers
from app.config import settings
from app.middleware.admin_auth import AdminAuthMiddleware
from app.seed import run_seed


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_seed()
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
app.include_router(dashboard.router, prefix=api)
app.include_router(amazon.router, prefix=api)
app.include_router(scope.router, prefix=api)
app.include_router(employees.router, prefix=api)
app.include_router(sellers.router, prefix=api)
app.include_router(groups.router, prefix=api)
app.include_router(roles.router, prefix=api)
app.include_router(legal_pages.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "sympleone"}
