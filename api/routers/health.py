from fastapi import APIRouter
from services.health import get_health_status

router = APIRouter(tags=["health"])

@router.get("/health")
def health() -> dict[str, str]:
    return get_health_status()