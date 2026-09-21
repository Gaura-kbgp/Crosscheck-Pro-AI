from fastapi import Request, status
from fastapi.responses import JSONResponse
import structlog
import uuid

logger = structlog.get_logger(__name__)

class BaseAPIException(Exception):
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, details: dict = None):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class ResourceNotFoundError(BaseAPIException):
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, code="RESOURCE_NOT_FOUND", status_code=status.HTTP_404_NOT_FOUND, details=details)

class BusinessLogicError(BaseAPIException):
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, code="BUSINESS_LOGIC_ERROR", status_code=status.HTTP_400_BAD_REQUEST, details=details)

async def global_exception_handler(request: Request, exc: BaseAPIException):
    request_id = request.state.request_id if hasattr(request.state, "request_id") else str(uuid.uuid4())
    logger.error("api_error", code=exc.code, message=exc.message, request_id=request_id)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id
            }
        }
    )

async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = request.state.request_id if hasattr(request.state, "request_id") else str(uuid.uuid4())
    logger.exception("unhandled_error", error=str(exc), request_id=request_id)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
                "details": {},
                "request_id": request_id
            }
        }
    )
