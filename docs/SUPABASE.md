# Supabase integration

PromptCode’s backend can use [Supabase](https://supabase.com) PostgreSQL instead of a local or self-hosted Postgres.

## What’s configured

- **Database**: The FastAPI app and Alembic use `PROMPTCODE_DATABASE_URL` with the `asyncpg` driver. Supabase’s connection string works with SSL enabled via `PROMPTCODE_DATABASE_SSL_REQUIRE=true`.
- **Auth**: The app keeps its existing JWT-based auth (signup/login in `backend`). It does **not** use Supabase Auth; only the database is backed by Supabase.

## Setup

1. **Create a Supabase project** at [supabase.com](https://supabase.com).

2. **Get the connection string**  
   Project Settings → Database → **Connection string** → **URI**.  
   Use either:
   - **Session mode** (port 5432), or  
   - **Transaction mode** (port 6543) for serverless-style connections.

3. **Adjust the URI for asyncpg**  
   Replace the scheme:
   - From: `postgresql://...`  
   - To: `postgresql+asyncpg://...`  
   Replace any `[YOUR-PASSWORD]` with your database password.

4. **Set environment variables** (e.g. in `.env` at the repo root):

   ```env
   PROMPTCODE_DATABASE_URL=postgresql+asyncpg://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres
   PROMPTCODE_DATABASE_SSL_REQUIRE=true
   ```

5. **Run migrations** (from repo root so `.env` is loaded):

   ```bash
   cd backend
   alembic upgrade head
   ```

6. **Seed challenges** (optional):

   ```bash
   python -m scripts.seed_challenge
   ```

7. **Start the backend** (no Docker Postgres needed):

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

## Optional: Supabase Auth and frontend

To use **Supabase Auth** (e.g. magic link, OAuth) instead of the current backend signup/login:

- You’d add the Supabase JS client to the frontend, call `supabase.auth.signInWith*`, and send the Supabase JWT to the backend.
- The backend would then validate the Supabase JWT (e.g. with Supabase’s JWT secret or a small auth service) instead of issuing its own tokens.

That would be a separate change; the current integration is **database-only** (Supabase Postgres + SSL).
