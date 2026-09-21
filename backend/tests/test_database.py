from app.db.session import engine, SessionLocal
from sqlalchemy import text
import pytest

def test_engine_initializes():
    assert engine is not None

def test_session_can_connect():
    session = SessionLocal()
    try:
        # Checking if it can compile a basic statement
        result = session.execute(text("SELECT 1"))
        assert result.scalar() == 1
    except Exception:
        pytest.skip("Database not available for testing")
    finally:
        session.close()
