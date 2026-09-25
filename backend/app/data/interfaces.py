"""Abstract data-access interfaces for OceanEmbed scientific data sources.

These interfaces define the required retrieval contracts for future ARGO, GLORYS, and
other data sources. They intentionally do not implement any dataset loading or parsing
logic until real data files are available in the repository.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any


class DataSource(ABC):
    """Base interface for a scientific-data source."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the source has a usable dataset configured."""


class ArgoDataSource(DataSource):
    """Interface for retrieving ARGO profile observations."""

    @abstractmethod
    def get_profile_by_id(self, profile_id: str) -> dict[str, Any]:
        """Return an ARGO profile by profile identifier."""

    @abstractmethod
    def get_validation_observations(
        self,
        *,
        date: date | None = None,
        depth: float | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> list[dict[str, Any]]:
        """Return ARGO validation observations matching the provided filters."""


class GlorysDataSource(DataSource):
    """Interface for retrieving GLORYS reference fields."""

    @abstractmethod
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
        """Return reference GLORYS temperature data for the requested field."""

    @abstractmethod
    def get_point_temperature(
        self,
        *,
        latitude: float,
        longitude: float,
        target_date: date,
        depth: float,
    ) -> dict[str, Any]:
        """Return a pointwise GLORYS temperature value for a location and depth."""


class DataLoader(ABC):
    """General-purpose loader interface for scientific datasets and metadata."""

    @abstractmethod
    def load_metadata(self) -> dict[str, Any]:
        """Return metadata about the dataset or project configuration."""

    @abstractmethod
    def load_available_dates(self) -> list[str]:
        """Return date strings available in the configured dataset."""

    @abstractmethod
    def load_available_depths(self) -> list[float]:
        """Return depths available in the configured dataset."""

    @abstractmethod
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
        """Return a temperature field by date/depth and optional geographic bounds."""
