from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_model as _get_model
from app.model.interface import OceanEmbedModel
from app.schemas.oceanembed import HazardFieldResponse, HazardSummaryResponse
from app.services.hazard import get_hazard_field as get_hazard_field_service
from app.services.hazard import get_hazard_summary as get_hazard_summary_service
from app.science.hazard import VARIABLE_INFO
from app.validation import validate_model_date

router = APIRouter(prefix="/api/hazard", tags=["hazard"])

#: Variables offered by the field endpoint. ``tchp_category`` is derived and only
#: meaningful in its integer form, so it is excluded from the free-form selector.
FIELD_VARIABLES = tuple(sorted(VARIABLE_INFO))


def get_hazard_model() -> OceanEmbedModel:
    """Route-level dependency so tests can override the model without touching the cache."""
    return _get_model()


@router.get("/variables", summary="List the available hazard diagnostics")
async def list_hazard_variables() -> list[dict[str, str]]:
    return [{"variable": key, "label": value[0], "unit": value[1]} for key, value in sorted(VARIABLE_INFO.items())]


@router.get("/summary", response_model=HazardSummaryResponse, summary="Cyclone-relevant diagnostics for one day")
async def get_hazard_summary(
    selected_date: date = Query(..., alias="date", description="Date to summarise."),
    model: OceanEmbedModel = Depends(get_hazard_model),
) -> HazardSummaryResponse:
    try:
        validate_model_date(selected_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_hazard_summary_service(selected_date, model=model)


@router.get("", response_model=HazardFieldResponse, summary="Return one hazard diagnostic as a grid")
@router.get("/", include_in_schema=False)
async def get_hazard_field(
    selected_date: date = Query(..., alias="date", description="Date for the diagnostic."),
    variable: str = Query(default="tchp", description=f"One of: {', '.join(FIELD_VARIABLES)}"),
    model: OceanEmbedModel = Depends(get_hazard_model),
) -> HazardFieldResponse:
    try:
        validate_model_date(selected_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return get_hazard_field_service(selected_date, variable, model=model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
