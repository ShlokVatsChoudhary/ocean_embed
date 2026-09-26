"""Thin integration boundary for the future OceanEmbed ML model.

This layer defines the contract the backend services will eventually use to ask the ML
model for temperature predictions. It does not implement training or inference; instead,
it makes the backend contract explicit and easy to replace when Friend 1 provides a real
trained artifact.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date as Date
from typing import Any

from pydantic import BaseModel, Field

from app.core.constants import (
    MODEL_AVAILABLE_DATES,
    MODEL_GRID_COLS,
    MODEL_GRID_ROWS,
    MODEL_LATITUDE_MAX,
    MODEL_LATITUDE_MIN,
    MODEL_LATITUDE_RESOLUTION,
    MODEL_LONGITUDE_MAX,
    MODEL_LONGITUDE_MIN,
    MODEL_LONGITUDE_RESOLUTION,
    STANDARD_DEPTHS,
)

class ModelInferenceInput(BaseModel):
    """Input payload shared across the future ML inference layer.

    This is intentionally broad enough to cover temperature-field and profile use cases
    without binding the backend to a specific model implementation.
    """

    date: Date
    latitude: float | None = None
    longitude: float | None = None
    depth: float | None = None
    latitude_min: float | None = None
    latitude_max: float | None = None
    longitude_min: float | None = None
    longitude_max: float | None = None


class ModelTemperaturePrediction(BaseModel):
    """Structured temperature field result from the ML model."""

    date: Date
    depth: float | None = None
    values: list[list[float | None]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelProfilePrediction(BaseModel):
    """Raw vertical temperature prediction returned by the ML model."""

    temperatures: list[float | None]


class OceanEmbedModel(ABC):
    """Abstract model interface for OceanEmbed inference."""

    @abstractmethod
    def infer_temperature_field(
        self,
        request: ModelInferenceInput,
    ) -> ModelTemperaturePrediction:
        """Return a temperature field prediction for the given request."""

    @abstractmethod
    def infer_profile(
        self,
        request: ModelInferenceInput,
    ) -> ModelProfilePrediction:
        """Return a vertical profile prediction for the given point request."""

    def available_dates(self) -> list[Date]:
        """Return the dates with available model data."""
        return list(MODEL_AVAILABLE_DATES)

    def point_temperature(
        self,
        *,
        latitude: float,
        longitude: float,
        date: Date,
        depth: float,
    ) -> float | None:
        """Return a single temperature value for a nearest-grid-cell lookup."""
        request = ModelInferenceInput(date=date, latitude=latitude, longitude=longitude, depth=depth)
        prediction = self.infer_temperature_field(request)
        if not prediction.values:
            return None

        row_count = len(prediction.values)
        col_count = len(prediction.values[0]) if row_count else 0
        row_index = self._nearest_grid_index(
            latitude,
            MODEL_LATITUDE_MIN,
            MODEL_LATITUDE_MAX,
            MODEL_LATITUDE_RESOLUTION,
            row_count,
        )
        col_index = self._nearest_grid_index(
            longitude,
            MODEL_LONGITUDE_MIN,
            MODEL_LONGITUDE_MAX,
            MODEL_LONGITUDE_RESOLUTION,
            col_count,
        )

        if row_index < row_count and col_index < col_count:
            return prediction.values[row_index][col_index]
        return None

    @staticmethod
    def _nearest_grid_index(value: float, min_value: float, max_value: float, resolution: float, length: int) -> int:
        if value <= min_value:
            return 0
        if value >= max_value:
            return max(length - 1, 0)
        fraction = (max_value - value) / resolution
        return min(max(int(round(fraction)), 0), length - 1)


class PlaceholderOceanEmbedModel(OceanEmbedModel):
    """Placeholder model that keeps the backend contract without pretending real inference exists."""

    def infer_temperature_field(
        self,
        request: ModelInferenceInput,
    ) -> ModelTemperaturePrediction:
        raise NotImplementedError(
            "OceanEmbed model inference is not implemented yet. Provide a trained model artifact."
        )

    def infer_profile(
        self,
        request: ModelInferenceInput,
    ) -> ModelProfilePrediction:
        raise NotImplementedError(
            "OceanEmbed profile inference is not implemented yet. Provide a trained model artifact."
        )
