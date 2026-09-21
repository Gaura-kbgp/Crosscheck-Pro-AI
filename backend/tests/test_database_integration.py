import pytest
from sqlalchemy import text
from app.db.session import engine
from app.core.config import settings

@pytest.mark.skipif(settings.APP_ENV == "test" or not settings.DATABASE_URL or "sqlite" in settings.DATABASE_URL.lower(), reason="Requires actual PostgreSQL DB")
def test_postgres_connection():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
