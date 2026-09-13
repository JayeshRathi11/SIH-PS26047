from fastapi import APIRouter
from app.core.database import check_db_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "MediKiosk Backend",
    }


@router.get("/health/db")
def database_health_check():
    connected, message = check_db_connection()
    return {
        "connected": connected,
        "detail": message,
    }
