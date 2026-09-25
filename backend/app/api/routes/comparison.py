from datetime import date

from fastapi import APIRouter, Query

from app.schemas.oceanembed import ComparisonResponse
from app.services.comparison import get_comparison as get_comparison_service

router = APIRouter(prefix="/api/comparison", tags=["comparison"])


@router.get("", response_model=ComparisonResponse, summary="Compare model output with GLORYS reference at a location")
@router.get("/", include_in_schema=False)
async def get_comparison(
    latitude: float = Query(..., description="Latitude of the comparison point."),
    longitude: float = Query(..., description="Longitude of the comparison point."),
    selected_date: date = Query(..., alias="date", description="Reference date for the comparison."),
    depth: float = Query(..., description="Depth in meters."),
) -> ComparisonResponse:
    return get_comparison_service(latitude, longitude, selected_date, depth)
