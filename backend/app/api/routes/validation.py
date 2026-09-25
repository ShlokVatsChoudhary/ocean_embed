from datetime import date

from fastapi import APIRouter, Query

from app.schemas.oceanembed import ValidationResponse
from app.services.validation import get_validation as get_validation_service

router = APIRouter(prefix="/api/validation", tags=["validation"])


@router.get("", response_model=ValidationResponse, summary="Return validation metrics and ARGO observation comparisons")
@router.get("/", include_in_schema=False)
async def get_validation(
    selected_date: date | None = Query(default=None, alias="date", description="Optional date filter for validation data."),
    depth: float | None = Query(default=None, description="Optional depth filter in meters."),
    latitude: float | None = Query(default=None, description="Optional latitude filter."),
    longitude: float | None = Query(default=None, description="Optional longitude filter."),
    argo_profile_id: str | None = Query(default=None, description="Optional ARGO profile identifier."),
) -> ValidationResponse:
    return get_validation_service(
        selected_date,
        depth,
        latitude,
        longitude,
        argo_profile_id,
    )
