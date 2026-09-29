from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.data.interfaces import GlorysDataSource
from app.model.interface import OceanEmbedModel
from app.schemas.oceanembed import ComparisonResponse
from app.services.comparison import get_comparison as get_comparison_service
from app.validation import validate_latitude, validate_longitude, validate_model_date, validate_standard_depth

router = APIRouter(prefix="/api/comparison", tags=["comparison"])

from app.api.deps import get_glorys_source as _get_glorys_source
from app.api.deps import get_model as _get_model


def get_comparison_model() -> OceanEmbedModel:
    """Route-level dependency so tests can override the model without touching the cache."""
    return _get_model()


def get_comparison_glorys_source() -> GlorysDataSource:
    """Route-level dependency so tests can override the reference source."""
    return _get_glorys_source()


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
