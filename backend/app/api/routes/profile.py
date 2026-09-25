from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.schemas.oceanembed import ProfileResponse
from app.services.profile import get_profile as get_profile_service
from app.validation import validate_depth, validate_latitude, validate_longitude

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse, summary="Return a depth profile for a point location and date")
@router.get("/", include_in_schema=False)
async def get_profile(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude of the point of interest."),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude of the point of interest."),
    selected_date: date = Query(..., alias="date", description="Date for the profile."),
    depth: float | None = Query(default=None, ge=0, description="Optional profile depth filter in meters."),
) -> ProfileResponse:
    try:
        validate_latitude(latitude)
        validate_longitude(longitude)
        if depth is not None:
            validate_depth(depth)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return get_profile_service(latitude, longitude, selected_date)
