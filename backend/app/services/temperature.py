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
from app.model.interface import ModelInferenceInput, OceanEmbedModel, PlaceholderOceanEmbedModel
from app.schemas.oceanembed import TemperatureFieldMetadata, TemperatureResponse


def _nearest_grid_index(value: float, minimum: float, maximum: float, resolution: float, length: int) -> int:
    if value <= minimum:
        return 0
    if value >= maximum:
        return max(length - 1, 0)
    return min(max(int(round((maximum - value) / resolution)), 0), length - 1)


def _subset_temperature_values(values: list[list[float | None]], latitude_min, latitude_max, longitude_min, longitude_max):
    if not values:
        return values

    start_lat = _nearest_grid_index(latitude_max if latitude_max is not None else MODEL_LATITUDE_MAX, MODEL_LATITUDE_MIN, MODEL_LATITUDE_MAX, MODEL_LATITUDE_RESOLUTION, len(values))
    end_lat = _nearest_grid_index(latitude_min if latitude_min is not None else MODEL_LATITUDE_MIN, MODEL_LATITUDE_MIN, MODEL_LATITUDE_MAX, MODEL_LATITUDE_RESOLUTION, len(values))
    lat_start = min(start_lat, end_lat)
    lat_end = max(start_lat, end_lat)

    start_lon = _nearest_grid_index(longitude_min if longitude_min is not None else MODEL_LONGITUDE_MIN, MODEL_LONGITUDE_MIN, MODEL_LONGITUDE_MAX, MODEL_LONGITUDE_RESOLUTION, len(values[0]))
    end_lon = _nearest_grid_index(longitude_max if longitude_max is not None else MODEL_LONGITUDE_MAX, MODEL_LONGITUDE_MIN, MODEL_LONGITUDE_MAX, MODEL_LONGITUDE_RESOLUTION, len(values[0]))
    lon_start = min(start_lon, end_lon)
    lon_end = max(start_lon, end_lon)

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
        model = PlaceholderOceanEmbedModel()

    if depth not in STANDARD_DEPTHS:
        valid_depths = ", ".join(str(value) for value in STANDARD_DEPTHS)
        raise ValueError(f"Requested depth {depth} is not one of the standard profile depths: {valid_depths}.")

    if selected_date not in MODEL_AVAILABLE_DATES:
        raise ValueError(f"Data unavailable for {selected_date}. Available model dates: {MODEL_AVAILABLE_DATES[0]} to {MODEL_AVAILABLE_DATES[-1]}.")

    request = ModelInferenceInput(
        date=selected_date,
        latitude_min=latitude_min,
        latitude_max=latitude_max,
        longitude_min=longitude_min,
        longitude_max=longitude_max,
        depth=depth,
    )

    try:
        prediction = model.infer_temperature_field(request)
        values = prediction.values
    except NotImplementedError:
        values = [[None for _ in range(MODEL_GRID_COLS)] for _ in range(MODEL_GRID_ROWS)]

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
