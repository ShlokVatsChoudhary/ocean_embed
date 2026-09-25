"""General dataset loader placeholder.

This module defines a general interface for loading dataset metadata and temperature fields,
without performing any real scientific loading. When actual files become available, the
implementation can be replaced without changing the service API.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.data.interfaces import DataLoader


class ScientificDataLoader(DataLoader):
    """Placeholder data loader that raises a clear error until real datasets exist."""

    def load_metadata(self) -> dict[str, Any]:
        raise NotImplementedError(
            "Dataset metadata loading is not implemented yet. Provide a real metadata source."
        )

    def load_available_dates(self) -> list[str]:
        raise NotImplementedError(
            "Available-date loading is not implemented yet. Provide a real dataset or file path."
        )

    def load_available_depths(self) -> list[float]:
        raise NotImplementedError(
            "Available-depth loading is not implemented yet. Provide a real dataset or file path."
        )

    def load_temperature_field(
        self,
        *,
        target_date: date,
        depth: float,
        latitude_min: float | None = None,
        latitude_max: float | None = None,
        longitude_min: float | None = None,
        longitude_max: float | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "Temperature field loading is not implemented yet. Provide a real scientific dataset."
        )
