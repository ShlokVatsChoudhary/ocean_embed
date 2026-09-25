from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.schemas.oceanembed import ValidationResponse
from app.services.validation import get_validation as get_validation_service
from app.validation import validate_depth, validate_latitude, validate_longitude

router = APIRouter(prefix="/api/validation", tags=["validation"])


@router.get("", response_model=ValidationResponse, summary="Return validation metrics and ARGO observation comparisons")
@router.get("/", include_in_schema=False)
async def get_validation(
    selected_date: date | None = Query(default=None, alias="date", description="Optional date filter for validation data."),
    depth: float | None = Query(default=None, ge=0, description="Optional depth filter in meters."),
    latitude: float | None = Query(default=None, ge=-90, le=90, description="Optional latitude filter."),
    longitude: float | None = Query(default=None, ge=-180, le=180, description="Optional longitude filter."),
    argo_profile_id: str | None = Query(default=None, description="Optional ARGO profile identifier."),
) -> ValidationResponse:
    try:
        if latitude is not None:
            validate_latitude(latitude)
        if longitude is not None:
            validate_longitude(longitude)
        if depth is not None:
            validate_depth(depth)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return get_validation_service(
        selected_date,
        depth,
        latitude,
        longitude,
        argo_profile_id,
    )
