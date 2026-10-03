from datetime import date

from app.core.constants import STANDARD_DEPTHS
from app.data.interfaces import ArgoDataSource, GlorysDataSource
from app.model.interface import ModelInferenceInput, OceanEmbedModel
from app.schemas.oceanembed import ProfilePoint, ProfileResponse
from app.validation import validate_model_date, validate_standard_depth


def _resolved_point(model: OceanEmbedModel, latitude: float, longitude: float, selected_date: date) -> tuple[float, float]:
    resolver = getattr(model, "resolve_grid_point", None)
    if resolver is None:
        return latitude, longitude
    try:
        resolved = dict(resolver(latitude=latitude, longitude=longitude, date=selected_date))
    except (NotImplementedError, TypeError, ValueError, KeyError):
        return latitude, longitude
    resolved_latitude = resolved.get("grid_latitude", latitude)
    resolved_longitude = resolved.get("grid_longitude", longitude)
    return float(resolved_latitude if resolved_latitude is not None else latitude), float(
        resolved_longitude if resolved_longitude is not None else longitude
    )


def _as_profile_points(temperatures: list[float | None]) -> list[ProfilePoint]:
    return [
        ProfilePoint(depth=standard_depth, temperature=temperature, units="degC")
        for standard_depth, temperature in zip(STANDARD_DEPTHS, temperatures)
    ]


def _glorys_profile_for_cell(
    glorys_source: GlorysDataSource | None,
    *,
    latitude: float,
    longitude: float,
    selected_date: date,
) -> list[ProfilePoint]:
    if glorys_source is None:
        return []

    series: list[ProfilePoint] = []
    for depth in STANDARD_DEPTHS:
        try:
            payload = glorys_source.get_point_temperature(
                latitude=latitude,
                longitude=longitude,
                target_date=selected_date,
                depth=depth,
            )
        except (RuntimeError, ValueError, FileNotFoundError):
            payload = {"temperature": None}

        temperature = payload.get("temperature") if isinstance(payload, dict) else None
        if temperature is None:
            series.append(ProfilePoint(depth=depth, temperature=None, units="degC"))
        else:
            series.append(ProfilePoint(depth=depth, temperature=float(temperature), units="degC"))
    return series


def _argo_profile_for_cell(
    argo_source: ArgoDataSource | None,
    *,
    latitude: float,
    longitude: float,
    selected_date: date,
) -> tuple[list[ProfilePoint], date | None, int | None]:
    if argo_source is None or not argo_source.is_available():
        return [], None, None

    matched = argo_source.matched_time(selected_date)
    argo_date, offset = matched if matched else (None, None)
    observations = argo_source.get_validation_observations(date=selected_date, latitude=latitude, longitude=longitude)
    by_depth: dict[float, float] = {}
    for observation in observations:
        depth = float(observation.get("depth", -1.0))
        if depth in by_depth:
            continue
        value = observation.get("observed_temperature")
        if value is not None:
            by_depth[depth] = float(value)

    series = [
        ProfilePoint(depth=depth, temperature=by_depth.get(float(depth)), units="degC")
        for depth in STANDARD_DEPTHS
    ]
    return series, argo_date, offset


def get_profile(
    latitude: float,
    longitude: float,
    selected_date: date,
    depth: float | None = None,
    model: OceanEmbedModel | None = None,
    glorys_source: GlorysDataSource | None = None,
    argo_source: ArgoDataSource | None = None,
) -> ProfileResponse:
    """Return a profile built from the model's raw 15-depth output."""
    if model is None:
        raise ValueError("Profile service requires an OceanEmbedModel instance.")

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

    points = _as_profile_points(prediction.temperatures)
    if depth is not None:
        selected_depth = depth
        profile = [point for point in points if point.depth == selected_depth]
    else:
        profile = points

    resolved_latitude, resolved_longitude = _resolved_point(model, latitude, longitude, selected_date)
    glorys_profile = _glorys_profile_for_cell(
        glorys_source,
        latitude=resolved_latitude,
        longitude=resolved_longitude,
        selected_date=selected_date,
    )
    argo_profile, argo_date, time_offset_days = _argo_profile_for_cell(
        argo_source,
        latitude=resolved_latitude,
        longitude=resolved_longitude,
        selected_date=selected_date,
    )

    return ProfileResponse(
        latitude=latitude,
        longitude=longitude,
        date=selected_date,
        profile=profile,
        requested_latitude=latitude,
        requested_longitude=longitude,
        grid_latitude=resolved_latitude,
        grid_longitude=resolved_longitude,
        glorys_profile=glorys_profile,
        argo_profile=argo_profile,
        argo_date=argo_date,
        time_offset_days=time_offset_days,
        provenance=(
            f"OceanEmbed profile at the resolved grid cell ({resolved_latitude:.2f}, {resolved_longitude:.2f}); "
            "GLORYS is reference/training-target data and ARGO is observational validation."
        ),
    )
