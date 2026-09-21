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
cors_origins = list(set(settings.cors_origins_list + [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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
