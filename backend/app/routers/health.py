from fastapi import APIRouter

from app.config.settings import get_settings
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", service=settings.app_name)
