from datetime import date

from app.data.glorys import GlorysDataAccessor
from app.data.interfaces import DataSourceStatus, GlorysDataSource
from app.model.interface import ModelInferenceInput, OceanEmbedModel
from app.schemas.oceanembed import ComparisonResponse


def _extract_temperature_value(payload: object) -> float | None:
    """Extract a scalar temperature from a model or data-source payload."""
    if payload is None:
        return None

    if isinstance(payload, (int, float)):
        return float(payload)

    if isinstance(payload, dict):
        for key in ("temperature", "value", "temp", "oceanembed_temperature", "glorys_temperature"):
            if key in payload and payload[key] is not None:
                return float(payload[key])
        return None

    if hasattr(payload, "temperature"):
        value = getattr(payload, "temperature")
        if value is not None:
            return float(value)

    if hasattr(payload, "value"):
        value = getattr(payload, "value")
        if value is not None:
            return float(value)

    return None


def _extract_point_temperature_from_model(model: OceanEmbedModel, latitude: float, longitude: float, selected_date: date, depth: float) -> float | None:
    """Ask the model for a point temperature using its proper point accessor."""
    return model.point_temperature(
        latitude=latitude,
        longitude=longitude,
        date=selected_date,
        depth=depth,
    )


def _resolve_grid_point(
    model: OceanEmbedModel,
    *,
    latitude: float,
    longitude: float,
    selected_date: date,
) -> dict[str, object]:
    """Ask the model which grid cell a requested coordinate resolves to.

    Grid transparency is nice-to-have, so an implementation that cannot report it degrades to
    empty rather than failing the whole comparison.
    """
    resolver = getattr(model, "resolve_grid_point", None)
    if resolver is None:
        return {}
    try:
        return dict(resolver(latitude=latitude, longitude=longitude, date=selected_date))
    except (NotImplementedError, TypeError, ValueError, KeyError):
        return {}


def _status_value(source: object) -> str:
    status = getattr(source, "status", None)
    if status is None:
        return DataSourceStatus.UNAVAILABLE.value
    return status.value if hasattr(status, "value") else str(status)


def _provenance_value(source: object) -> str:
    provenance = getattr(source, "provenance", None)
    if provenance is None:
        return "GLORYS data is unavailable in this environment."
    return str(provenance)


def get_comparison(
    latitude: float,
    longitude: float,
    selected_date: date,
    depth: float,
    model: OceanEmbedModel | None = None,
    glorys_source: GlorysDataSource | None = None,
) -> ComparisonResponse:
    """Compare a single OceanEmbed point temperature against a GLORYS point temperature."""
    if model is None:
        raise ValueError("Comparison service requires an OceanEmbedModel instance.")
    if glorys_source is None:
        glorys_source = GlorysDataAccessor()

    grid = _resolve_grid_point(
        model,
        latitude=latitude,
        longitude=longitude,
        selected_date=selected_date,
    )
    resolved_latitude = grid.get("grid_latitude", latitude)
    resolved_longitude = grid.get("grid_longitude", longitude)
    if resolved_latitude is None:
        resolved_latitude = latitude
    if resolved_longitude is None:
        resolved_longitude = longitude

    oceanembed_temperature = _extract_point_temperature_from_model(
        model,
        latitude=float(resolved_latitude),
        longitude=float(resolved_longitude),
        selected_date=selected_date,
        depth=depth,
    )

    try:
        glorys_payload = glorys_source.get_point_temperature(
            latitude=float(resolved_latitude),
            longitude=float(resolved_longitude),
            target_date=selected_date,
            depth=depth,
        )
    except (RuntimeError, ValueError, FileNotFoundError):
        glorys_payload = None

    glorys_temperature = _extract_temperature_value(glorys_payload)

    if oceanembed_temperature is None or glorys_temperature is None:
        difference = None
    else:
        difference = oceanembed_temperature - glorys_temperature

    if oceanembed_temperature is None:
        state = "model_unavailable"
        state_message = (
            "OceanEmbed prediction unavailable at this location, depth and date. "
            "No fallback value is substituted."
        )
    elif glorys_temperature is None:
        state = "model_only"
        state_message = (
            "GLORYS reference unavailable at this location, depth and date. "
            "This is a missing reference, not an error."
        )
    else:
        state = "model_and_reference"
        state_message = (
            "OceanEmbed and the GLORYS reference are both available; difference is "
            "OceanEmbed minus GLORYS."
        )

    offset = grid.get("offset_degrees")
    if oceanembed_temperature is not None and isinstance(offset, (int, float)) and offset > 0:
        state_message = (
            f"{state_message} The value is read from the nearest full-depth model cell at "
            f"{grid.get('grid_latitude')}N, {grid.get('grid_longitude')}E, "
            f"{offset} degrees from the requested cell, because the requested cell has no "
            f"complete 0-1000 m column."
        )

    return ComparisonResponse(
        latitude=latitude,
        longitude=longitude,
        date=selected_date,
        depth=depth,
        oceanembed_temperature=oceanembed_temperature,
        glorys_temperature=glorys_temperature,
        difference=difference,
        glorys_status=_status_value(glorys_source),
        glorys_provenance=_provenance_value(glorys_source),
        unit="degC",
        requested_latitude=latitude,
        requested_longitude=longitude,
        grid_latitude=grid.get("grid_latitude"),
        grid_longitude=grid.get("grid_longitude"),
        nearest_grid_latitude=grid.get("nearest_grid_latitude"),
        nearest_grid_longitude=grid.get("nearest_grid_longitude"),
        offset_degrees=grid.get("offset_degrees"),
        state=state,
        state_message=state_message,
    )
