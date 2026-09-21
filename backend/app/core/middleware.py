import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects standard defense-in-depth security response headers.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        from app.core.config import settings
        if request.url.scheme == "https" or settings.APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            
        return response
