"""ARGO validation data access.

ARGO is the **independent** observational reference for OceanEmbed. It is used
only for evaluation: it is never an input channel and never a training target.

The archive shipped with the demo is the INCOIS 10-day gridded McCreary ARGO
analysis (``T_ANALYZED``), which is a 1x1 degree product on 24 depth levels.
OceanEmbed predicts on a 0.25 degree grid at 15 standard depths, so this module
regrids ARGO with nearest-neighbour index lookup and interpolates vertically to
the standard depths. That is the same procedure used by the training repository
(``model/PS66-Ocean-Model/src/argo.py``), so the numbers reported by the API and
by ``run_argo_validation.py`` come from one method, not two.

Two honest limitations are surfaced rather than hidden:

* ARGO has no 0 m level (it starts at 5 m), so depth 0 reports no observation.
* The product is a 10-day analysis while OceanEmbed is daily, so each model date
  is matched to the nearest ARGO analysis time and the offset is reported.

Data locations tried, in order:

1. ``OCEANEMBED_ARGO_PATH``
2. ``<repo>/backend/data/argo/*.nc`` (or ``*.npz``)
3. ``<model_root>/data/raw/argo*.nc``

If none exist the accessor reports ``UNAVAILABLE`` and every validation result is
empty. No synthetic ARGO values are ever produced.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import get_settings
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
from app.data.interfaces import ArgoDataSource, DataSourceStatus

N_LAT = int(round((MODEL_LATITUDE_MAX - MODEL_LATITUDE_MIN) / MODEL_LATITUDE_RESOLUTION)) + 1
N_LON = int(round((MODEL_LONGITUDE_MAX - MODEL_LONGITUDE_MIN) / MODEL_LONGITUDE_RESOLUTION)) + 1

#: Names seen across INCOIS / generic gridded-ARGO files.
_TEMP_NAMES = ("T_ANALYZED", "temp", "temperature", "TEMP", "thetao", "T", "TEMP_ADJUSTED")
_DEPTH_NAMES = ("depth", "ZAX", "z", "lev", "level", "pres", "pressure")
_LAT_NAMES = ("latitude", "lat", "YAX")
_LON_NAMES = ("longitude", "lon", "XAX")
_TIME_NAMES = ("time", "TIME", "t")

#: Absolute sentinel guard for fill values that survive ``mask_and_scale``.
_FILL_ABS_LIMIT = 1e4

#: Only interpolate between measured levels; extrapolate 0 m from the shallowest
#: level the way the training repository does, and leave everything else NaN.
_SURFACE_DEPTH_M = float(min(STANDARD_DEPTHS))


def _axis_index(axis: list[float], target: float) -> int:
    return int(np.argmin(np.abs(np.asarray(axis, dtype=float) - float(target))))


def _nearest_axis(axis: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Index of the nearest source coordinate for every target coordinate."""
    axis = np.asarray(axis, dtype=float)
    target = np.asarray(target, dtype=float)
    return np.abs(target[:, None] - axis[None, :]).argmin(axis=1)


def _interp_to_standard_depths(values: np.ndarray, depth_axis: np.ndarray) -> np.ndarray:
    """Linearly interpolate ``(..., depth)`` onto ``STANDARD_DEPTHS``.

    Below the deepest measured level the result is NaN; the shallowest
    standard depth falls back to the shallowest measured level.
    """
    d = np.asarray(depth_axis, dtype=float)
    v = np.asarray(values, dtype=float)
    if v.shape[-1] != d.size:
        raise ValueError(f"depth axis ({d.size}) does not match data ({v.shape[-1]}).")

    order = np.argsort(d)
    d = d[order]
    v = v[..., order]

    tgt = np.asarray(STANDARD_DEPTHS, dtype=float)
    out = np.full(v.shape[:-1] + (tgt.size,), np.nan, dtype="float32")

    for k, level in enumerate(tgt):
        if level <= d[0]:
            out[..., k] = v[..., 0]
            continue
        if level > d[-1]:
            continue  # deeper than ARGO reports -> no observation
        j = int(np.searchsorted(d, level, side="left"))
        lo, hi = j - 1, j
        span = d[hi] - d[lo]
        if span <= 0:
            out[..., k] = v[..., lo]
            continue
        w = (level - d[lo]) / span
        out[..., k] = (1.0 - w) * v[..., lo] + w * v[..., hi]

    return out


class ArgoDataAccessor(ArgoDataSource):
    """Load the bundled gridded ARGO analysis and regrid it to the model grid."""

    def __init__(self, argo_path: str | Path | None = None) -> None:
        settings = get_settings()
        self._explicit_path = Path(argo_path).expanduser() if argo_path else None
        self._argo_dir = Path(settings.argo_dir).expanduser()
        self._model_root = Path(settings.model_root).expanduser()

        self._path: Path | None = None
        self._resolved = False
        #: (times as datetime64[D], temperature (T, 15, 101, 241))
        self._cache: tuple[np.ndarray, np.ndarray] | None = None
        self._load_error: str | None = None

    # ------------------------------------------------------------------ paths
    def _candidates(self) -> list[Path]:
        found: list[Path] = []

        if self._explicit_path is not None:
            found.append(self._explicit_path)

        env_path = os.getenv("OCEANEMBED_ARGO_PATH")
        if env_path:
            found.append(Path(env_path).expanduser())

        for directory in (self._argo_dir, self._model_root / "data" / "raw", self._model_root / "data" / "argo"):
            if not directory.is_dir():
                continue
            for pattern in ("*.nc", "*.nc4", "*.npz"):
                found.extend(sorted(directory.glob(pattern)))

        return found

    def _resolve_path(self) -> Path | None:
        if self._resolved:
            return self._path
        self._resolved = True
        for candidate in self._candidates():
            if candidate.is_file() and candidate.stat().st_size > 0:
                self._path = candidate
                break
        return self._path

    # ------------------------------------------------------------------ status
    #: Machine-readable description of what kind of reference this is.
    kind = "gridded_10day_analysis_1deg"

    @property
    def path(self) -> Path | None:
        return self._resolve_path()

    def is_available(self) -> bool:
        return self._resolve_path() is not None

    @property
    def status(self) -> DataSourceStatus:
        return DataSourceStatus.BUNDLED_SAMPLE if self.is_available() else DataSourceStatus.UNAVAILABLE

    @property
    def provenance(self) -> str:
        if not self.is_available():
            return (
                "ARGO validation data is unavailable. Set OCEANEMBED_ARGO_PATH or place a "
                "gridded ARGO NetCDF under backend/data/argo/."
            )
        return (
            f"Independent ARGO reference (INCOIS 10-day gridded analysis, T_ANALYZED) loaded from "
            f"{self._path.name}. ARGO is used for evaluation only and never for training. "
            f"ARGO is a 1 degree, 10-day product; model output is 0.25 degree daily."
        )

    # -------------------------------------------------------------------- load
    def _load_netcdf(self, path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        import xarray as xr

        with xr.open_dataset(path, mask_and_scale=True) as ds:
            temp_name = next((n for n in _TEMP_NAMES if n in ds.data_vars), None)
            if temp_name is None:
                raise ValueError(f"No temperature variable in {path.name}; found {list(ds.data_vars)}.")

            da = ds[temp_name]

            def pick(names: tuple[str, ...]) -> str | None:
                return next((n for n in names if n in da.coords or n in da.dims), None)

            lat_name, lon_name = pick(_LAT_NAMES), pick(_LON_NAMES)
            depth_name, time_name = pick(_DEPTH_NAMES), pick(_TIME_NAMES)
            if lat_name is None or lon_name is None or depth_name is None:
                raise ValueError(f"Could not identify lat/lon/depth coordinates in {path.name}.")

            values = np.array(da.values, dtype="float64", copy=True)
            dims = list(da.dims)
            lat = np.asarray(da[lat_name].values, dtype=float)
            lon = np.asarray(da[lon_name].values, dtype=float)
            depth_axis = np.asarray(da[depth_name].values, dtype=float)
            times = (
                np.asarray(da[time_name].values, dtype="datetime64[D]")
                if time_name is not None
                else np.array([np.datetime64(d, "D") for d in MODEL_AVAILABLE_DATES])
            )

        # Fill values that survived decoding, then force (time, depth, lat, lon).
        values[np.abs(values) > _FILL_ABS_LIMIT] = np.nan
        target_names = [n for n in (time_name, depth_name, lat_name, lon_name) if n is not None]
        values = np.transpose(values, [dims.index(n) for n in target_names])
        if time_name is None:
            values = values[None, ...]
        return values, times, lat, lon, depth_axis

    def _load_npz(self, path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        with np.load(path) as data:
            temp_key = next((k for k in _TEMP_NAMES if k in data), None)
            if temp_key is None:
                raise ValueError(f"No temperature array in {path.name}; found {list(data.files)}.")
            values = np.asarray(data[temp_key], dtype="float64")
            lat = np.asarray(data["lat"] if "lat" in data else data["latitude"], dtype=float)
            lon = np.asarray(data["lon"] if "lon" in data else data["longitude"], dtype=float)
            depth_axis = np.asarray(data["depth"], dtype=float)
            times = (
                np.asarray(data["time"], dtype="datetime64[D]")
                if "time" in data
                else np.array([np.datetime64(d, "D") for d in MODEL_AVAILABLE_DATES])
            )
        if values.ndim == 3:
            values = values[None, ...]
        return values, times, lat, lon, depth_axis

    def _load(self) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(times, temperature)`` on the model grid as ``(T, 15, 101, 241)``."""
        if self._cache is not None:
            return self._cache
        if self._load_error is not None:
            raise RuntimeError(self._load_error)

        path = self._resolve_path()
        if path is None:
            self._load_error = "ARGO validation data is unavailable in this environment."
            raise RuntimeError(self._load_error)

        try:
            if path.suffix.lower() == ".npz":
                values, times, lat, lon, depth_axis = self._load_npz(path)
            else:
                values, times, lat, lon, depth_axis = self._load_netcdf(path)
        except Exception as exc:  # noqa: BLE001 - surfaced through the API as a status
            self._load_error = f"Failed to read ARGO file {path.name}: {exc}"
            raise RuntimeError(self._load_error) from exc

        # Vertical interpolation to the model's standard depths, then nearest
        # horizontal regrid onto the 0.25 degree model grid. The vertical axis
        # is index 1 of the (time, depth, lat, lon) array.
        v = np.moveaxis(np.asarray(values, dtype="float64"), 1, -1)
        on_depths = np.moveaxis(
            _interp_to_standard_depths(v, np.asarray(depth_axis, dtype=float)), -1, 1
        )

        lat_target = MODEL_LATITUDE_MIN + np.arange(N_LAT) * MODEL_LATITUDE_RESOLUTION
        lon_target = MODEL_LONGITUDE_MIN + np.arange(N_LON) * MODEL_LONGITUDE_RESOLUTION
        # ``_nearest_axis(source, target)`` returns, for every target coordinate,
        # the index of the nearest source coordinate. Read as model cell -> ARGO
        # cell, which is the same nearest-neighbour upsample the training
        # repository uses in ``src/argo.py::regrid_to_target``.
        iy = _nearest_axis(np.asarray(lat, dtype=float), lat_target)
        ix = _nearest_axis(np.asarray(lon, dtype=float), lon_target)

        # (T, 15, n_argo_lat, n_argo_lon) -> (T, 15, 101, 241)
        field = np.asarray(on_depths[:, :, iy, :][:, :, :, ix], dtype="float32")

        self._cache = (times, field)
        return self._cache

    # ------------------------------------------------------------------ public
    def available_times(self) -> list[date]:
        if not self.is_available():
            return []
        times, _ = self._load()
        return [date.fromisoformat(str(t)) for t in times]

    def matched_time(self, target: date) -> tuple[date, int] | None:
        """Nearest ARGO analysis time for a model date, plus the offset in days."""
        times = self.available_times()
        if not times:
            return None
        target_ord = target.toordinal()
        best = min(times, key=lambda t: abs(t.toordinal() - target_ord))
        return best, best.toordinal() - target_ord

    def temperature_field(self, target: date) -> np.ndarray | None:
        """ARGO field on the model grid for the nearest analysis time."""
        match = self.matched_time(target)
        if match is None:
            return None
        times, field = self._load()
        argo_date, _ = match
        index = int(np.searchsorted(times, np.datetime64(argo_date, "D")))
        index = min(max(index, 0), len(times) - 1)
        return np.asarray(field[index], dtype=float)

    # ------------------------------------------------------- interface methods
    def get_profile_by_id(self, profile_id: str) -> dict[str, Any]:
        """Return the ARGO profile at a grid cell.

        The bundled archive is a *gridded* product, so there are no float IDs.
        Cells are addressed as ``argo-<lat>-<lon>`` and the returned profile
        includes every available ARGO analysis time at that cell.
        """
        if not self.is_available():
            raise RuntimeError("ARGO validation data is unavailable in this environment.")

        try:
            _, lat_text, lon_text = profile_id.split("-", 2)
            latitude, longitude = float(lat_text), float(lon_text)
        except ValueError as exc:
            raise ValueError(
                f"Unrecognised ARGO profile id {profile_id!r}; expected 'argo-<lat>-<lon>'."
            ) from exc

        times, field = self._load()
        lat_target = MODEL_LATITUDE_MIN + np.arange(N_LAT) * MODEL_LATITUDE_RESOLUTION
        lon_target = MODEL_LONGITUDE_MIN + np.arange(N_LON) * MODEL_LONGITUDE_RESOLUTION
        iy = _axis_index(list(lat_target), latitude)
        ix = _axis_index(list(lon_target), longitude)

        # ARGO lives on 1 degree centres, so the model cell nearest a requested
        # point is frequently one ARGO never samples. Snap to the closest cell
        # that actually carries an observation instead of returning an empty
        # profile for a point the user can see on the map.
        observed = np.isfinite(field).any(axis=(0, 1))
        if not observed[iy, ix]:
            rows, cols = np.where(observed)
            if rows.size:
                distance = (rows - iy) ** 2 + (cols - ix) ** 2
                iy, ix = int(rows[distance.argmin()]), int(cols[distance.argmin()])

        levels = field[:, :, iy, ix]  # (T, 15)
        series = []
        for t_index, time_value in enumerate(times):
            profile = [
                {"depth": float(depth), "temperature": float(levels[t_index, d_index])}
                for d_index, depth in enumerate(STANDARD_DEPTHS)
                if np.isfinite(levels[t_index, d_index])
            ]
            if profile:
                series.append({"date": str(time_value), "profile": profile})

        return {
            "profile_id": profile_id,
            "source": "ARGO",
            "kind": "gridded_analysis",
            "requested": {"latitude": float(latitude), "longitude": float(longitude)},
            "latitude": float(MODEL_LATITUDE_MIN + iy * MODEL_LATITUDE_RESOLUTION),
            "longitude": float(MODEL_LONGITUDE_MIN + ix * MODEL_LONGITUDE_RESOLUTION),
            "series": series,
        }

    def observed_cells(self, target: date) -> list[dict[str, Any]]:
        """Grid cells carrying at least one ARGO level on the nearest analysis time.

        This is the ARGO analogue of a float list. The bundled archive is gridded,
        so cells are reported rather than float identifiers.
        """
        field = self.temperature_field(target)
        if field is None:
            return []

        lat_axis = MODEL_LATITUDE_MIN + np.arange(N_LAT) * MODEL_LATITUDE_RESOLUTION
        lon_axis = MODEL_LONGITUDE_MIN + np.arange(N_LON) * MODEL_LONGITUDE_RESOLUTION
        depths = np.asarray(STANDARD_DEPTHS, dtype=float)

        cells: list[dict[str, Any]] = []
        for row in range(N_LAT):
            for col in range(N_LON):
                column = field[:, row, col]
                finite = np.isfinite(column)
                if not finite.any():
                    continue
                present = depths[finite]
                cells.append(
                    {
                        "latitude": float(lat_axis[row]),
                        "longitude": float(lon_axis[col]),
                        "n_levels": int(finite.sum()),
                        "depth_min": float(present.min()),
                        "depth_max": float(present.max()),
                    }
                )
        return cells

    def get_validation_observations(
        self,
        *,
        date: date | None = None,
        depth: float | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> list[dict[str, Any]]:
        """ARGO values on the model grid, filtered by date/depth/point.

        Returns one dict per *observed* grid cell and depth; NaN cells are
        omitted so the caller never sees a fabricated value.
        """
        if not self.is_available():
            return []

        targets = [date] if date is not None else list(MODEL_AVAILABLE_DATES)
        lat_target = MODEL_LATITUDE_MIN + np.arange(N_LAT) * MODEL_LATITUDE_RESOLUTION
        lon_target = MODEL_LONGITUDE_MIN + np.arange(N_LON) * MODEL_LONGITUDE_RESOLUTION
        depth_indices = (
            [STANDARD_DEPTHS.index(depth)] if depth in STANDARD_DEPTHS else range(len(STANDARD_DEPTHS))
        )

        observations: list[dict[str, Any]] = []
        for target in targets:
            field = self.temperature_field(target)
            if field is None:
                continue
            match = self.matched_time(target)
            argo_date, offset = match if match else (target, 0)
            for d_index in depth_indices:
                layer = field[d_index]
                rows, cols = np.where(np.isfinite(layer))
                for row, col in zip(rows.tolist(), cols.tolist()):
                    latitude_value = float(lat_target[row])
                    longitude_value = float(lon_target[col])
                    if latitude is not None and abs(latitude_value - latitude) > 1.0:
                        continue
                    if longitude is not None and abs(longitude_value - longitude) > 1.0:
                        continue
                    observations.append(
                        {
                            "latitude": latitude_value,
                            "longitude": longitude_value,
                            "date": target,
                            "argo_date": argo_date,
                            "time_offset_days": offset,
                            "depth": float(STANDARD_DEPTHS[d_index]),
                            "observed_temperature": float(layer[row, col]),
                            "source": "ARGO",
                        }
                    )
        return observations
