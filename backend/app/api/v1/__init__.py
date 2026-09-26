from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.projects import router as projects_router
from app.api.v1.documents import router as documents_router
from app.api.v1.processing import router as processing_router
from app.api.v1.crosscheck import router as crosscheck_router
from app.api.v1.review import router as review_router
from app.api.v1.reports import router as reports_router
from app.api.v1.manufacturers import router as manufacturers_router
from app.api.v1.nkba_reference import router as nkba_reference_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router)
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(organizations_router, prefix="/organizations", tags=["organizations"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(documents_router, tags=["documents"])
api_router.include_router(processing_router, tags=["processing"])
api_router.include_router(crosscheck_router, tags=["crosscheck"])
api_router.include_router(review_router, tags=["review"])
api_router.include_router(reports_router, tags=["reports"])
api_router.include_router(manufacturers_router, prefix="/manufacturers", tags=["manufacturers"])
api_router.include_router(nkba_reference_router, prefix="/nkba-reference-documents", tags=["nkba-reference"])
