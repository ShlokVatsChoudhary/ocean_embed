"""Independent validation of OceanEmbed against ARGO.

ARGO is the observational reference and is **never** used for training. Every
number returned here is computed from real, co-located model/ARGO pairs; when no
overlap exists the payload says so instead of substituting placeholder values.

Two habits matter more than the headline number:

1. **A common mask.** Model and reference are compared only where both have a
   finite value, and the number of cells per day is reported so the reader can
   judge how much of the basin the statistic actually covers.
2. **Bands, not one average.** ``metrics.rmse`` averages every depth, which is
   dominated by the deep layers where temperature barely changes. The
   ``>= 50 m`` band and the thermocline band (50-200 m) are reported separately.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from app.core.constants import (
    MODEL_AVAILABLE_DATES,
    MODEL_LATITUDE_MAX,
    MODEL_LATITUDE_MIN,
    MODEL_LATITUDE_RESOLUTION,
    MODEL_LONGITUDE_MAX,
    MODEL_LONGITUDE_MIN,
    MODEL_LONGITUDE_RESOLUTION,
    STANDARD_DEPTHS,
)
from app.data.argo import ArgoDataAccessor
from app.data.interfaces import ArgoDataSource
from app.model.interface import OceanEmbedModel
from app.schemas.oceanembed import (
    DepthMetrics,
    ScatterPoint,
    ValidationMetrics,
    ValidationObservation,
    ValidationResponse,
    ValidationSummary,
)

#: Depth bands. ``THERMOCLINE`` is inclusive at both ends.
GE50_DEPTH = 50.0
THERMOCLINE_MIN = 50.0
THERMOCLINE_MAX = 200.0

#: Cap on point-level payload size so the JSON stays small.
MAX_SCATTER_POINTS = 400
MAX_OBSERVATIONS = 250

MODEL_VERSION = "oceanembed-v0.3-real"

EVALUATION_CAVEAT = (
    "Validated on the model's available window, which overlaps the training period. "
    "These scores are an optimistic upper bound; an independent year is still required. "
    "The ARGO product is a 1-degree, 10-day analysis: it is upsampled to the model grid, so "
    "each ARGO value contributes to several model cells, and the 0 m model level is compared "
    "against the 5 m ARGO level because the product has no 0 m layer."
)


# --------------------------------------------------------------------------- stats
def _finite_pairs(predicted: np.ndarray, observed: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    both = np.isfinite(predicted) & np.isfinite(observed)
    return np.asarray(predicted[both], dtype="float64"), np.asarray(observed[both], dtype="float64")


def _rmse(predicted: np.ndarray, observed: np.ndarray) -> float | None:
    if predicted.size == 0:
        return None
    return float(np.sqrt(np.mean((predicted - observed) ** 2)))


def _mae(predicted: np.ndarray, observed: np.ndarray) -> float | None:
    if predicted.size == 0:
        return None
    return float(np.mean(np.abs(predicted - observed)))


def _bias(predicted: np.ndarray, observed: np.ndarray) -> float | None:
    if predicted.size == 0:
        return None
    return float(np.mean(predicted - observed))


def _correlation(predicted: np.ndarray, observed: np.ndarray) -> float | None:
    if predicted.size < 2:
        return None
    if np.std(predicted) == 0 or np.std(observed) == 0:
        return None
    return float(np.corrcoef(predicted, observed)[0, 1])


# ----------------------------------------------------------------------- filtering
def _latlon_slice(
    latitude: float | None, longitude: float | None
) -> tuple[slice, slice]:
    """Nearest grid window for an optional point filter."""
    if latitude is None:
        rows = slice(None)
    else:
        n_lat = int(round((MODEL_LATITUDE_MAX - MODEL_LATITUDE_MIN) / MODEL_LATITUDE_RESOLUTION)) + 1
        row = int(round((latitude - MODEL_LATITUDE_MIN) / MODEL_LATITUDE_RESOLUTION))
        row = min(max(row, 0), n_lat - 1)
        rows = slice(row, row + 1)

    if longitude is None:
        cols = slice(None)
    else:
        n_lon = int(round((MODEL_LONGITUDE_MAX - MODEL_LONGITUDE_MIN) / MODEL_LONGITUDE_RESOLUTION)) + 1
        col = int(round((longitude - MODEL_LONGITUDE_MIN) / MODEL_LONGITUDE_RESOLUTION))
        col = min(max(col, 0), n_lon - 1)
        cols = slice(col, col + 1)

    return rows, cols


# ------------------------------------------------------------------ main entry point
def get_validation(
    selected_date: date | None = None,
    depth: float | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    argo_profile_id: str | None = None,
    *,
    model: OceanEmbedModel | None = None,
    argo: ArgoDataSource | None = None,
) -> ValidationResponse:
    """Compare OceanEmbed against ARGO on a common mask."""
    argo_source = argo if argo is not None else ArgoDataAccessor()

    if not argo_source.is_available():
        return ValidationResponse(
            dataset="ARGO",
            status="unavailable",
            provenance=argo_source.provenance,
            metrics=ValidationMetrics(),
            summary=ValidationSummary(
                status="unavailable",
                provenance=argo_source.provenance,
                model_version=MODEL_VERSION,
                caveat=EVALUATION_CAVEAT,
            ),
        )

    if model is None:
        raise ValueError("Validation requires an OceanEmbedModel instance.")

    dates = [selected_date] if selected_date is not None else list(MODEL_AVAILABLE_DATES)
    rows, cols = _latlon_slice(latitude, longitude)
    depth_indices = (
        [STANDARD_DEPTHS.index(depth)] if depth in STANDARD_DEPTHS else list(range(len(STANDARD_DEPTHS)))
    )

    per_depth_predicted: dict[int, list[np.ndarray]] = {i: [] for i in depth_indices}
    per_depth_observed: dict[int, list[np.ndarray]] = {i: [] for i in depth_indices}
    per_depth_positions: dict[int, list[tuple[float, float, date]]] = {i: [] for i in depth_indices}
    common_mask_cells: list[int] = []

    for target in dates:
        predicted_field = model.temperature_field_array(target)
        observed_field = argo_source.temperature_field(target)
        if observed_field is None:
            continue

        predicted_field = np.asarray(predicted_field, dtype="float64")[:, rows, cols]
        observed_field = np.asarray(observed_field, dtype="float64")[:, rows, cols]

        both = np.isfinite(predicted_field) & np.isfinite(observed_field)
        if both.any():
            # Cells usable at every depth in the request: the common mask.
            common_mask_cells.append(int(both.all(axis=0).sum()))

        for d_index in depth_indices:
            p = predicted_field[d_index]
            o = observed_field[d_index]
            mask = np.isfinite(p) & np.isfinite(o)
            if not mask.any():
                continue
            per_depth_predicted[d_index].append(p[mask])
            per_depth_observed[d_index].append(o[mask])

            n_lat = p.shape[0]
            n_lon = p.shape[1]
            for flat in np.flatnonzero(mask.ravel()):
                r, c = divmod(int(flat), n_lon)
                if latitude is None and longitude is None and len(per_depth_positions[d_index]) >= MAX_OBSERVATIONS:
                    break
                lat_value = (
                    latitude
                    if latitude is not None
                    else MODEL_LATITUDE_MIN + (rows.start or 0) * MODEL_LATITUDE_RESOLUTION + r * MODEL_LATITUDE_RESOLUTION
                )
                lon_value = (
                    longitude
                    if longitude is not None
                    else MODEL_LONGITUDE_MIN + (cols.start or 0) * MODEL_LONGITUDE_RESOLUTION + c * MODEL_LONGITUDE_RESOLUTION
                )
                per_depth_positions[d_index].append((lat_value, lon_value, target))

    all_predicted = np.concatenate([np.concatenate(v) for v in per_depth_predicted.values() if v]) if any(per_depth_predicted.values()) else np.array([])
    all_observed = np.concatenate([np.concatenate(v) for v in per_depth_observed.values() if v]) if any(per_depth_observed.values()) else np.array([])

    if all_predicted.size == 0:
        return ValidationResponse(
            dataset="ARGO",
            status="no_overlap",
            provenance=argo_source.provenance,
            reference_kind=getattr(argo_source, "kind", "gridded_analysis"),
            metrics=ValidationMetrics(),
            summary=ValidationSummary(
                status="no_overlap",
                provenance=argo_source.provenance,
                model_version=MODEL_VERSION,
                caveat=EVALUATION_CAVEAT,
            ),
        )

    def _band(lo: float, hi: float) -> tuple[np.ndarray, np.ndarray]:
        predicted_parts, observed_parts = [], []
        for d_index, parts in per_depth_predicted.items():
            level = STANDARD_DEPTHS[d_index]
            if lo <= level <= hi and parts:
                predicted_parts.append(np.concatenate(parts))
                observed_parts.append(np.concatenate(per_depth_observed[d_index]))
        if not predicted_parts:
            return np.array([]), np.array([])
        return np.concatenate(predicted_parts), np.concatenate(observed_parts)

    ge50_predicted, ge50_observed = _band(GE50_DEPTH, float("inf"))
    therm_predicted, therm_observed = _band(THERMOCLINE_MIN, THERMOCLINE_MAX)

    per_depth = [
        DepthMetrics(
            depth=float(STANDARD_DEPTHS[d_index]),
            rmse=_rmse(np.concatenate(parts), np.concatenate(per_depth_observed[d_index])),
            mae=_mae(np.concatenate(parts), np.concatenate(per_depth_observed[d_index])),
            bias=_bias(np.concatenate(parts), np.concatenate(per_depth_observed[d_index])),
            correlation=_correlation(np.concatenate(parts), np.concatenate(per_depth_observed[d_index])),
            n=int(sum(part.size for part in parts)),
        )
        for d_index, parts in per_depth_predicted.items()
        if parts
    ]

    metrics = ValidationMetrics(
        rmse=_rmse(all_predicted, all_observed),
        mae=_mae(all_predicted, all_observed),
        bias=_bias(all_predicted, all_observed),
        correlation=_correlation(all_predicted, all_observed),
        n_observations=int(all_predicted.size),
        rmse_ge50=_rmse(ge50_predicted, ge50_observed),
        rmse_thermocline=_rmse(therm_predicted, therm_observed),
        n_cells_per_day=int(round(float(np.mean(common_mask_cells)))) if common_mask_cells else None,
    )

    # ------------------------------------------------------------- scatter / audit
    scatter: list[ScatterPoint] = []
    if all_predicted.size:
        step = max(1, all_predicted.size // MAX_SCATTER_POINTS)
        depth_lookup = np.concatenate(
            [np.full(int(sum(p.size for p in parts)), STANDARD_DEPTHS[d_index]) for d_index, parts in per_depth_predicted.items() if parts]
        )
        for index in range(0, all_predicted.size, step):
            if len(scatter) >= MAX_SCATTER_POINTS:
                break
            scatter.append(
                ScatterPoint(
                    predicted=float(all_predicted[index]),
                    observed=float(all_observed[index]),
                    depth=float(depth_lookup[index]),
                )
            )

    observations: list[ValidationObservation] = []
    for d_index, positions in per_depth_positions.items():
        predicted_parts = per_depth_predicted[d_index]
        observed_parts = per_depth_observed[d_index]
        if not predicted_parts:
            continue
        flat_predicted = np.concatenate(predicted_parts)
        flat_observed = np.concatenate(observed_parts)
        for (lat_value, lon_value, target), p_value, o_value in zip(positions, flat_predicted, flat_observed):
            if len(observations) >= MAX_OBSERVATIONS:
                break
            observations.append(
                ValidationObservation(
                    latitude=float(lat_value),
                    longitude=float(lon_value),
                    date=target,
                    depth=float(STANDARD_DEPTHS[d_index]),
                    oceanembed_temperature=float(p_value),
                    observed_temperature=float(o_value),
                    difference=float(p_value - o_value),
                    source="ARGO",
                )
            )

    matched = argo_source.matched_time(dates[0])
    date_range = (
        f"{dates[0].isoformat()} to {dates[-1].isoformat()}"
        if len(dates) > 1
        else dates[0].isoformat()
    )

    summary = ValidationSummary(
        status="available",
        provenance=argo_source.provenance,
        reference="ARGO",
        reference_kind=getattr(argo_source, "kind", "gridded_analysis"),
        date_range=date_range,
        n_profiles=metrics.n_cells_per_day,
        n_observations=metrics.n_observations,
        mean_error=metrics.mae,
        correlation=metrics.correlation,
        model_version=MODEL_VERSION,
        caveat=EVALUATION_CAVEAT,
    )
    if matched is not None and matched[1] != 0:
        summary.caveat = (
            f"{EVALUATION_CAVEAT} ARGO is a 10-day analysis, so model dates are matched to the "
            f"nearest analysis time (up to {abs(matched[1])} days away for {dates[0].isoformat()})."
        )

    return ValidationResponse(
        dataset="ARGO",
        status="available",
        provenance=argo_source.provenance,
        reference_kind=getattr(argo_source, "kind", "gridded_analysis"),
        metrics=metrics,
        per_depth=per_depth,
        summary=summary,
        scatter=scatter,
        observations=observations,
    )


# ---------------------------------------------------------------------- alerts
def get_anomaly_alerts(
    selected_date: date | None = None,
    *,
    limit: int = 6,
    model: OceanEmbedModel | None = None,
    argo: ArgoDataSource | None = None,
) -> "AnomalyAlertResponse":
    """Return the strongest model-vs-ARGO disagreements for review.

    These are *diagnostic* candidates, not operational hazard warnings: they mark
    where the reconstruction is least consistent with observations so a reviewer
    knows which locations to inspect first.
    """
    from app.schemas.oceanembed import AnomalyAlert, AnomalyAlertResponse

    argo_source = argo if argo is not None else ArgoDataAccessor()
    if not argo_source.is_available() or model is None:
        return AnomalyAlertResponse(
            status="unavailable",
            provenance=argo_source.provenance,
            alerts=[],
        )

    dates = [selected_date] if selected_date is not None else list(MODEL_AVAILABLE_DATES)
    lat_axis = MODEL_LATITUDE_MIN + np.arange(101) * MODEL_LATITUDE_RESOLUTION
    lon_axis = MODEL_LONGITUDE_MIN + np.arange(241) * MODEL_LONGITUDE_RESOLUTION

    candidates: list[tuple[float, date, int, int, int, float, float]] = []
    for target in dates:
        predicted = np.asarray(model.temperature_field_array(target), dtype="float64")
        observed = argo_source.temperature_field(target)
        if observed is None:
            continue
        observed = np.asarray(observed, dtype="float64")
        difference = predicted - observed
        difference[~np.isfinite(difference)] = np.nan
        flat = np.argsort(np.abs(np.nan_to_num(difference, nan=0.0)).ravel())[::-1][: limit * 4]
        for flat_index in flat:
            d_index, rest = divmod(int(flat_index), observed.shape[1] * observed.shape[2])
            r, c = divmod(rest, observed.shape[2])
            value = float(difference[d_index, r, c])
            if not np.isfinite(value):
                continue
            candidates.append(
                (abs(value), target, int(d_index), int(r), int(c), value, float(observed[d_index, r, c]))
            )

    candidates.sort(key=lambda item: item[0], reverse=True)

    alerts: list[AnomalyAlert] = []
    for magnitude, target, d_index, r, c, value, observed_value in candidates[:limit]:
        direction = "warm" if value > 0 else "cold"
        alerts.append(
            AnomalyAlert(
                id=f"argo-{lat_axis[r]:.2f}-{lon_axis[c]:.2f}",
                lat=float(lat_axis[r]),
                lon=float(lon_axis[c]),
                date=target,
                depth=float(STANDARD_DEPTHS[d_index]),
                difference=float(value),
                direction=direction,
                message=(
                    f"OceanEmbed is {abs(value):.2f} degC too {direction} versus ARGO at "
                    f"{STANDARD_DEPTHS[d_index]:.0f} m (model {observed_value + value:.2f}, "
                    f"ARGO {observed_value:.2f})."
                ),
            )
        )

    return AnomalyAlertResponse(
        status="available" if alerts else "no_overlap",
        provenance=argo_source.provenance,
        alerts=alerts,
    )
