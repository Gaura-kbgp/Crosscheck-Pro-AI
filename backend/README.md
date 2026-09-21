# CrossCheckPro Backend - Phase 1

## Setup

1. Python version: Python 3.10+
2. Virtual environment setup:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Environment variables:
   Copy `.env.example` to `.env` and fill in your details.

5. How to start FastAPI:
   ```powershell
   uvicorn main:app --reload
   ```

6. How to run Alembic:
   ```powershell
   alembic upgrade head
   ```

7. How to start Celery:
   ```powershell
   celery -A app.worker.celery_app.celery_app worker --loglevel=info
   ```

8. How to run tests:
   ```powershell
   pytest
   ```

## Supabase PostgreSQL Setup

1. Create/open Supabase project
2. Obtain PostgreSQL connection string
3. Put it in `.env` (e.g. `DATABASE_URL=postgresql+psycopg://postgres.projectid:password@aws-0-region.pooler.supabase.com:6543/postgres`)
4. Install dependencies: `pip install -r requirements.txt`
5. Run Alembic: `alembic upgrade head`
6. Verify migration status: `alembic current` and `alembic heads`
7. Start FastAPI: `uvicorn main:app --reload`
