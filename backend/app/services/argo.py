"""ARGO-backed service helpers used by the API routes."""

from __future__ import annotations

from datetime import date

from app.core.constants import MODEL_AVAILABLE_DATES
from app.data.argo import ArgoDataAccessor
from app.data.interfaces import ArgoDataSource
from app.schemas.oceanembed import ArgoFloat, ArgoFloatResponse


def get_argo_floats(
    selected_date: date | None = None,
    *,
    argo: ArgoDataSource | None = None,
) -> ArgoFloatResponse:
    """ARGO-observed cells for a date, shaped for the map markers and cell list."""
    argo_source = argo if argo is not None else ArgoDataAccessor()
    target = selected_date or MODEL_AVAILABLE_DATES[0]

    if not argo_source.is_available():
        return ArgoFloatResponse(
            date=target,
            status="unavailable",
            provenance=argo_source.provenance,
            floats=[],
        )

    matched = argo_source.matched_time(target)
    argo_date, offset = matched if matched else (None, None)

    floats = [
        ArgoFloat(
            id=f"argo-{cell['latitude']:.2f}-{cell['longitude']:.2f}",
            lat=cell["latitude"],
            lon=cell["longitude"],
            n_levels=cell["n_levels"],
            depth_min=cell["depth_min"],
            depth_max=cell["depth_max"],
        )
        for cell in argo_source.observed_cells(target)
    ]

    return ArgoFloatResponse(
        date=target,
        status="available" if floats else "no_overlap",
        provenance=argo_source.provenance,
        argo_date=argo_date,
        time_offset_days=offset,
        floats=floats,
    )
