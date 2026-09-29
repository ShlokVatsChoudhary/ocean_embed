from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_argo_source as _get_argo_source
from app.api.deps import get_model as _get_model
from app.data.interfaces import ArgoDataSource
from app.model.interface import OceanEmbedModel
from app.schemas.oceanembed import ValidationResponse
from app.services.validation import get_validation as get_validation_service
from app.validation import validate_depth, validate_latitude, validate_longitude

router = APIRouter(prefix="/api/validation", tags=["validation"])


def get_validation_model() -> OceanEmbedModel:
    """Route-level dependency so tests can override the model."""
    return _get_model()


def get_validation_argo() -> ArgoDataSource:
    """Route-level dependency so tests can override the ARGO reference."""
    return _get_argo_source()


@router.get("", response_model=ValidationResponse, summary="Return ARGO validation metrics and observation comparisons")
@router.get("/", include_in_schema=False)
async def get_validation(
    selected_date: date | None = Query(default=None, alias="date", description="Optional date filter for validation data."),
    depth: float | None = Query(default=None, ge=0, description="Optional depth filter in meters."),
    latitude: float | None = Query(default=None, ge=-90, le=90, description="Optional latitude filter."),
    longitude: float | None = Query(default=None, ge=-180, le=180, description="Optional longitude filter."),
    argo_profile_id: str | None = Query(default=None, description="Optional ARGO profile identifier."),
    model: OceanEmbedModel = Depends(get_validation_model),
    argo: ArgoDataSource = Depends(get_validation_argo),
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
        model=model,
        argo=argo,
    )
