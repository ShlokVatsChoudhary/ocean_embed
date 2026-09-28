"""GLORYS reference data access for the bundled sample/model artifacts."""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from app.core.constants import (
    MODEL_AVAILABLE_DATES,
    MODEL_DATE_END,
    MODEL_DATE_START,
    MODEL_LATITUDE_MAX,
    MODEL_LATITUDE_MIN,
    MODEL_LATITUDE_RESOLUTION,
    MODEL_LONGITUDE_MAX,
    MODEL_LONGITUDE_MIN,
    MODEL_LONGITUDE_RESOLUTION,
    STANDARD_DEPTHS,
)
from app.data.interfaces import DataSourceStatus, GlorysDataSource


def _nearest_grid_index(value: float, minimum: float, maximum: float, resolution: float, length: int) -> int:
    if value <= minimum:
        return 0
    if value >= maximum:
        return max(length - 1, 0)
    return min(max(int(round((value - minimum) / resolution)), 0), max(length - 1, 0))


class GlorysDataAccessor(GlorysDataSource):
    """Read the bundled GLORYS-style sample field when no external dataset is configured."""

    def __init__(self, model_root: str | Path | None = None):
        self.model_root = self._resolve_model_root(model_root)
        self._sample_cache: tuple[np.ndarray, list[date]] | None = None
        self._y_path: Path | None = self._resolve_y_path()

    @property
    def status(self) -> DataSourceStatus:
        if self.is_available():
            return DataSourceStatus.BUNDLED_SAMPLE
        return DataSourceStatus.UNAVAILABLE

    @property
    def provenance(self) -> str:
        if self.status == DataSourceStatus.LIVE:
            return "Live GLORYS data source configured for this deployment."
        if self.status == DataSourceStatus.BUNDLED_SAMPLE:
            return "GLORYS data source status: bundled_sample; bundled sample values are being used and are not live GLORYS data. Source: model/PS66-Ocean-Model/samples/Y_2020.npy."
        return "GLORYS data is unavailable in this environment."

    def _is_live_glorys_configured(self) -> bool:
        live_root = os.getenv("OCEANEMBED_GLORYS_ROOT") or os.getenv("GLORYS_DATA_ROOT")
        if not live_root:
            return False
        return Path(live_root).expanduser().exists()

    @staticmethod
    def _resolve_model_root(model_root: str | Path | None = None) -> Path:
        if model_root is not None:
            return Path(model_root).expanduser().resolve()

        env_root = os.getenv("OCEANEMBED_MODEL_ROOT")
        if env_root:
            return Path(env_root).expanduser().resolve()

        root = Path(__file__).resolve().parents[3] / "model" / "PS66-Ocean-Model"
        return root.resolve()

    def _resolve_y_path(self) -> Path | None:
        roots: list[Path] = []

        env_root = os.getenv("OCEANEMBED_GLORYS_ROOT") or os.getenv("GLORYS_DATA_ROOT")
        if env_root:
            roots.append(Path(env_root).expanduser())

        roots.append(self.model_root)

        seen: set[Path] = set()
        for root in roots:
            root = root.resolve() if root.exists() else root.expanduser().resolve(strict=False)
            if root in seen:
                continue
            seen.add(root)

            candidates = [
                root / "Y_2020.npy",
                root / "samples" / "Y_2020.npy",
                root / "data" / "processed" / "Y_2020.npy",
            ]
            for candidate in candidates:
                if candidate.exists():
                    return candidate

        return None

    def _load_sample_data(self) -> tuple[np.ndarray, list[date]]:
        if self._sample_cache is not None:
            return self._sample_cache

        y_path = self._resolve_y_path()
        if y_path is None:
            raise FileNotFoundError(
                "GLORYS sample data is unavailable. "
                f"No Y_2020.npy file was found under {self.model_root} or the configured GLORYS root."
            )

        array = np.load(y_path)
        dates = [date(2020, 1, 1) + timedelta(days=offset) for offset in range(array.shape[0])]
        self._sample_cache = (array, dates)
        self._y_path = y_path
        return self._sample_cache

    def is_available(self) -> bool:
        return self._resolve_y_path() is not None

    def _field_for_date(self, target_date: date) -> np.ndarray:
        array, dates = self._load_sample_data()
        if target_date not in dates:
            raise ValueError(
                f"Requested GLORYS date {target_date.isoformat()} is outside the supported demo range: "
                f"{MODEL_DATE_START.isoformat()} to {MODEL_DATE_END.isoformat()}."
            )
        return array[dates.index(target_date)]

    def get_temperature_field(
        self,
        *,
        target_date: date,
        depth: float,
        latitude_min: float | None = None,
        latitude_max: float | None = None,
        longitude_min: float | None = None,
        longitude_max: float | None = None,
    ) -> dict[str, Any]:
        if not self.is_available():
            raise RuntimeError("GLORYS reference data is not available in this environment.")

        if depth not in STANDARD_DEPTHS:
            valid_depths = ", ".join(str(value) for value in STANDARD_DEPTHS)
            raise ValueError(f"Requested depth {depth} is not one of the standard profile depths: {valid_depths}.")

        field = self._field_for_date(target_date)
        depth_index = STANDARD_DEPTHS.index(depth)
        values = field[depth_index]

        lat_axis = np.arange(MODEL_LATITUDE_MIN, MODEL_LATITUDE_MAX + MODEL_LATITUDE_RESOLUTION / 2.0, MODEL_LATITUDE_RESOLUTION, dtype=float)
        lon_axis = np.arange(MODEL_LONGITUDE_MIN, MODEL_LONGITUDE_MAX + MODEL_LONGITUDE_RESOLUTION / 2.0, MODEL_LONGITUDE_RESOLUTION, dtype=float)

        lat_min = latitude_min if latitude_min is not None else MODEL_LATITUDE_MIN
        lat_max = latitude_max if latitude_max is not None else MODEL_LATITUDE_MAX
        lon_min = longitude_min if longitude_min is not None else MODEL_LONGITUDE_MIN
        lon_max = longitude_max if longitude_max is not None else MODEL_LONGITUDE_MAX

        row_start = _nearest_grid_index(lat_max, MODEL_LATITUDE_MIN, MODEL_LATITUDE_MAX, MODEL_LATITUDE_RESOLUTION, values.shape[0])
        row_end = _nearest_grid_index(lat_min, MODEL_LATITUDE_MIN, MODEL_LATITUDE_MAX, MODEL_LATITUDE_RESOLUTION, values.shape[0])
        lat_start = min(row_start, row_end)
        lat_end = max(row_start, row_end)

        col_start = _nearest_grid_index(lon_min, MODEL_LONGITUDE_MIN, MODEL_LONGITUDE_MAX, MODEL_LONGITUDE_RESOLUTION, values.shape[1])
        col_end = _nearest_grid_index(lon_max, MODEL_LONGITUDE_MIN, MODEL_LONGITUDE_MAX, MODEL_LONGITUDE_RESOLUTION, values.shape[1])
        lon_start = min(col_start, col_end)
        lon_end = max(col_start, col_end)

        subset = values[lat_start:lat_end + 1, lon_start:lon_end + 1]
        return {
            "date": target_date,
            "depth": depth,
            "values": subset.tolist(),
            "lats": lat_axis[lat_start:lat_end + 1].tolist(),
            "lons": lon_axis[lon_start:lon_end + 1].tolist(),
            "latitude_min": lat_min,
            "latitude_max": lat_max,
            "longitude_min": lon_min,
            "longitude_max": lon_max,
        }

    def get_point_temperature(
        self,
        *,
        latitude: float,
        longitude: float,
        target_date: date,
        depth: float,
    ) -> dict[str, Any]:
        if not self.is_available():
            raise RuntimeError("GLORYS reference data is not available in this environment.")

        if depth not in STANDARD_DEPTHS:
            valid_depths = ", ".join(str(value) for value in STANDARD_DEPTHS)
            raise ValueError(f"Requested depth {depth} is not one of the standard profile depths: {valid_depths}.")

        field = self._field_for_date(target_date)
        depth_index = STANDARD_DEPTHS.index(depth)
        lat_index = _nearest_grid_index(latitude, MODEL_LATITUDE_MIN, MODEL_LATITUDE_MAX, MODEL_LATITUDE_RESOLUTION, field[depth_index].shape[0])
        lon_index = _nearest_grid_index(longitude, MODEL_LONGITUDE_MIN, MODEL_LONGITUDE_MAX, MODEL_LONGITUDE_RESOLUTION, field[depth_index].shape[1])
        value = float(field[depth_index, lat_index, lon_index])
        return {"temperature": value}
