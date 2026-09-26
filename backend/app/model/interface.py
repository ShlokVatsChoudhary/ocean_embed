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


class PlaceholderOceanEmbedModel(OceanEmbedModel):
    """Placeholder implementation that intentionally raises until a trained model is supplied."""

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
