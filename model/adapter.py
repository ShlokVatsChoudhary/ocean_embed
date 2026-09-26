"""OceanEmbed v1 — TensorFlow inference adapter.

Implements the backend contract declared in ``backend/app/model/interface.py``
(the ``OceanEmbedModel`` ABC) using the trained encoder–decoder shipped in this
package.

The adapter can run in two ways:

* **inside the backend** — it imports ``app.model.interface`` so it *is* an
  ``OceanEmbedModel`` and returns the backend's pydantic schemas;
* **standalone** — if that import is unavailable it falls back to lightweight
  dataclasses with the same attribute names, so it can be unit-tested on its own.

Typical use inside the backend::

    from model.adapter import OceanEmbedV1

    model = OceanEmbedV1()                      # loads weights once
    profile = model.infer_profile(request)      # -> .temperatures (15 floats)
    field   = model.infer_temperature_field(req)  # -> .values (2-D list)

Notes
-----
* Inputs come from the shipped ``input_cache/X_2020Q1.npz`` (surface channels
  for 2020-01-01 … 2020-03-31). Requests outside that window are served from the
  **nearest available day** and the served date is reported in the field
  metadata (``served_date`` vs ``requested_date``).
* The model predicts **normalised** temperature; values are de-normalised back
  to °C before being returned.
* Land / below-seabed cells are NaN and are serialised as ``None``.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from . import config
from .net import OceanModel

# --------------------------------------------------------------------------
# Backend bridge (optional)
# --------------------------------------------------------------------------
try:  # pragma: no cover - depends on layout
    from app.model.interface import (  # type: ignore
        ModelInferenceInput,
        ModelProfilePrediction,
        ModelTemperaturePrediction,
        OceanEmbedModel,
    )

    _BACKEND = True
except Exception:  # standalone
    _BACKEND = False

    @dataclass
    class ModelInferenceInput:  # type: ignore[no-redef]
        date: dt.date
        latitude: Optional[float] = None
        longitude: Optional[float] = None
        depth: Optional[float] = None
        latitude_min: Optional[float] = None
        latitude_max: Optional[float] = None
        longitude_min: Optional[float] = None
        longitude_max: Optional[float] = None

    @dataclass
    class ModelProfilePrediction:  # type: ignore[no-redef]
        temperatures: list = field(default_factory=list)

    @dataclass
    class ModelTemperaturePrediction:  # type: ignore[no-redef]
        date: dt.date
        depth: Optional[float] = None
        values: list = field(default_factory=list)
        metadata: dict = field(default_factory=dict)

    class OceanEmbedModel:  # type: ignore[no-redef]
        """Duck-typed stand-in for the backend ABC when running standalone."""


def _nearest(levels, target: float) -> int:
    """Index of the entry in ``levels`` closest to ``target``."""
    return int(np.argmin([abs(float(v) - float(target)) for v in levels]))


def _as_list(arr: np.ndarray) -> list:
    """2-D float array -> list of lists with NaN mapped to ``None``."""
    out: list = []
    for row in np.asarray(arr, dtype="float64"):
        out.append([None if not np.isfinite(v) else float(v) for v in row])
    return out


class OceanEmbedV1(OceanEmbedModel):
    """Trained OceanEmbed encoder–decoder behind the backend's model contract."""

    def __init__(
        self,
        weights=config.WEIGHTS,
        stats=config.STATS,
        cache=config.CACHE,
        *,
        strict_dates: bool = False,
    ):
        import tensorflow as tf  # imported lazily so the module stays importable

        self.tf = tf
        self.strict_dates = strict_dates

        # ---- normalisation statistics -------------------------------------
        st = dict(np.load(stats, allow_pickle=True))
        self.stats = st

        # ---- cached surface inputs ----------------------------------------
        bundle = np.load(cache, allow_pickle=True)
        self.X = bundle["X"]                       # (T, C, NY, NX) float16
        self.dates = [str(d) for d in bundle["dates"]]
        self.channels = [str(c) for c in bundle["channels"]]
        # static fields: land mask + seabed depth (metres)
        self.ocean = bundle["ocean"].astype(bool)  # (NY, NX)
        self.bathy = bundle["bathy"].astype("float32")  # (NY, NX), NaN on land

        # ---- model ---------------------------------------------------------
        cin = len(self.channels)
        self.model = OceanModel(
            cin=cin,
            D=config.LATENT_DIM,
            Z=len(config.DEPTHS),
            widths=config.WIDTHS,
        )
        # Build variables by a single forward pass (the model has no build()
        # override — see the training repo's notes).
        self.model(
            tf.zeros([1, cin, config.NY, config.NX], dtype=tf.float32),
            training=False,
        )
        self.model.load_weights(str(weights))

    # ------------------------------------------------------------------ utils
    def available_dates(self) -> list[str]:
        """ISO dates the shipped input cache can serve."""
        return list(self.dates)

    def _index_for(self, day: dt.date) -> int:
        key = day.isoformat()
        if key in self.dates:
            return self.dates.index(key)
        if self.strict_dates:
            raise ValueError(
                f"Date {key} is outside the available range "
                f"{self.dates[0]} … {self.dates[-1]}."
            )
        # nearest available day
        avail = [dt.date.fromisoformat(d) for d in self.dates]
        return int(np.argmin([abs((a - day).days) for a in avail]))

    def _cells(self, lat: float, lon: float) -> tuple[int, int]:
        return _nearest(config.LAT, lat), _nearest(config.LON, lon)

    def _predict_day(self, day: dt.date) -> tuple[np.ndarray, int]:
        """Return (temperature °C ``(Z, NY, NX)``, cache index) for one day."""
        idx = self._index_for(day)
        x = self.X[idx].astype("float32")          # (C, NY, NX)
        x = x.copy()
        for i, c in enumerate(self.channels):
            mean = self.stats[f"x_mean_{c}"]
            std = self.stats[f"x_std_{c}"] + 1e-6
            x[i] = (x[i] - mean) / std
        # land/missing cells are NaN in the cache; the model was trained with
        # them zero-filled (see data.make_dataset) and NaN would otherwise
        # propagate through every convolution.
        x = np.nan_to_num(x, nan=0.0)
        pred, _ = self.model(x[None], training=False)   # (1, Z, NY, NX)
        pred = pred[0].numpy()
        # de-normalise to °C
        pred = pred * float(self.stats["y_std"]) + float(self.stats["y_mean"])
        return pred, idx

    # ----------------------------------------------------------- inference
    def infer_profile(self, request: ModelInferenceInput) -> ModelProfilePrediction:
        """Vertical profile (15 standard depths) at a point."""
        if request.latitude is None or request.longitude is None:
            raise ValueError("Point profile inference requires latitude and longitude.")
        pred, _ = self._predict_day(request.date)
        iy, ix = self._cells(request.latitude, request.longitude)
        if not self.ocean[iy, ix]:
            return ModelProfilePrediction(temperatures=[None] * len(config.DEPTHS))
        seabed = float(self.bathy[iy, ix])
        column = pred[:, iy, ix]
        temps = [
            None if (not np.isfinite(v) or z > seabed) else float(v)
            for z, v in zip(config.DEPTHS, column)
        ]
        return ModelProfilePrediction(temperatures=temps)

    def infer_temperature_field(
        self, request: ModelInferenceInput
    ) -> ModelTemperaturePrediction:
        """Horizontal temperature field at one depth over an optional bbox.

        ``values`` is row-major with **rows ordered by increasing latitude**
        (5 °N → 30 °N) and **columns by increasing longitude** (45 °E → 105 °E).
        """
        pred, idx = self._predict_day(request.date)

        depth = request.depth if request.depth is not None else config.DEPTHS[0]
        iz = _nearest(config.DEPTHS, depth)
        zd = float(config.DEPTHS[iz])
        field = pred[iz].copy()                     # (NY, NX)
        # mask land and cells whose seabed is shallower than the requested depth
        field[~(self.ocean & (self.bathy >= zd))] = np.nan

        # geographic window
        lat_min = request.latitude_min if request.latitude_min is not None else config.LAT_MIN
        lat_max = request.latitude_max if request.latitude_max is not None else config.LAT_MAX
        lon_min = request.longitude_min if request.longitude_min is not None else config.LON_MIN
        lon_max = request.longitude_max if request.longitude_max is not None else config.LON_MAX

        lat_i = [i for i, v in enumerate(config.LAT) if lat_min <= v <= lat_max]
        lon_i = [i for i, v in enumerate(config.LON) if lon_min <= v <= lon_max]
        sub = field[np.ix_(lat_i, lon_i)] if lat_i and lon_i else np.empty((0, 0))

        served = dt.date.fromisoformat(self.dates[idx])
        meta = {
            "variable": "temperature",
            "units": "degC",
            "requested_depth": float(depth),
            "served_depth": zd,
            "served_date": served.isoformat(),
            "requested_date": request.date.isoformat(),
            "grid_shape": [len(lat_i), len(lon_i)],
            "axis_order": "rows=latitude(ascending), cols=longitude(ascending)",
            "latitudes": [config.LAT[i] for i in lat_i],
            "longitudes": [config.LON[i] for i in lon_i],
            "source": "OceanEmbed v1 (TensorFlow encoder-decoder)",
        }
        return ModelTemperaturePrediction(
            date=served,
            depth=zd,
            values=_as_list(sub),
            metadata=meta,
        )

    # ------------------------------------------------- convenience helpers
    def infer_point(
        self, latitude: float, longitude: float, day: dt.date, depth: float
    ) -> Optional[float]:
        """Single temperature value at (lat, lon, depth, date)."""
        pred, _ = self._predict_day(day)
        iy, ix = self._cells(latitude, longitude)
        iz = _nearest(config.DEPTHS, depth)
        if not self.ocean[iy, ix] or config.DEPTHS[iz] > float(self.bathy[iy, ix]):
            return None
        v = pred[iz, iy, ix]
        return None if not np.isfinite(v) else float(v)


__all__ = [
    "OceanEmbedV1",
    "ModelInferenceInput",
    "ModelProfilePrediction",
    "ModelTemperaturePrediction",
    "OceanEmbedModel",
    "_BACKEND",
]
