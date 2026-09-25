"""GLORYS data-access placeholder module.

This module intentionally raises NotImplementedError until a real GLORYS dataset or file is
made available in the repository. It only defines the interface expected by the service layer.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.data.interfaces import GlorysDataSource


class GlorysDataAccessor(GlorysDataSource):
    """Placeholder GLORYS accessor that raises a clear error until data is available."""

    def is_available(self) -> bool:
        return False

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
        raise NotImplementedError(
            "GLORYS temperature field loading is not implemented yet. Provide a dataset or loader."
        )

    def get_point_temperature(
        self,
        *,
        latitude: float,
        longitude: float,
        target_date: date,
        depth: float,
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "GLORYS point temperature retrieval is not implemented yet. Provide a dataset or loader."
        )
