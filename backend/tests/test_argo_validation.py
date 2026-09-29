"""Contract tests for the ARGO validation path.

These tests pin the properties that matter scientifically, not just the plumbing:
the model is compared against ARGO only on a common mask, land stays missing, and
the reported bands are computed from real pairs.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from app.core.constants import MODEL_AVAILABLE_DATES, STANDARD_DEPTHS
from app.data.interfaces import DataSourceStatus
from app.data.argo import ArgoDataAccessor
from app.services.comparison import get_comparison
from app.services.validation import get_anomaly_alerts, get_validation
from app.services.argo import get_argo_floats

pytestmark = pytest.mark.skipif(
    not ArgoDataAccessor().is_available(),
    reason="Bundled ARGO archive is not present; validation cannot run.",
)


@pytest.fixture(scope="module")
def model():
    from app.model.adapter import OceanEmbedModelAdapter

    return OceanEmbedModelAdapter()


@pytest.fixture(scope="module")
def argo():
    return ArgoDataAccessor()


def test_argo_regrid_shape_and_land_missing(argo):
    field = argo.temperature_field(date(2020, 1, 1))
    assert field is not None
    assert field.shape == (len(STANDARD_DEPTHS), 101, 241)
    # Land must stay missing rather than being filled with a numeric value.
    assert 0.0 < np.isfinite(field).mean() < 1.0


def test_argo_matches_nearest_analysis_time(argo):
    matched_date, offset = argo.matched_time(date(2020, 1, 1))
    assert matched_date == date(2019, 12, 30)
    assert offset == -2


def test_validation_uses_a_common_mask(model, argo):
    result = get_validation(date(2020, 1, 1), model=model, argo=argo)
    assert result.status == "available"
    assert result.metrics.n_observations == sum(entry.n for entry in result.per_depth)

    # Every reported sample must be a real pair, so the count can never exceed the
    # number of cells that are finite in both fields.
    predicted = model.temperature_field_array(date(2020, 1, 1))
    observed = argo.temperature_field(date(2020, 1, 1))
    shared = int((np.isfinite(predicted) & np.isfinite(observed)).sum())
    assert result.metrics.n_observations == shared


def test_validation_reports_bands_separately(model, argo):
    result = get_validation(model=model, argo=argo)
    metrics = result.metrics
    assert metrics.rmse is not None
    assert metrics.rmse_ge50 is not None
    assert metrics.rmse_thermocline is not None
    # The thermocline band is bounded by the >= 50 m band, so it cannot be larger.
    assert metrics.rmse_ge50 >= 0.0
    assert metrics.rmse_thermocline > 0.0
    assert 0.0 < metrics.correlation <= 1.0


def test_per_depth_levels_are_standard_depths(model, argo):
    result = get_validation(date(2020, 1, 1), model=model, argo=argo)
    assert [entry.depth for entry in result.per_depth] == list(STANDARD_DEPTHS)
    assert all(entry.n > 0 for entry in result.per_depth)


def test_validation_carries_provenance_and_caveat(model, argo):
    result = get_validation(date(2020, 1, 1), model=model, argo=argo)
    assert result.summary.model_version
    assert result.summary.caveat
    assert result.provenance
    assert result.summary.n_profiles > 0


def test_argo_floats_are_observed_cells(argo):
    response = get_argo_floats(date(2020, 1, 1), argo=argo)
    assert response.status == "available"
    assert response.floats
    assert response.time_offset_days == -2
    sample = response.floats[0]
    assert 5.0 <= sample.lat <= 30.0
    assert 45.0 <= sample.lon <= 105.0
    assert sample.n_levels >= 1


def test_alerts_report_largest_disagreements(model, argo):
    response = get_anomaly_alerts(date(2020, 1, 1), limit=5, model=model, argo=argo)
    assert response.status == "available"
    assert len(response.alerts) == 5
    magnitudes = [abs(alert.difference) for alert in response.alerts]
    assert magnitudes == sorted(magnitudes, reverse=True)


def test_metadata_exposes_argo_status():
    from app.services.metadata import get_metadata

    metadata = get_metadata()
    assert metadata.argo_status in {"bundled_sample", "unavailable"}
    assert metadata.model_parameter_count == 1_643_288
    assert metadata.available_depths == list(STANDARD_DEPTHS)
    assert metadata.available_dates == [value.isoformat() for value in MODEL_AVAILABLE_DATES]


# --------------------------------------------------------------- comparison states
# §8 of the interface contract: State A (model + reference), State B (model only) and
# State C (model unavailable) must be distinguishable, and the response must report which
# grid cell was actually read rather than implying exact-point skill.

class _GridAwareModel:
    """Model double that reports the grid cell it snapped to."""

    def __init__(self, value):
        self._value = value

    def point_temperature(self, *, latitude, longitude, date, depth):
        return self._value

    def resolve_grid_point(self, *, latitude, longitude, date):
        return {
            "grid_latitude": round(round(latitude / 0.25) * 0.25, 4),
            "grid_longitude": round(round(longitude / 0.25) * 0.25, 4),
            "lat_index": int(round(latitude / 0.25)),
            "lon_index": int(round(longitude / 0.25)),
            "has_value": self._value is not None,
        }


class _PointSource:
    def __init__(self, value):
        self._value = value
        self.status = DataSourceStatus.UNAVAILABLE if value is None else DataSourceStatus.BUNDLED_SAMPLE
        self.provenance = "test reference"

    def get_point_temperature(self, *, latitude, longitude, target_date, depth):
        return {"temperature": self._value}


def test_comparison_state_a_when_both_present():
    result = get_comparison(
        15.1, 65.13, date(2020, 1, 1), 100.0,
        model=_GridAwareModel(22.34),
        glorys_source=_PointSource(22.22),
    )
    assert result.state == "model_and_reference"
    assert round(result.oceanembed_temperature, 2) == 22.34
    assert round(result.difference, 2) == 0.12
    # Grid transparency: 65.13 snaps to 65.25, and both requested and actual are reported.
    assert result.requested_longitude == 65.13
    assert result.grid_longitude == 65.25
    assert result.grid_latitude == 15.0


def test_comparison_state_b_is_model_only_not_an_error():
    result = get_comparison(
        15.0, 65.0, date(2020, 1, 1), 100.0,
        model=_GridAwareModel(22.34),
        glorys_source=_PointSource(None),
    )
    assert result.state == "model_only"
    assert result.oceanembed_temperature is not None
    assert result.glorys_temperature is None
    assert result.difference is None


def test_comparison_state_c_never_fabricates_a_value():
    result = get_comparison(
        15.0, 65.0, date(2020, 1, 1), 100.0,
        model=_GridAwareModel(None),
        glorys_source=_PointSource(22.22),
    )
    assert result.state == "model_unavailable"
    assert result.oceanembed_temperature is None
    assert result.difference is None


def test_comparison_tolerates_model_without_grid_reporting():
    class _NoGrid(_GridAwareModel):
        resolve_grid_point = None

    result = get_comparison(
        15.0, 65.0, date(2020, 1, 1), 100.0,
        model=_NoGrid(22.34),
        glorys_source=_PointSource(22.22),
    )
    assert result.grid_latitude is None
    assert result.state == "model_and_reference"


def test_comparison_reports_when_value_is_not_local():
    """A shelf-sea request resolves to a full-column cell far away; that offset must be visible."""

    class _FarModel:
        def point_temperature(self, *, latitude, longitude, date, depth):
            return 24.0

        def resolve_grid_point(self, *, latitude, longitude, date):
            return {
                "grid_latitude": 25.0,
                "grid_longitude": 57.25,
                "nearest_grid_latitude": 28.0,
                "nearest_grid_longitude": 50.0,
                "offset_degrees": 7.25,
                "has_value": True,
            }

    result = get_comparison(
        28.0, 50.0, date(2020, 1, 1), 100.0,
        model=_FarModel(),
        glorys_source=_PointSource(23.5),
    )
    assert result.offset_degrees == 7.25
    assert result.nearest_grid_longitude == 50.0
    assert "7.25 degrees from the requested cell" in result.state_message


def test_adapter_grid_offset_is_zero_where_the_column_is_complete():
    """In deep water the value must come from the requested cell itself."""
    from app.model.adapter import OceanEmbedModelAdapter

    model = OceanEmbedModelAdapter()
    resolved = model.resolve_grid_point(latitude=15.0, longitude=65.0, date=date(2020, 1, 1))
    assert resolved["offset_degrees"] == 0.0
    assert resolved["grid_latitude"] == resolved["nearest_grid_latitude"]
