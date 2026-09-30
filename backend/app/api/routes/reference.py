from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_glorys_source
from app.data.interfaces import GlorysDataSource
from app.schemas.oceanembed import TemperatureResponse
from app.services.reference import get_reference_temperature as get_reference_service
from app.validation import (
    validate_geographic_bounds,
    validate_latitude,
    validate_longitude,
    validate_model_date,
    validate_standard_depth,
)

router = APIRouter(prefix="/api/reference", tags=["reference"])


def get_reference_source() -> GlorysDataSource:
    """Route-level dependency so tests can override the reference source."""
    return get_glorys_source()


@router.get(
    "",
    response_model=TemperatureResponse,
    summary="Return the reference (GLORYS) temperature field the model was trained against",
)
@router.get("/", include_in_schema=False)
async def get_reference(
    selected_date: date = Query(..., alias="date", description="Date for the requested reference field."),
    depth: float = Query(..., ge=0, description="Depth level in meters."),
    latitude_min: float | None = Query(default=None, ge=-90, le=90),
    latitude_max: float | None = Query(default=None, ge=-90, le=90),
    longitude_min: float | None = Query(default=None, ge=-180, le=180),
    longitude_max: float | None = Query(default=None, ge=-180, le=180),
    glorys: GlorysDataSource = Depends(get_reference_source),
) -> TemperatureResponse:
    try:
        validate_model_date(selected_date)
        validate_standard_depth(depth)
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

    try:
        return get_reference_service(
            selected_date,
            depth,
            latitude_min=latitude_min,
            latitude_max=latitude_max,
            longitude_min=longitude_min,
            longitude_max=longitude_max,
            glorys=glorys,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
