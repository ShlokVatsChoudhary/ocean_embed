from datetime import date

from app.core.constants import STANDARD_DEPTHS
from app.model.interface import ModelInferenceInput, OceanEmbedModel, PlaceholderOceanEmbedModel
from app.schemas.oceanembed import ProfilePoint, ProfileResponse
from app.validation import validate_model_date, validate_standard_depth


def get_profile(
    latitude: float,
    longitude: float,
    selected_date: date,
    depth: float | None = None,
    model: OceanEmbedModel | None = None,
) -> ProfileResponse:
    """Return a profile built from the model's raw 15-depth output."""
    if model is None:
        model = PlaceholderOceanEmbedModel()

    validate_model_date(selected_date)
    if depth is not None:
        validate_standard_depth(depth)

    request = ModelInferenceInput(
        date=selected_date,
        latitude=latitude,
        longitude=longitude,
        depth=depth,
    )
    prediction = model.infer_profile(request)

    if len(prediction.temperatures) != len(STANDARD_DEPTHS):
        raise ValueError(
            f"Model profile inference must return exactly {len(STANDARD_DEPTHS)} temperatures, "
            f"got {len(prediction.temperatures)}."
        )

    points = [
        ProfilePoint(depth=standard_depth, temperature=temperature, units="degC")
        for standard_depth, temperature in zip(STANDARD_DEPTHS, prediction.temperatures)
    ]

    if depth is not None:
        selected_depth = depth
        profile = [
            point for point in points if point.depth == selected_depth
        ]
    else:
        profile = points

    return ProfileResponse(
        latitude=latitude,
        longitude=longitude,
        date=selected_date,
        profile=profile,
    )
