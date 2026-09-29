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
    glorys_status: str = "bundled_sample"
    glorys_provenance: str = "Bundled sample data is being used; this is not live GLORYS data."
    argo_status: str = "unavailable"
    argo_provenance: str = "ARGO validation data is unavailable in this environment."
    argo_available_dates: list[str] = Field(default_factory=list)
    model_available_dates: list[str] = Field(default_factory=list)
    model_name: str = "PS66 OceanEmbed"
    model_parameter_count: int | None = None
    evaluation_note: str = (
        "Metrics are reported on a common evaluation mask. Near-surface and deep layers are "
        "reported separately from the thermocline."
    )


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
    glorys_status: str = "bundled_sample"
    glorys_provenance: str = "Bundled sample data is being used; this is not live GLORYS data."
    unit: str = "degC"


class CoverageResponse(BaseModel):
    """Fraction of the model grid carrying a finite value for a date and depth."""

    date: Date
    depth: float
    grid_shape: list[int] = Field(default_factory=lambda: [101, 241])
    valid_cells: int
    total_cells: int
    coverage: float
    note: str = (
        "Coverage is the fraction of grid cells with a finite value. It is a data-availability "
        "measure, not a model-confidence score."
    )


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
    """Summary validation metrics for a set of observations.

    ``rmse``/``mae``/``bias`` cover every evaluated depth. The banded figures are
    reported separately because an unweighted average over all depths is dominated
    by the slowly varying deep layers and flatters a model that is weak in the
    thermocline.
    """

    rmse: float | None = None
    mae: float | None = None
    bias: float | None = None
    correlation: float | None = None
    n_observations: int | None = None
    rmse_ge50: float | None = None
    rmse_thermocline: float | None = None
    n_cells_per_day: int | None = None


class DepthMetrics(BaseModel):
    """Validation metrics for one standard depth level."""

    depth: float
    rmse: float | None = None
    mae: float | None = None
    bias: float | None = None
    correlation: float | None = None
    n: int = 0


class ValidationSummary(BaseModel):
    """Headline validation summary shown on the validation page."""

    status: str = "unavailable"
    provenance: str = ""
    reference: str = "ARGO"
    reference_kind: str = ""
    date_range: str = ""
    n_profiles: int | None = None
    n_observations: int | None = None
    mean_error: float | None = None
    correlation: float | None = None
    model_version: str = ""
    caveat: str = ""


class ScatterPoint(BaseModel):
    """One model-vs-reference pair for the predicted/observed scatter plot."""

    predicted: float
    observed: float
    depth: float


class ValidationResponse(BaseModel):
    """Validation results for ARGO observations or other reference data."""

    dataset: str = "ARGO"
    status: str = "unavailable"
    provenance: str = ""
    reference_kind: str = ""
    metrics: ValidationMetrics = Field(default_factory=ValidationMetrics)
    per_depth: list[DepthMetrics] = Field(default_factory=list)
    summary: ValidationSummary = Field(default_factory=ValidationSummary)
    scatter: list[ScatterPoint] = Field(default_factory=list)
    observations: list[ValidationObservation] = Field(default_factory=list)


class ArgoFloat(BaseModel):
    """An ARGO-observed grid cell that has data on the requested date."""

    id: str
    lat: float
    lon: float
    n_levels: int
    depth_min: float | None = None
    depth_max: float | None = None
    source: str = "ARGO"


class ArgoFloatResponse(BaseModel):
    """ARGO cell locations for a date, used to draw markers and a profile list."""

    date: Date
    status: str = "unavailable"
    provenance: str = ""
    argo_date: Date | None = None
    time_offset_days: int | None = None
    floats: list[ArgoFloat] = Field(default_factory=list)


class AnomalyAlert(BaseModel):
    """A location where model and reference disagree most strongly."""

    id: str
    lat: float
    lon: float
    date: Date
    depth: float
    difference: float
    direction: str
    message: str


class AnomalyAlertResponse(BaseModel):
    """Largest model-vs-reference disagreements, surfaced as review candidates."""

    status: str = "unavailable"
    provenance: str = ""
    alerts: list[AnomalyAlert] = Field(default_factory=list)
