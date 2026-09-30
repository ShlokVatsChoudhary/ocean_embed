"""Reference (GLORYS) temperature fields.

The web UI shows the model beside the reference field it was trained against, so
that difference has to be served rather than invented client-side.

This is explicitly NOT a validation source. The bundled ``Y_2020.npy`` is the
model's own training target for these dates, so any agreement here is in-sample
and optimistic by construction. Independent evidence comes from ARGO via
``app/services/validation.py``, and the response is labelled accordingly.
"""

from __future__ import annotations

import math
from datetime import date

from app.core.constants import MODEL_AVAILABLE_DATES, STANDARD_DEPTHS
from app.data.interfaces import GlorysDataSource
from app.schemas.oceanembed import TemperatureFieldMetadata, TemperatureResponse


def _finite_or_none(rows: object) -> list[list[float | None]]:
    """Replace non-finite values with None.

    NaN serialises to the bare token ``NaN``, which is not valid JSON, so a browser
    that calls ``JSON.parse`` on it fails outright. Land cells must arrive as null.
    """
    if not isinstance(rows, list):
        return []
    cleaned: list[list[float | None]] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        cleaned.append([
            None if value is None or not math.isfinite(float(value)) else float(value)
            for value in row
        ])
    return cleaned


def get_reference_temperature(
    selected_date: date,
    depth: float,
    latitude_min: float | None = None,
    latitude_max: float | None = None,
    longitude_min: float | None = None,
    longitude_max: float | None = None,
    glorys: GlorysDataSource | None = None,
) -> TemperatureResponse:
    """Return the reference temperature field for a supported date and depth."""
    if glorys is None:
        raise ValueError("Reference service requires a GlorysDataSource instance.")

    if depth not in STANDARD_DEPTHS:
        valid_depths = ", ".join(str(value) for value in STANDARD_DEPTHS)
        raise ValueError(f"Requested depth {depth} is not one of the standard profile depths: {valid_depths}.")

    if selected_date not in MODEL_AVAILABLE_DATES:
        raise ValueError(
            f"Data unavailable for {selected_date}. Available model dates: "
            f"{MODEL_AVAILABLE_DATES[0]} to {MODEL_AVAILABLE_DATES[-1]}."
        )

    payload = glorys.get_temperature_field(
        target_date=selected_date,
        depth=depth,
        latitude_min=latitude_min,
        latitude_max=latitude_max,
        longitude_min=longitude_min,
        longitude_max=longitude_max,
    )

    lats = payload.get("lats") or []
    lons = payload.get("lons") or []
    bounds = {
        "latitude_min": float(lats[0]) if lats else latitude_min,
        "latitude_max": float(lats[-1]) if lats else latitude_max,
        "longitude_min": float(lons[0]) if lons else longitude_min,
        "longitude_max": float(lons[-1]) if lons else longitude_max,
    }

    try:
        status = glorys.status.value
    except AttributeError:  # pragma: no cover - defensive
        status = "unknown"

    return TemperatureResponse(
        metadata=TemperatureFieldMetadata(
            date=selected_date,
            depth=depth,
            variable="temperature",
            units="degC",
            bounds=bounds,
            source=f"glorys_reference:{status}",
        ),
        values=_finite_or_none(payload.get("values")),
    )
