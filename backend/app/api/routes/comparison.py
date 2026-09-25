from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.schemas.oceanembed import ComparisonResponse
from app.services.comparison import get_comparison as get_comparison_service
from app.validation import validate_depth, validate_latitude, validate_longitude

router = APIRouter(prefix="/api/comparison", tags=["comparison"])


@router.get("", response_model=ComparisonResponse, summary="Compare model output with GLORYS reference at a location")
@router.get("/", include_in_schema=False)
async def get_comparison(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude of the comparison point."),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude of the comparison point."),
    selected_date: date = Query(..., alias="date", description="Reference date for the comparison."),
    depth: float = Query(..., ge=0, description="Depth in meters."),
) -> ComparisonResponse:
    try:
        validate_latitude(latitude)
        validate_longitude(longitude)
        validate_depth(depth)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return get_comparison_service(latitude, longitude, selected_date, depth)
