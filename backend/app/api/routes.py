from fastapi import APIRouter

from app.api.ai_explanations import router as ai_explanations_router
from app.api.audit_log import router as audit_log_router
from app.api.data_quality import router as data_quality_router
from app.api.exceptions import router as exceptions_router
from app.api.health import router as health_router
from app.api.reconciliation import router as reconciliation_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(reconciliation_router)
api_router.include_router(exceptions_router)
api_router.include_router(audit_log_router)
api_router.include_router(ai_explanations_router)
api_router.include_router(data_quality_router)

