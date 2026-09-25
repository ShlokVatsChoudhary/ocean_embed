from datetime import date

from fastapi import APIRouter, Query

from app.schemas.oceanembed import TemperatureResponse
from app.services.temperature import get_temperature as get_temperature_service

router = APIRouter(prefix="/api/temperature", tags=["temperature"])


@router.get("", response_model=TemperatureResponse, summary="Return a temperature field for a requested date and depth")
@router.get("/", include_in_schema=False)
async def get_temperature(
    selected_date: date = Query(..., alias="date", description="Date for the requested temperature field."),
    depth: float = Query(..., description="Depth level in meters."),
    latitude_min: float | None = Query(default=None, description="Optional minimum latitude for subset extraction."),
    latitude_max: float | None = Query(default=None, description="Optional maximum latitude for subset extraction."),
    longitude_min: float | None = Query(default=None, description="Optional minimum longitude for subset extraction."),
    longitude_max: float | None = Query(default=None, description="Optional maximum longitude for subset extraction."),
) -> TemperatureResponse:
    return get_temperature_service(
        selected_date,
        depth,
        latitude_min=latitude_min,
        latitude_max=latitude_max,
        longitude_min=longitude_min,
        longitude_max=longitude_max,
    )
