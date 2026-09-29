"""ARGO validation routes.

These expose the independent reference data in the shapes the frontend needs:
the observation-cell list (map markers + profile picker) and the strongest
model-vs-ARGO disagreements (review candidates).
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_argo_source as _get_argo_source
from app.api.deps import get_model as _get_model
from app.data.interfaces import ArgoDataSource
from app.model.interface import OceanEmbedModel
from app.schemas.oceanembed import AnomalyAlertResponse, ArgoFloatResponse
from app.services.argo import get_argo_floats as get_argo_floats_service
from app.services.validation import get_anomaly_alerts as get_anomaly_alerts_service
from app.validation import validate_model_date

router = APIRouter(prefix="/api/argo", tags=["argo"])


def get_argo_model() -> OceanEmbedModel:
    """Route-level dependency so tests can override the model."""
    return _get_model()


def get_argo_reference() -> ArgoDataSource:
    """Route-level dependency so tests can override the ARGO reference."""
    return _get_argo_source()


def get_argo_model() -> OceanEmbedModel:
    """Route-level dependency so tests can override the model."""
    return _get_model()


def get_argo_reference() -> ArgoDataSource:
    """Route-level dependency so tests can override the ARGO reference."""
    return _get_argo_source()


@router.get("/floats", response_model=ArgoFloatResponse, summary="Return ARGO-observed cells for a date")
async def get_argo_floats(
    selected_date: date | None = Query(default=None, alias="date", description="Date to report ARGO cells for."),
    argo: ArgoDataSource = Depends(get_argo_reference),
) -> ArgoFloatResponse:
    if selected_date is not None:
        try:
            validate_model_date(selected_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_argo_floats_service(selected_date, argo=argo)


@router.get("/alerts", response_model=AnomalyAlertResponse, summary="Return the largest model-vs-ARGO disagreements")
async def get_argo_alerts(
    selected_date: date | None = Query(default=None, alias="date", description="Optional date filter."),
    limit: int = Query(default=6, ge=1, le=50, description="Maximum number of alerts to return."),
    model: OceanEmbedModel = Depends(get_argo_model),
    argo: ArgoDataSource = Depends(get_argo_reference),
) -> AnomalyAlertResponse:
    if selected_date is not None:
        try:
            validate_model_date(selected_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_anomaly_alerts_service(selected_date, limit=limit, model=model, argo=argo)
