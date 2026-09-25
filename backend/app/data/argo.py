"""ARGO data-access placeholder module.

This module is intentionally not implemented until a real ARGO dataset or file is present
in the repository. It exists to define the retrieval interface expected by future service
logic without returning fake scientific values.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.data.interfaces import ArgoDataSource


class ArgoDataAccessor(ArgoDataSource):
    """Placeholder ARGO accessor that raises a clear error until data is available."""

    def is_available(self) -> bool:
        return False

    def get_profile_by_id(self, profile_id: str) -> dict[str, Any]:
        raise NotImplementedError(
            "ARGO profile retrieval is not implemented yet. Provide a real dataset or file path."
        )

    def get_validation_observations(
        self,
        *,
        date: date | None = None,
        depth: float | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "ARGO validation observation loading is not implemented yet. Provide a dataset or loader."
        )
