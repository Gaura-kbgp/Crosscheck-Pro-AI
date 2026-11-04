import pytest
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from main import app
from app.db.base import Base
from app.api.dependencies import get_db

@pytest.fixture(scope="session")
def engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture(scope="function")
def db_session(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def mock_celery_delay(monkeypatch):
    monkeypatch.setattr("celery.app.task.Task.delay", lambda *args, **kwargs: None)

@pytest.fixture(autouse=True)
def reset_rate_limiter(monkeypatch):
    from app.core.rate_limiter import reset_rate_limit_store, RateLimiter

    # RateLimiter tries the real Redis (settings.REDIS_URL — the project's
    # actual shared Upstash instance per .env) before falling back to the
    # in-memory store this fixture resets. Tests therefore accumulate hits
    # against that one shared, cross-run Redis key regardless of the reset
    # below, causing cascading 429s the more times the suite has been run
    # (observed: auth/password tests failing with 429 instead of their
    # expected status). Force the in-memory path for the whole test session
    # so rate-limit tests are deterministic and isolated from any other
    # process hitting the same Redis instance.
    monkeypatch.setattr(RateLimiter, "_check_redis", lambda self, key: None)

    reset_rate_limit_store()
    yield
    reset_rate_limit_store()
