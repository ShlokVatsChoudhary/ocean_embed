from datetime import date

from app.schemas.oceanembed import ComparisonResponse


def get_comparison(latitude: float, longitude: float, selected_date: date, depth: float) -> ComparisonResponse:
    """Return a deterministic mock comparison payload for development.

    This is not a real OceanEmbed reconstruction, GLORYS field, or scientific difference
    calculation; it only defines the expected response contract.
    """
    return ComparisonResponse(
        latitude=latitude,
        longitude=longitude,
        date=selected_date,
        depth=depth,
        oceanembed_temperature=None,
        glorys_temperature=None,
        difference=None,
        unit="degC",
    )
