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
    #: Which dataset produced this field. Left unset for the model's own output and
    #: set to the reference source for /api/reference, so a reference field can never
    #: be mistaken for a model prediction (or for validation data).
    source: str | None = None


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
    requested_latitude: float | None = None
    requested_longitude: float | None = None
    grid_latitude: float | None = None
    grid_longitude: float | None = None
    glorys_profile: list[ProfilePoint] = Field(default_factory=list)
    argo_profile: list[ProfilePoint] = Field(default_factory=list)
    argo_date: Date | None = None
    time_offset_days: int | None = None
    provenance: str = ""


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

    # Grid transparency. A requested coordinate is snapped to the nearest grid cell, so the
    # response reports both what was asked for and what was actually read.
    requested_latitude: float | None = None
    requested_longitude: float | None = None
    #: The cell the value came from. Over a shelf sea the nearest cell may lack a full-depth
    #: column, so this can differ from ``nearest_grid_*``.
    grid_latitude: float | None = None
    grid_longitude: float | None = None
    #: The grid cell closest to the request, regardless of data availability.
    nearest_grid_latitude: float | None = None
    nearest_grid_longitude: float | None = None
    #: Distance in degrees between the two, i.e. how far the value had to travel. Non-zero means
    #: the requested cell had no complete profile.
    offset_degrees: float | None = None
    grid_resolution_degrees: float = 0.25

    # State A: model and reference both available.
    # State B: model available, reference unavailable. A legitimate missing reference,
    #          explicitly not an error.
    # State C: model unavailable. No fallback scientific numbers are produced.
    state: str = "model_unavailable"
    state_message: str = "OceanEmbed prediction unavailable at this location, depth and date."


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


# --------------------------------------------------------------- ocean hazards
# Derived cyclone-relevant diagnostics. These are the quantities a warning centre
# uses; the raw temperature field is the input to them, not the product.

class HazardFieldResponse(BaseModel):
    """A single hazard diagnostic as a gridded field."""

    date: Date
    variable: str
    label: str
    unit: str
    values: list[list[float | None]]
    grid_shape: list[int] = Field(default_factory=lambda: [101, 241])
    bounds: dict[str, float] = Field(default_factory=dict)
    stats: dict[str, float | int | None] = Field(default_factory=dict)
    category_breaks: list[float] = Field(default_factory=list)
    category_labels: list[str] = Field(default_factory=list)
    min_valid_depth_m: float = 300.0
    provenance: str = ""
    caveat: str = ""


class HazardSummaryItem(BaseModel):
    """Summary statistics for one hazard diagnostic."""

    variable: str
    label: str
    unit: str
    minimum: float | None = None
    median: float | None = None
    maximum: float | None = None
    valid_cells: int = 0
    total_cells: int = 0


class HazardSummaryResponse(BaseModel):
    """Every hazard diagnostic for one day, plus the cyclone-relevant counts."""

    date: Date
    status: str = "unavailable"
    metrics: list[HazardSummaryItem] = Field(default_factory=list)
    valid_cells: int = 0
    total_cells: int = 0
    coverage: float = 0.0
    favourable_cells: int = 0
    rapid_intensification_cells: int = 0
    min_valid_depth_m: float = 300.0
    provenance: str = ""
    caveat: str = ""
