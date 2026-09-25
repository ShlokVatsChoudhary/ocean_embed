from datetime import date

from fastapi import APIRouter, Query

from app.schemas.oceanembed import ProfileResponse
from app.services.profile import get_profile as get_profile_service

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse, summary="Return a depth profile for a point location and date")
@router.get("/", include_in_schema=False)
async def get_profile(
    latitude: float = Query(..., description="Latitude of the point of interest."),
    longitude: float = Query(..., description="Longitude of the point of interest."),
    selected_date: date = Query(..., alias="date", description="Date for the profile."),
) -> ProfileResponse:
    return get_profile_service(latitude, longitude, selected_date)
