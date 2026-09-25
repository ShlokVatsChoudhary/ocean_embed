from datetime import date

from app.schemas.oceanembed import ValidationMetrics, ValidationResponse


def get_validation(
    selected_date: date | None = None,
    depth: float | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    argo_profile_id: str | None = None,
) -> ValidationResponse:
    """Return a deterministic mock validation payload for development.

    The values intentionally remain unset because no real ARGO or OceanEmbed validation
    data is being loaded yet. This provides a stable API contract for future integration.
    """
    return ValidationResponse(
        dataset="ARGO",
        metrics=ValidationMetrics(
            rmse=None,
            mae=None,
            bias=None,
            n_observations=None,
        ),
        observations=[],
    )
