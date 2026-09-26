from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.data.glorys import GlorysDataAccessor
from app.data.interfaces import GlorysDataSource
from app.model.interface import OceanEmbedModel, PlaceholderOceanEmbedModel
from app.schemas.oceanembed import ComparisonResponse
from app.services.comparison import get_comparison as get_comparison_service
from app.validation import validate_latitude, validate_longitude, validate_model_date, validate_standard_depth

router = APIRouter(prefix="/api/comparison", tags=["comparison"])


def get_comparison_model() -> OceanEmbedModel:
    """Return the configured model implementation for comparison requests."""
    return PlaceholderOceanEmbedModel()


def get_comparison_glorys_source() -> GlorysDataSource:
    """Return the configured GLORYS reference source for comparison requests."""
    return GlorysDataAccessor()


@router.get("", response_model=ComparisonResponse, summary="Compare model output with GLORYS reference at a location")
@router.get("/", include_in_schema=False)
async def get_comparison(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude of the comparison point."),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude of the comparison point."),
    selected_date: date = Query(..., alias="date", description="Reference date for the comparison."),
    depth: float = Query(..., ge=0, description="Depth in meters."),
    model: OceanEmbedModel = Depends(get_comparison_model),
    glorys_source: GlorysDataSource = Depends(get_comparison_glorys_source),
) -> ComparisonResponse:
    try:
        validate_latitude(latitude)
        validate_longitude(longitude)
        validate_model_date(selected_date)
        validate_standard_depth(depth)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return get_comparison_service(latitude, longitude, selected_date, depth, model=model, glorys_source=glorys_source)
