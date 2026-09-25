# SympleOne API

FastAPI backend for **SympleOne**: admin (Symple owner), employees, and sellers with SQLite, JWT auth, roles/policies, groups, and seller assignments.

## User kinds

| Kind | Description |
|------|-------------|
| **admin** | Symple owner — full access, manage employees, sellers, groups, roles |
| **employee** | Symple staff — access seller accounts assigned directly or via groups; privileges from roles/policies |
| **seller** | Marketplace seller — access only own products/services (scope via `accessible_seller_ids`) |

## Quick start

```bash
cd sympleone-backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8080
```

- API base: `http://localhost:8080/api`
- OpenAPI: `http://localhost:8080/docs`
- Health: `http://localhost:8080/health`

Default admin (from `.env`): `admin@sympleone.com` / `ChangeMeAdmin123!`

### Seed 150 sellers

```bash
python -m scripts.seed_sellers
```

Default seller password: `SellerPass123!` (`seller001@sympleone.com` … `seller150@sympleone.com`).

## Auth (matches React frontend)

`POST /api/auth/login`

```json
{ "email": "admin@sympleone.com", "password": "..." }
```

Response:

```json
{
  "accessToken": "<jwt>",
  "user": { "id": "...", "email": "...", "name": "...", "role": "admin" }
}
```

`GET /api/auth/me` — Bearer token, returns policies and status.

## Admin endpoints (Bearer + admin user)

| Area | Endpoints |
|------|-----------|
| Employees | `GET/POST /api/admin/employees`, `PATCH /api/admin/employees/{id}`, `POST .../suspend`, `POST .../activate`, `DELETE ...` |
| Seller assignment | `GET/POST /api/admin/employees/{id}/sellers`, `DELETE .../sellers/{seller_id}` |
| Sellers | `GET/POST /api/admin/sellers`, `PATCH`, `POST .../suspend`, `DELETE` |
| Groups | `GET/POST /api/admin/groups`, `PATCH`, `DELETE` (members: employees + sellers) |
| RBAC | `GET /api/admin/policies`, `GET/POST/PATCH/DELETE /api/admin/roles`, `POST /api/admin/employees/{id}/roles` |

## Scope helper

`GET /api/scope/me` — policies and `accessible_seller_ids` for the current user (use for read-only product/dashboard APIs).

## Configuration

| Env var | Purpose |
|---------|---------|
| `SYMPLEONE_SECRET_KEY` | JWT signing |
| `SYMPLEONE_DATABASE_URL` | Default `sqlite:///./sympleone.db` |
| `SYMPLEONE_ADMIN_EMAIL` / `SYMPLEONE_ADMIN_PASSWORD` | First-run admin seed |

## Frontend

Point the React app at:

```env
VITE_API_BASE_URL=http://localhost:8080/api
VITE_AUTH_RELAXED=false
```

Login path: `auth.login` → `/api/auth/login` (already aligned in `sympleone` `api.config.ts` when base URL is set).
