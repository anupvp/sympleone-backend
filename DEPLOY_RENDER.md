# Deploy SympleOne API on Render

See the full two-service guide in the frontend repo: **`sympleone/DEPLOY_RENDER.md`**.

Quick steps for **this** repository:

1. Push `sympleone-backend` to GitHub.
2. Render → **New** → **Blueprint** → select this repo (`render.yaml` included).
3. Set `SYMPLEONE_ADMIN_PASSWORD` (and Amazon env vars if needed).
4. Note the service URL: `https://sympleone-api.onrender.com`.
5. Configure the frontend with  
   `VITE_API_BASE_URL=https://sympleone-api.onrender.com/api`.

Health check: `/health`  
API docs: `/docs`
