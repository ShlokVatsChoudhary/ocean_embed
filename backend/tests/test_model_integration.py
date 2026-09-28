from datetime import date

import pytest

from app.model.adapter import OceanEmbedModelAdapter
from app.model.interface import (
    ModelInferenceInput,
    OceanEmbedModel,
    PlaceholderOceanEmbedModel,
)


def test_model_input_contract():
    request = ModelInferenceInput(
        date=date(2024, 1, 1),
        latitude=10.5,
        longitude=20.25,
        depth=15.0,
    )
    assert request.date == date(2024, 1, 1)
    assert request.latitude == 10.5
    assert request.longitude == 20.25
    assert request.depth == 15.0


def test_model_interface_is_abstract():
    assert issubclass(OceanEmbedModel, object)
    assert OceanEmbedModel.__abstractmethods__ == {"infer_temperature_field", "infer_profile"}


def test_placeholder_model_raises_not_implemented():
    model = PlaceholderOceanEmbedModel()
    request = ModelInferenceInput(date=date(2024, 1, 1), latitude=10.0, longitude=20.0, depth=10.0)

    with pytest.raises(NotImplementedError):
        model.infer_temperature_field(request)

    with pytest.raises(NotImplementedError):
        model.infer_profile(request)


def test_real_adapter_loads_trained_ps66_model_and_predicts_finite_profile():
    model = OceanEmbedModelAdapter()
    request = ModelInferenceInput(date=date(2020, 1, 1), latitude=10.0, longitude=50.0)

    prediction = model.infer_profile(request)

    assert len(prediction.temperatures) == 15
    assert all(value is not None and value == value and value != float("inf") for value in prediction.temperatures)


def test_real_profile_route_returns_finite_temperatures_from_ps66_model():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/api/profile?latitude=10&longitude=50&date=2020-01-01")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["profile"]) == 15
    assert all(
        point["temperature"] is not None and point["temperature"] == point["temperature"] for point in payload["profile"]
    )


def test_ps66_model_accepts_current_demo_data_range():
    model = OceanEmbedModelAdapter()

    for requested_date in [date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 7)]:
        prediction = model.infer_profile(ModelInferenceInput(date=requested_date, latitude=12.0, longitude=68.0))
        assert len(prediction.temperatures) == 15
        assert all(value is not None and value == value and abs(float(value)) < float("inf") for value in prediction.temperatures)

    for invalid_date in [date(2019, 12, 31), date(2020, 1, 8), date(2020, 2, 5), date(2020, 3, 31), date(2020, 4, 1)]:
        with pytest.raises(ValueError, match="outside the supported model range"):
            model.infer_profile(ModelInferenceInput(date=invalid_date, latitude=12.0, longitude=68.0))


def test_profile_route_rejects_outside_current_data_range():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/api/profile?latitude=12&longitude=68&date=2020-02-05")

    assert response.status_code == 400, response.text
    assert "Data unavailable" in response.json()["detail"]


def test_ps66_model_uses_latitude_and_longitude_axes_in_correct_order():
    model = OceanEmbedModelAdapter()
    lat_only = model.point_temperature(latitude=10.0, longitude=50.0, date=date(2020, 1, 1), depth=10.0)
    lon_only = model.point_temperature(latitude=50.0, longitude=10.0, date=date(2020, 1, 1), depth=10.0)

    assert lat_only is not None
    assert lon_only is not None
    assert lat_only != lon_only
