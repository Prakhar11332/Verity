from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """Health check endpoint confirming backend service status."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.env,
    }
