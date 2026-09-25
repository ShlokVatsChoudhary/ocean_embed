from datetime import date

from app.schemas.oceanembed import ProfilePoint, ProfileResponse


def get_profile(latitude: float, longitude: float, selected_date: date) -> ProfileResponse:
    """Return a deterministic mock profile shape for development.

    The profile contains placeholder depth entries with null temperatures; it is not a
    real OceanEmbed reconstruction or ARGO profile.
    """
    mock_depths = [0.0, 10.0, 25.0, 50.0, 100.0]
    profile = [
        ProfilePoint(depth=depth, temperature=None, units="degC") for depth in mock_depths
    ]

    return ProfileResponse(
        latitude=latitude,
        longitude=longitude,
        date=selected_date,
        profile=profile,
    )
