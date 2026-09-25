from datetime import date

from app.schemas.oceanembed import TemperatureFieldMetadata, TemperatureResponse


def get_temperature(
    selected_date: date,
    depth: float,
    latitude_min: float | None = None,
    latitude_max: float | None = None,
    longitude_min: float | None = None,
    longitude_max: float | None = None,
) -> TemperatureResponse:
    """Return a deterministic mock temperature field shape for API development.

    The returned grid is intentionally empty/nullable and should be replaced with real
    OceanEmbed model output when the model/service layer is implemented.
    """
    return TemperatureResponse(
        metadata=TemperatureFieldMetadata(
            date=selected_date,
            depth=depth,
            variable="temperature",
            units="degC",
            bounds={
                "latitude_min": latitude_min,
                "latitude_max": latitude_max,
                "longitude_min": longitude_min,
                "longitude_max": longitude_max,
            },
        ),
        values=[[None, None], [None, None]],
    )
