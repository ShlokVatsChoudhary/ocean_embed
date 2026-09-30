"""Tests for the reference (GLORYS) field endpoint.

The reference field is the field the model was trained against, so publishing it
creates two specific risks that these tests pin down:

* it must never be presentable as validation evidence, so every payload carries a
  ``source`` label that starts with ``glorys_reference``;
* its land cells must serialise as JSON ``null``, because ``NaN`` is not valid
  JSON and a browser calling ``JSON.parse`` on it fails outright.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pytest

from app.data.interfaces import DataSourceStatus, GlorysDataSource
from app.services.reference import get_reference_temperature

SMALL_FIELD = np.array(
    [
        [28.0, 27.5, np.nan],
        [26.0, np.nan, 24.0],
        [22.0, 21.0, 20.0],
    ]
)


class FakeGlorys(GlorysDataSource):
    """Minimal source that returns a known 3x3 field so the contract is checkable."""

    def __init__(self, *, available: bool = True):
        self._available = available

    @property
    def status(self) -> DataSourceStatus:
        return DataSourceStatus.BUNDLED_SAMPLE if self._available else DataSourceStatus.UNAVAILABLE

    @property
    def provenance(self) -> str:
        return "fake"

    def is_available(self) -> bool:
        return self._available

    def get_temperature_field(self, *, target_date: date, depth: float, **kwargs: Any) -> dict[str, Any]:
        if not self._available:
            raise RuntimeError("GLORYS reference data is not available in this environment.")
        return {
            "date": target_date,
            "depth": depth,
            "values": SMALL_FIELD.tolist(),
            "lats": [30.0, 29.75, 29.5],
            "lons": [45.0, 45.25, 45.5],
        }

    def get_point_temperature(self, **kwargs: Any) -> dict[str, Any]:  # pragma: no cover
        return {"temperature": 25.0}


# ------------------------------------------------------------------- service
def test_reference_field_labels_its_source_so_it_cannot_pass_as_validation():
    response = get_reference_temperature(date(2020, 1, 1), 100.0, glorys=FakeGlorys())
    assert response.metadata.source == "glorys_reference:bundled_sample"


def test_reference_field_replaces_nan_with_none():
    response = get_reference_temperature(date(2020, 1, 1), 100.0, glorys=FakeGlorys())
    assert response.values[0][2] is None
    assert response.values[1][1] is None
    assert response.values[0][0] == pytest.approx(28.0)


def test_reference_field_bounds_come_from_the_returned_axes():
    response = get_reference_temperature(date(2020, 1, 1), 100.0, glorys=FakeGlorys())
    bounds = response.metadata.bounds
    assert bounds["latitude_min"] == pytest.approx(30.0)
    assert bounds["latitude_max"] == pytest.approx(29.5)
    assert bounds["longitude_min"] == pytest.approx(45.0)
    assert bounds["longitude_max"] == pytest.approx(45.5)


def test_reference_field_rejects_a_non_standard_depth():
    with pytest.raises(ValueError, match="standard profile depths"):
        get_reference_temperature(date(2020, 1, 1), 33.0, glorys=FakeGlorys())


def test_reference_field_rejects_a_date_outside_the_supported_range():
    with pytest.raises(ValueError, match="Data unavailable"):
        get_reference_temperature(date(2019, 6, 1), 100.0, glorys=FakeGlorys())


def test_reference_field_requires_a_source():
    with pytest.raises(ValueError, match="requires a GlorysDataSource"):
        get_reference_temperature(date(2020, 1, 1), 100.0, glorys=None)


# ----------------------------------------------------------------- endpoints
@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_reference_endpoint_returns_a_field_matching_the_model_grid(client):
    response = client.get("/api/reference", params={"date": "2020-01-01", "depth": 100})
    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["source"].startswith("glorys_reference")
    assert body["metadata"]["variable"] == "temperature"
    values = np.array(
        [[np.nan if v is None else v for v in row] for row in body["values"]],
        dtype="float64",
    )
    assert values.shape == (101, 241)


def test_reference_endpoint_json_contains_no_bare_nan_token(client):
    """NaN is not valid JSON; land must arrive as null."""
    text = client.get("/api/reference", params={"date": "2020-01-01", "depth": 100}).text
    assert "NaN" not in text
    assert "Infinity" not in text


def test_reference_endpoint_rejects_an_unknown_depth(client):
    response = client.get("/api/reference", params={"date": "2020-01-01", "depth": 33})
    assert response.status_code == 400


def test_reference_endpoint_rejects_an_unknown_date(client):
    response = client.get("/api/reference", params={"date": "2019-06-01", "depth": 100})
    assert response.status_code == 400


def test_reference_endpoint_reports_unavailable_source_as_503(client):
    from app.api.routes.reference import get_reference_source
    from app.main import app

    app.dependency_overrides[get_reference_source] = lambda: FakeGlorys(available=False)
    try:
        response = client.get("/api/reference", params={"date": "2020-01-01", "depth": 100})
        assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_reference_source, None)
