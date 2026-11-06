from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.core.exceptions import BaseAPIException, global_exception_handler, unhandled_exception_handler
from app.api.v1 import api_router
import logging

logger = logging.getLogger(__name__)

# Setup structured logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Recover jobs abandoned by a previous server process.
    # Multi-instance safe: only marks jobs whose heartbeat is stale or absent
    # beyond the grace window (see recover_stale_jobs for the full policy).
    try:
        from app.db.session import SessionLocal
        from app.services.processing_service import recover_stale_jobs
        db = SessionLocal()
        try:
            count = recover_stale_jobs(db)
            if count:
                logger.warning("Startup: recovered %d stale job(s)", count)
        finally:
            db.close()
    except Exception as e:
        logger.error("Startup recovery failed (non-fatal): %s", e)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="v1",
    lifespan=lifespan,
)

# CORS
# Always include the known production + local dev origins as a fallback, so a
# missing/misconfigured CORS_ORIGINS env var on the host (e.g. Render) can never
# silently lock every user out of auth (see TESTING_REVIEW_FIXLIST.md P0-1).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.resolved_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)

# Exception handlers
app.add_exception_handler(BaseAPIException, global_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# Routers
app.include_router(api_router, prefix="/api/v1")
