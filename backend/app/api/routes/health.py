from fastapi import APIRouter

from app.core.config import settings
from app.schemas.jobs import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db_kind = "sqlite" if settings.database_url.startswith("sqlite") else "postgresql"
    return HealthResponse(status="ok", app_name=settings.app_name, database=db_kind)
