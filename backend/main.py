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
    # On startup: mark any jobs stuck in a non-terminal state as FAILED.
    # uvicorn --reload kills background tasks mid-run; without this, a reload
    # during extraction leaves the project in PROCESSING forever and blocks
    # all future Rescans with a 409.
    try:
        from app.db.session import SessionLocal
        from app.models.core import ProcessingJob, ProcessingJobStatus, Project, ProjectStatus
        db = SessionLocal()
        try:
            stuck = db.query(ProcessingJob).filter(
                ProcessingJob.status.notin_([
                    ProcessingJobStatus.COMPLETED,
                    ProcessingJobStatus.FAILED,
                ])
            ).all()
            if stuck:
                logger.warning("Startup: marking %d stuck job(s) as FAILED", len(stuck))
                for job in stuck:
                    job.status = ProcessingJobStatus.FAILED
                    job.error = {"message": "Server restarted while job was running"}
                    project = db.query(Project).filter(Project.id == job.project_id).first()
                    if project and project.status == ProjectStatus.PROCESSING:
                        project.status = ProjectStatus.FAILED
                db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error("Startup cleanup failed (non-fatal): %s", e)
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
