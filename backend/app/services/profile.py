from datetime import date

from app.core.constants import STANDARD_DEPTHS
from app.model.interface import ModelInferenceInput, OceanEmbedModel, PlaceholderOceanEmbedModel
from app.schemas.oceanembed import ProfilePoint, ProfileResponse


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

    if depth is not None and depth not in STANDARD_DEPTHS:
        raise ValueError(
            f"Requested depth {depth} is not one of the standard profile depths: {STANDARD_DEPTHS}."
        )

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
