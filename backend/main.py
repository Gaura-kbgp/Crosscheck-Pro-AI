from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.core.exceptions import BaseAPIException, global_exception_handler, unhandled_exception_handler
from app.api.v1 import api_router

# Setup structured logging
setup_logging()

app = FastAPI(
    title=settings.APP_NAME,
    version="v1",
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
