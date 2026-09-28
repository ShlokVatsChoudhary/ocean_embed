from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import tensorflow as tf

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
from app.model.interface import (
    ModelInferenceInput,
    ModelProfilePrediction,
    ModelTemperaturePrediction,
    OceanEmbedModel,
)


def _nearest_grid_index(value: float, minimum: float, maximum: float, resolution: float, length: int) -> int:
    if value <= minimum:
        return 0
    if value >= maximum:
        return max(length - 1, 0)
    index = int(round((value - minimum) / resolution))
    return min(max(index, 0), max(length - 1, 0))


class OceanEmbedModelAdapter(OceanEmbedModel):
    """Concrete adapter for the trained PS66 OceanModel and shipped weights."""

    input_channels = ["sst", "sss", "sla", "ugos", "vgos"]
    output_depths = list(STANDARD_DEPTHS)
    grid_shape = (101, 241)

    def __init__(self, model_root: str | Path | None = None):
        self.model_root = self._resolve_model_root(model_root)
        self._sample_cache: tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], list[str]] | None = None
        self._sample_dates: list[date] | None = None
        self._tf_model = None
        self._tf_model_imports = None

    @staticmethod
    def _resolve_model_root(model_root: str | Path | None = None) -> Path:
        if model_root is not None:
            return Path(model_root).expanduser().resolve()

        env_root = os.getenv("OCEANEMBED_MODEL_ROOT")
        if env_root:
            return Path(env_root).expanduser().resolve()

        root = Path(__file__).resolve().parents[3] / "model" / "PS66-Ocean-Model"
        return root.resolve()

    def _load_ps66_runtime(self):
        if self._tf_model is not None:
            return self._tf_model

        model_dir = self.model_root
        src_dir = model_dir / "src"
        if str(model_dir) not in sys.path:
            sys.path.insert(0, str(model_dir))
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        try:
            from src import data as ps66_data
            from src.model import OceanModel
        except Exception as exc:  # pragma: no cover - import failure is a real runtime block
            raise RuntimeError(
                "The PS66 TensorFlow runtime could not be imported. "
                "Expected the trained model at "
                f"{model_dir / 'weights' / 'model_2020.weights.h5'}"
            ) from exc

        weights_path = model_dir / "weights" / "model_2020.weights.h5"
        if not weights_path.exists():
            raise FileNotFoundError(f"PS66 weights not found at {weights_path}.")

        X, Y, stats, channels = ps66_data.load_arrays("2020")
        if X.shape[1] != len(self.input_channels):
            raise ValueError(
                "PS66 model input mismatch: expected "
                f"{len(self.input_channels)} channels, got {X.shape[1]}."
            )

        Xn, _ = ps66_data.normalize(X, Y, stats, channels)
        model = OceanModel(cin=X.shape[1], D=256, Z=Y.shape[1])
        _ = model(tf.zeros([1, X.shape[1], X.shape[2], X.shape[3]], dtype=tf.float32))
        model.load_weights(str(weights_path))

        self._tf_model = model
        self._sample_cache = (X, Y, stats, list(channels))
        self._sample_dates = list(MODEL_AVAILABLE_DATES)
        self._tf_model_imports = (ps66_data, model)
        return self._tf_model

    def _load_sample_arrays(self) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], list[str]]:
        if self._sample_cache is not None:
            return self._sample_cache

        self._load_ps66_runtime()
        assert self._sample_cache is not None
        return self._sample_cache

    def _model_sample_dates(self) -> list[date]:
        if self._sample_dates is None:
            self._load_ps66_runtime()
        assert self._sample_dates is not None
        return self._sample_dates

    def _sample_depth_index(self, depth: float) -> int:
        if depth not in STANDARD_DEPTHS:
            valid_depths = ", ".join(str(value) for value in STANDARD_DEPTHS)
            raise ValueError(f"Requested depth {depth} is not one of the standard profile depths: {valid_depths}.")
        return STANDARD_DEPTHS.index(depth)

    def _date_index_for_request(self, target_date: date) -> int:
        sample_dates = self._model_sample_dates()
        if target_date not in sample_dates:
            raise ValueError(
                f"Requested date {target_date.isoformat()} is outside the supported model range: "
                f"{MODEL_DATE_START.isoformat()} to {MODEL_DATE_END.isoformat()}."
            )
        return sample_dates.index(target_date)

    def _predict_field_for_date(self, target_date: date) -> np.ndarray:
        X, Y, stats, channels = self._load_sample_arrays()
        date_index = self._date_index_for_request(target_date)
        x_input = np.nan_to_num(X[date_index], nan=0.0).astype(np.float32)

        x_norm = x_input.copy()
        for i, channel_name in enumerate(channels):
            channel_key = str(channel_name)
            mean = float(stats[f"x_mean_{channel_key}"])
            std = float(stats[f"x_std_{channel_key}"]) + 1e-6
            x_norm[i] = (x_input[i] - mean) / std

        model = self._load_ps66_runtime()
        batched = np.expand_dims(x_norm, axis=0)
        prediction, _ = model(tf.convert_to_tensor(batched, dtype=tf.float32), training=False)
        prediction = prediction.numpy()[0]
        denormalized = prediction * (float(stats["y_std"]) + 1e-6) + float(stats["y_mean"])
        return np.where(np.isfinite(Y[date_index]), denormalized, np.nan)

    def _output_field(self, request: ModelInferenceInput) -> np.ndarray:
        field = self._predict_field_for_date(request.date)

        if request.depth is not None:
            depth_index = self._sample_depth_index(request.depth)
            return field[depth_index]

        return field[0]

    def _subset_field_values(
        self,
        values: np.ndarray,
        *,
        latitude_min: float | None = None,
        latitude_max: float | None = None,
        longitude_min: float | None = None,
        longitude_max: float | None = None,
    ) -> np.ndarray:
        if values.ndim != 2:
            return values

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

        return values[lat_start : lat_end + 1, lon_start : lon_end + 1]

    def infer_temperature_field(
        self,
        request: ModelInferenceInput,
    ) -> ModelTemperaturePrediction:
        field = self._predict_field_for_date(request.date)
        depth_index = self._sample_depth_index(request.depth) if request.depth is not None else 0
        array = field[depth_index]

        values = [
            [None if not np.isfinite(float(value)) else float(value) for value in row]
            for row in array.tolist()
        ]

        return ModelTemperaturePrediction(
            date=request.date,
            depth=request.depth,
            values=values,
            metadata={
                "model": "PS66 OceanEmbed (trained weights)",
                "input_channels": self.input_channels,
                "output_depths": [float(depth) for depth in STANDARD_DEPTHS],
                "grid_shape": list(self.grid_shape),
                "source": "PS66 Keras model via model_2020.weights.h5",
            },
        )

    def _nearest_valid_grid_point(self, field: np.ndarray, latitude: float, longitude: float) -> tuple[int, int]:
        lat_index = _nearest_grid_index(
            latitude,
            MODEL_LATITUDE_MIN,
            MODEL_LATITUDE_MAX,
            MODEL_LATITUDE_RESOLUTION,
            field.shape[1],
        )
        lon_index = _nearest_grid_index(
            longitude,
            MODEL_LONGITUDE_MIN,
            MODEL_LONGITUDE_MAX,
            MODEL_LONGITUDE_RESOLUTION,
            field.shape[2],
        )

        max_radius = max(field.shape[1], field.shape[2])
        for radius in range(max_radius + 1):
            row_min = max(0, lat_index - radius)
            row_max = min(field.shape[1] - 1, lat_index + radius)
            col_min = max(0, lon_index - radius)
            col_max = min(field.shape[2] - 1, lon_index + radius)

            candidates: list[tuple[int, int]] = []
            for row in range(row_min, row_max + 1):
                for col in range(col_min, col_max + 1):
                    if abs(row - lat_index) + abs(col - lon_index) <= radius:
                        candidates.append((row, col))

            for row, col in candidates:
                if np.all(np.isfinite(field[:, row, col])):
                    return row, col

        raise ValueError(
            f"No finite PS66 model cell found near latitude={latitude}, longitude={longitude} for the requested date."
        )

    def infer_profile(
        self,
        request: ModelInferenceInput,
    ) -> ModelProfilePrediction:
        if request.latitude is None or request.longitude is None:
            raise ValueError("Profile inference requires both latitude and longitude.")

        field = self._predict_field_for_date(request.date)
        lat_index, lon_index = self._nearest_valid_grid_point(field, request.latitude, request.longitude)
        profile = field[:, lat_index, lon_index]
        temperatures = [None if not np.isfinite(float(value)) else float(value) for value in profile.tolist()]
        if any(temp is None for temp in temperatures):
            raise ValueError(
                f"PS66 model profile returned non-finite values for latitude={request.latitude}, longitude={request.longitude}, date={request.date.isoformat()}."
            )
        return ModelProfilePrediction(temperatures=temperatures)

    def point_temperature(
        self,
        *,
        latitude: float,
        longitude: float,
        date: date,
        depth: float,
    ) -> float | None:
        field = self._predict_field_for_date(date)
        depth_index = self._sample_depth_index(depth)
        lat_index, lon_index = self._nearest_valid_grid_point(field, latitude, longitude)
        value = float(field[depth_index, lat_index, lon_index])
        if not np.isfinite(value):
            return None
        return value


if __name__ == "__main__":
    model = OceanEmbedModelAdapter()
    print(model.model_root)
    print(model.input_channels)
    print(model.output_depths)
