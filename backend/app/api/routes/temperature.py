from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.schemas.oceanembed import TemperatureResponse
from app.services.temperature import get_temperature as get_temperature_service
from app.validation import validate_depth, validate_geographic_bounds, validate_latitude, validate_longitude

router = APIRouter(prefix="/api/temperature", tags=["temperature"])


@router.get("", response_model=TemperatureResponse, summary="Return a temperature field for a requested date and depth")
@router.get("/", include_in_schema=False)
async def get_temperature(
    selected_date: date = Query(..., alias="date", description="Date for the requested temperature field."),
    depth: float = Query(..., ge=0, description="Depth level in meters."),
    latitude_min: float | None = Query(default=None, ge=-90, le=90, description="Optional minimum latitude for subset extraction."),
    latitude_max: float | None = Query(default=None, ge=-90, le=90, description="Optional maximum latitude for subset extraction."),
    longitude_min: float | None = Query(default=None, ge=-180, le=180, description="Optional minimum longitude for subset extraction."),
    longitude_max: float | None = Query(default=None, ge=-180, le=180, description="Optional maximum longitude for subset extraction."),
) -> TemperatureResponse:
    try:
        validate_depth(depth)
        validate_geographic_bounds(latitude_min, latitude_max, "latitude_min", "latitude_max")
        validate_geographic_bounds(longitude_min, longitude_max, "longitude_min", "longitude_max")
        if latitude_min is not None:
            validate_latitude(latitude_min, "latitude_min")
        if latitude_max is not None:
            validate_latitude(latitude_max, "latitude_max")
        if longitude_min is not None:
            validate_longitude(longitude_min, "longitude_min")
        if longitude_max is not None:
            validate_longitude(longitude_max, "longitude_max")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return get_temperature_service(
        selected_date,
        depth,
        latitude_min=latitude_min,
        latitude_max=latitude_max,
        longitude_min=longitude_min,
        longitude_max=longitude_max,
    )
