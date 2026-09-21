from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

if not settings.DATABASE_URL:
    if settings.APP_ENV == "test":
        db_url = "sqlite:///./test.db"
    else:
        raise ValueError("DATABASE_URL must be provided in development/production environments. Do not fall back to SQLite silently.")
else:
    db_url = settings.DATABASE_URL

engine = create_engine(
    db_url,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
