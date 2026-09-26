from datetime import date

from app.data.glorys import GlorysDataAccessor
from app.data.interfaces import GlorysDataSource
from app.model.interface import ModelInferenceInput, OceanEmbedModel, PlaceholderOceanEmbedModel
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
    """Ask the model for a point temperature and extract the scalar value from its response."""
    request = ModelInferenceInput(
        date=selected_date,
        latitude=latitude,
        longitude=longitude,
        depth=depth,
    )
    prediction = model.infer_temperature_field(request)

    if not prediction.values:
        return None

    flattened: list[float | None] = []
    for row in prediction.values:
        if isinstance(row, list):
            flattened.extend(row)
        else:
            flattened.append(row)

    for value in flattened:
        if value is not None:
            return float(value)

    return None


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
        model = PlaceholderOceanEmbedModel()
    if glorys_source is None:
        glorys_source = GlorysDataAccessor()

    try:
        oceanembed_temperature = _extract_point_temperature_from_model(
            model,
            latitude=latitude,
            longitude=longitude,
            selected_date=selected_date,
            depth=depth,
        )
    except NotImplementedError:
        oceanembed_temperature = None

    try:
        glorys_payload = glorys_source.get_point_temperature(
            latitude=latitude,
            longitude=longitude,
            target_date=selected_date,
            depth=depth,
        )
        glorys_temperature = _extract_temperature_value(glorys_payload)
    except NotImplementedError:
        glorys_temperature = None

    if oceanembed_temperature is None or glorys_temperature is None:
        difference = None
    else:
        difference = oceanembed_temperature - glorys_temperature

    return ComparisonResponse(
        latitude=latitude,
        longitude=longitude,
        date=selected_date,
        depth=depth,
        oceanembed_temperature=oceanembed_temperature,
        glorys_temperature=glorys_temperature,
        difference=difference,
        unit="degC",
    )
