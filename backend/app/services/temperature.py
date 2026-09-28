from datetime import date

from app.core.constants import (
    MODEL_AVAILABLE_DATES,
    MODEL_GRID_COLS,
    MODEL_GRID_ROWS,
    MODEL_LATITUDE_MAX,
    MODEL_LATITUDE_MIN,
    MODEL_LATITUDE_RESOLUTION,
    MODEL_LONGITUDE_MAX,
    MODEL_LONGITUDE_MIN,
    MODEL_LONGITUDE_RESOLUTION,
    STANDARD_DEPTHS,
)
from app.model.interface import ModelInferenceInput, OceanEmbedModel
from app.schemas.oceanembed import TemperatureFieldMetadata, TemperatureResponse


def _nearest_grid_index(value: float, minimum: float, maximum: float, resolution: float, length: int) -> int:
    if value <= minimum:
        return 0
    if value >= maximum:
        return max(length - 1, 0)
    return min(max(int(round((value - minimum) / resolution)), 0), max(length - 1, 0))


def _subset_temperature_values(values: list[list[float | None]], latitude_min, latitude_max, longitude_min, longitude_max):
    if not values:
        return values

    lat_count = len(values)
    lon_count = len(values[0]) if values and values[0] else 0
    lat_min = latitude_min if latitude_min is not None else MODEL_LATITUDE_MIN
    lat_max = latitude_max if latitude_max is not None else MODEL_LATITUDE_MAX
    lon_min = longitude_min if longitude_min is not None else MODEL_LONGITUDE_MIN
    lon_max = longitude_max if longitude_max is not None else MODEL_LONGITUDE_MAX

    row_start = _nearest_grid_index(lat_max, MODEL_LATITUDE_MIN, MODEL_LATITUDE_MAX, MODEL_LATITUDE_RESOLUTION, lat_count)
    row_end = _nearest_grid_index(lat_min, MODEL_LATITUDE_MIN, MODEL_LATITUDE_MAX, MODEL_LATITUDE_RESOLUTION, lat_count)
    lat_start = min(row_start, row_end)
    lat_end = max(row_start, row_end)

    col_start = _nearest_grid_index(lon_min, MODEL_LONGITUDE_MIN, MODEL_LONGITUDE_MAX, MODEL_LONGITUDE_RESOLUTION, lon_count)
    col_end = _nearest_grid_index(lon_max, MODEL_LONGITUDE_MIN, MODEL_LONGITUDE_MAX, MODEL_LONGITUDE_RESOLUTION, lon_count)
    lon_start = min(col_start, col_end)
    lon_end = max(col_start, col_end)

    return [row[lon_start : lon_end + 1] for row in values[lat_start : lat_end + 1]]


def get_temperature(
    selected_date: date,
    depth: float,
    latitude_min: float | None = None,
    latitude_max: float | None = None,
    longitude_min: float | None = None,
    longitude_max: float | None = None,
    model: OceanEmbedModel | None = None,
) -> TemperatureResponse:
    """Return a temperature field for a supported date and standard depth."""
    if model is None:
        raise ValueError("Temperature service requires an OceanEmbedModel instance.")

    if depth not in STANDARD_DEPTHS:
        valid_depths = ", ".join(str(value) for value in STANDARD_DEPTHS)
        raise ValueError(f"Requested depth {depth} is not one of the standard profile depths: {valid_depths}.")

    if selected_date not in MODEL_AVAILABLE_DATES:
        raise ValueError(f"Data unavailable for {selected_date}. Available model dates: {MODEL_AVAILABLE_DATES[0]} to {MODEL_AVAILABLE_DATES[-1]}.")

    request = ModelInferenceInput(
        date=selected_date,
        depth=depth,
        latitude_min=latitude_min,
        latitude_max=latitude_max,
        longitude_min=longitude_min,
        longitude_max=longitude_max,
    )
    prediction = model.infer_temperature_field(request)
    values = prediction.values

    if latitude_min is not None or latitude_max is not None or longitude_min is not None or longitude_max is not None:
        values = _subset_temperature_values(values, latitude_min, latitude_max, longitude_min, longitude_max)

    bounds = {
        "latitude_min": latitude_min if latitude_min is not None else MODEL_LATITUDE_MIN,
        "latitude_max": latitude_max if latitude_max is not None else MODEL_LATITUDE_MAX,
        "longitude_min": longitude_min if longitude_min is not None else MODEL_LONGITUDE_MIN,
        "longitude_max": longitude_max if longitude_max is not None else MODEL_LONGITUDE_MAX,
    }

    return TemperatureResponse(
        metadata=TemperatureFieldMetadata(
            date=selected_date,
            depth=depth,
            variable="temperature",
            units="degC",
            bounds=bounds,
        ),
        values=values,
    )
