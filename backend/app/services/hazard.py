"""Ocean-hazard diagnostics service.

This is the disaster-management layer: it turns the reconstructed temperature
field into the quantities a cyclone warning centre actually uses. The raw
temperature field is an input to these, not the deliverable.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from app.core.constants import STANDARD_DEPTHS
from app.model.interface import OceanEmbedModel
from app.schemas.oceanembed import HazardFieldResponse, HazardSummaryItem, HazardSummaryResponse
from app.science.hazard import (
    CATEGORY_BREAKS,
    CATEGORY_LABELS,
    MIN_VALID_DEPTH,
    VARIABLE_INFO,
    hazard_fields,
)

MIN_LATITUDE, MAX_LATITUDE = 5.0, 30.0
MIN_LONGITUDE, MAX_LONGITUDE = 45.0, 105.0

PROVENANCE = (
    "Derived from the OceanEmbed subsurface temperature reconstruction. TCHP and D26 follow "
    "the Leipper & Volgenau (1972) 26 \u00b0C convention; OHC is integrated to 300 m relative to "
    "0 \u00b0C; MLD uses a 0.2 \u00b0C criterion; thermocline depth is the maximum vertical gradient."
)

CAVEAT = (
    "These are diagnostics of the model reconstruction, not an operational hazard forecast. "
    "They inherit the model's error, which peaks in the thermocline, so treat absolute TCHP "
    "values as indicative. The underlying temperature field is validated against independent "
    "ARGO data, and the validated window overlaps the training period, so this is an optimistic "
    "upper bound on skill. Columns shallower than "
    f"{MIN_VALID_DEPTH:.0f} m are reported as no-value rather than as a low TCHP, because a "
    "truncated profile would otherwise be read as low cyclone risk."
)

_SUMMARY_VARIABLES = ("tchp", "d26", "ohc", "mld", "thermocline_depth")


def _field_list(array: np.ndarray) -> list[list[float | None]]:
    return [
        [None if not np.isfinite(value) else float(value) for value in row]
        for row in np.asarray(array, dtype="float64").tolist()
    ]


def _stats(array: np.ndarray) -> dict[str, float | int | None]:
    values = np.asarray(array, dtype="float64")
    finite = values[np.isfinite(values)]
    total = int(values.size)
    if finite.size == 0:
        return {
            "minimum": None,
            "median": None,
            "maximum": None,
            "valid_cells": 0,
            "total_cells": total,
            "coverage": 0.0,
        }
    return {
        "minimum": float(finite.min()),
        "median": float(np.median(finite)),
        "maximum": float(finite.max()),
        "valid_cells": int(finite.size),
        "total_cells": total,
        "coverage": float(finite.size / total) if total else 0.0,
    }


def compute_hazards(model: OceanEmbedModel, selected_date: date) -> dict:
    """Compute every hazard diagnostic for a date. Shared by both endpoints."""
    temperature = np.asarray(model.temperature_field_array(selected_date), dtype="float64")
    return hazard_fields(temperature, np.asarray(STANDARD_DEPTHS, dtype="float64"))


def get_hazard_field(
    selected_date: date,
    variable: str,
    *,
    model: OceanEmbedModel,
) -> HazardFieldResponse:
    """Return one hazard diagnostic as a gridded field."""
    if variable not in VARIABLE_INFO:
        raise ValueError(
            f"Unknown hazard variable {variable!r}. Expected one of: "
            f"{', '.join(sorted(VARIABLE_INFO))}."
        )

    fields = compute_hazards(model, selected_date)
    array = np.asarray(fields[variable], dtype="float64")
    label, unit = VARIABLE_INFO[variable]
    stats = _stats(array)

    lat_count, lon_count = array.shape
    return HazardFieldResponse(
        date=selected_date,
        variable=variable,
        label=label,
        unit=unit,
        values=_field_list(array),
        grid_shape=[int(lat_count), int(lon_count)],
        bounds={
            "latitude_min": MIN_LATITUDE,
            "latitude_max": MAX_LATITUDE,
            "longitude_min": MIN_LONGITUDE,
            "longitude_max": MAX_LONGITUDE,
        },
        stats=stats,
        category_breaks=list(CATEGORY_BREAKS) if variable == "tchp" else [],
        category_labels=list(CATEGORY_LABELS) if variable == "tchp" else [],
        min_valid_depth_m=MIN_VALID_DEPTH,
        provenance=PROVENANCE,
        caveat=CAVEAT,
    )


def get_hazard_summary(
    selected_date: date,
    *,
    model: OceanEmbedModel,
) -> HazardSummaryResponse:
    """Return every hazard diagnostic as summary statistics for one day."""
    fields = compute_hazards(model, selected_date)

    metrics: list[HazardSummaryItem] = []
    for variable in _SUMMARY_VARIABLES:
        stats = _stats(fields[variable])
        label, unit = VARIABLE_INFO[variable]
        metrics.append(
            HazardSummaryItem(
                variable=variable,
                label=label,
                unit=unit,
                minimum=stats["minimum"],
                median=stats["median"],
                maximum=stats["maximum"],
                valid_cells=int(stats["valid_cells"]),
                total_cells=int(stats["total_cells"]),
            )
        )

    mask = np.asarray(fields["valid_mask"], dtype=bool)
    category = np.asarray(fields["tchp_category"], dtype="float64")
    total = int(mask.size)
    valid = int(np.isfinite(category).sum())

    return HazardSummaryResponse(
        date=selected_date,
        status="available" if valid else "unavailable",
        metrics=metrics,
        valid_cells=valid,
        total_cells=total,
        coverage=float(valid / total) if total else 0.0,
        favourable_cells=int((category >= 2).sum()),
        rapid_intensification_cells=int((category >= 3).sum()),
        min_valid_depth_m=MIN_VALID_DEPTH,
        provenance=PROVENANCE,
        caveat=CAVEAT,
    )
