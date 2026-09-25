from __future__ import annotations

from datetime import date as Date

from pydantic import BaseModel, Field


class MetadataRequest(BaseModel):
    """Reserved empty request model for metadata queries."""


class MetadataResponse(BaseModel):
    """Project and dataset metadata exposed by the API."""

    dataset_name: str = "OceanEmbed"
    project: str = "OceanEmbed"
    description: str = "Subsurface ocean temperature reconstruction backend skeleton."
    available_dates: list[str] = Field(default_factory=list)
    available_depths: list[float] = Field(default_factory=list)
    spatial_resolution: dict[str, float | str] = Field(
        default_factory=lambda: {
            "latitude": 0.25,
            "longitude": 0.25,
            "units": "degrees",
        }
    )
    supported_variables: list[str] = Field(default_factory=lambda: ["temperature"])


class TemperatureRequest(BaseModel):
    """Query parameters for a bulk temperature field request."""

    date: Date
    depth: float
    latitude_min: float | None = None
    latitude_max: float | None = None
    longitude_min: float | None = None
    longitude_max: float | None = None


class TemperatureFieldMetadata(BaseModel):
    """Metadata describing a temperature field response."""

    date: Date
    depth: float
    variable: str = "temperature"
    units: str = "degC"
    spatial_resolution: dict[str, float | str] = Field(
        default_factory=lambda: {
            "latitude": 0.25,
            "longitude": 0.25,
            "units": "degrees",
        }
    )
    bounds: dict[str, float | None] = Field(
        default_factory=lambda: {
            "latitude_min": None,
            "latitude_max": None,
            "longitude_min": None,
            "longitude_max": None,
        }
    )


class TemperatureResponse(BaseModel):
    """A minimal temperature-field response with grid-level values."""

    metadata: TemperatureFieldMetadata
    values: list[list[float | None]] = Field(default_factory=list)


class ProfileRequest(BaseModel):
    """Query parameters for a depth profile at a single point."""

    latitude: float
    longitude: float
    date: Date


class ProfilePoint(BaseModel):
    """A single point in a depth-wise temperature profile."""

    depth: float
    temperature: float | None = None
    units: str = "degC"


class ProfileResponse(BaseModel):
    """Depth-wise temperature profile for a point in time and space."""

    latitude: float
    longitude: float
    date: Date
    profile: list[ProfilePoint] = Field(default_factory=list)


class ComparisonRequest(BaseModel):
    """Query parameters for a location-specific comparison between model and reference data."""

    latitude: float
    longitude: float
    date: Date
    depth: float


class ComparisonResponse(BaseModel):
    """A minimal comparison of OceanEmbed and GLORYS temperatures."""

    latitude: float
    longitude: float
    date: Date
    depth: float
    oceanembed_temperature: float | None = None
    glorys_temperature: float | None = None
    difference: float | None = None
    unit: str = "degC"


class ValidationRequest(BaseModel):
    """Query parameters for retrieving validation information for ARGO observations."""

    date: Date | None = None
    depth: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    argo_profile_id: str | None = None


class ValidationObservation(BaseModel):
    """A single observation comparison between model and ARGO/reference temperature."""

    latitude: float | None = None
    longitude: float | None = None
    date: Date | None = None
    depth: float | None = None
    oceanembed_temperature: float | None = None
    observed_temperature: float | None = None
    difference: float | None = None
    source: str = "ARGO"


class ValidationMetrics(BaseModel):
    """Summary validation metrics for a set of observations."""

    rmse: float | None = None
    mae: float | None = None
    bias: float | None = None
    n_observations: int | None = None


class ValidationResponse(BaseModel):
    """Validation results for ARGO observations or other reference data."""

    dataset: str = "ARGO"
    metrics: ValidationMetrics = Field(default_factory=ValidationMetrics)
    observations: list[ValidationObservation] = Field(default_factory=list)
