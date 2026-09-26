from datetime import date

from fastapi.testclient import TestClient

from app.api.routes.comparison import get_comparison_glorys_source, get_comparison_model
from app.api.routes.profile import get_profile_model
from app.core.constants import MODEL_AVAILABLE_DATES, STANDARD_DEPTHS
from app.data.interfaces import GlorysDataSource
from app.main import app
from app.model.interface import ModelInferenceInput, ModelTemperaturePrediction, OceanEmbedModel
from app.services.comparison import get_comparison
from app.services.metadata import get_metadata
from app.services.profile import get_profile
from app.services.temperature import get_temperature
from app.services.validation import get_validation


class FakeProfileModel(OceanEmbedModel):
    def __init__(self, values=None):
        self.values = values if values is not None else [float(value) for value in range(15)]
        self.received_request = None

    def infer_temperature_field(self, request):
        raise NotImplementedError

    def infer_profile(self, request: ModelInferenceInput):
        self.received_request = request
        from app.model.interface import ModelProfilePrediction

        return ModelProfilePrediction(temperatures=self.values)


class FakeComparisonModel(OceanEmbedModel):
    def __init__(self, temperature):
        self.temperature = temperature
        self.received_request = None

    def infer_temperature_field(self, request: ModelInferenceInput):
        self.received_request = request
        return ModelTemperaturePrediction(
            date=request.date,
            depth=request.depth,
            values=[[self.temperature]],
        )

    def infer_profile(self, request: ModelInferenceInput):
        raise NotImplementedError


class FakeGlorysSource(GlorysDataSource):
    def __init__(self, temperature):
        self.temperature = temperature
        self.received_request = None

    def is_available(self) -> bool:
        return True

    def get_temperature_field(self, **kwargs):
        raise NotImplementedError

    def get_point_temperature(self, *, latitude, longitude, target_date, depth):
        self.received_request = {
            "latitude": latitude,
            "longitude": longitude,
            "target_date": target_date,
            "depth": depth,
        }
        return {"temperature": self.temperature}


client = TestClient(app)


def test_service_metadata_contract():
    response = get_metadata()
    assert response.dataset_name == "OceanEmbed"
    assert response.supported_variables == ["temperature"]
    assert response.available_depths == STANDARD_DEPTHS
    assert response.available_dates == [date.isoformat() for date in MODEL_AVAILABLE_DATES]
    assert len(response.available_depths) == 15
    assert all(depth in STANDARD_DEPTHS for depth in response.available_depths)


def test_service_temperature_contract():
    response = get_temperature(date(2020, 1, 1), 10.0)
    assert response.metadata.date == date(2020, 1, 1)
    assert response.metadata.depth == 10.0


def test_service_profile_contract():
    model = FakeProfileModel()
    response = get_profile(10.0, 20.0, date(2020, 1, 1), model=model)
    assert response.latitude == 10.0
    assert response.longitude == 20.0
    assert response.date == date(2020, 1, 1)
    assert [point.depth for point in response.profile] == STANDARD_DEPTHS
    assert [point.temperature for point in response.profile] == [float(value) for value in range(15)]


def test_profile_model_mapping_and_validation():
    model = FakeProfileModel()
    response = get_profile(12.5, 21.5, date(2020, 2, 3), model=model)

    assert model.received_request.latitude == 12.5
    assert model.received_request.longitude == 21.5
    assert model.received_request.date == date(2020, 2, 3)
    assert response.profile[0].depth == STANDARD_DEPTHS[0]
    assert response.profile[0].temperature == 0.0
    assert response.profile[-1].depth == STANDARD_DEPTHS[-1]
    assert response.profile[-1].temperature == 14.0

    filtered = get_profile(12.5, 21.5, date(2020, 2, 3), model=model, depth=125.0)
    assert len(filtered.profile) == 1
    assert filtered.profile[0].depth == 125.0
    assert filtered.profile[0].temperature == 8.0

    try:
        get_profile(12.5, 21.5, date(2020, 2, 3), model=model, depth=15.0)
        raise AssertionError("Expected ValueError for unsupported depth")
    except ValueError as exc:
        assert "standard profile depths" in str(exc)


def test_profile_requires_exactly_15_model_outputs():
    for values in ([float(value) for value in range(14)], [float(value) for value in range(16)]):
        model = FakeProfileModel(values=values)
        try:
            get_profile(10.0, 20.0, date(2020, 1, 1), model=model)
            raise AssertionError("Expected ValueError for invalid output length")
        except ValueError as exc:
            assert "exactly 15" in str(exc)


def test_profile_preserves_none_values():
    model = FakeProfileModel(values=[0.0, None, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0])
    response = get_profile(10.0, 20.0, date(2020, 1, 1), model=model)
    assert response.profile[1].temperature is None
    assert response.profile[0].temperature == 0.0


def test_profile_route_response_is_valid():
    fake_model = FakeProfileModel()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_profile_model] = lambda: fake_model
    try:
        response = client.get("/api/profile?latitude=10&longitude=20&date=2020-01-01")
        assert response.status_code == 200
        payload = response.json()
        assert payload["latitude"] == 10.0
        assert payload["longitude"] == 20.0
        assert payload["date"] == "2020-01-01"
        assert len(payload["profile"]) == 15
        assert payload["profile"][0]["depth"] == 0.0
        assert payload["profile"][0]["temperature"] == 0.0
        assert payload["profile"][8]["depth"] == 125.0
        assert payload["profile"][8]["temperature"] == 8.0
    finally:
        app.dependency_overrides.clear()


def test_service_comparison_contract():
    response = get_comparison(10.0, 20.0, date(2020, 1, 1), 10.0)
    assert response.depth == 10.0
    assert response.unit == "degC"


def test_comparison_difference_calculation():
    model = FakeComparisonModel(temperature=12.0)
    glorys = FakeGlorysSource(temperature=9.5)
    response = get_comparison(10.0, 20.0, date(2020, 1, 2), 100.0, model=model, glorys_source=glorys)

    assert response.oceanembed_temperature == 12.0
    assert response.glorys_temperature == 9.5
    assert response.difference == 2.5
    assert response.latitude == 10.0
    assert response.longitude == 20.0
    assert response.date == date(2020, 1, 2)
    assert response.depth == 100.0
    assert model.received_request.latitude == 10.0
    assert model.received_request.longitude == 20.0
    assert model.received_request.date == date(2020, 1, 2)
    assert model.received_request.depth == 100.0
    assert glorys.received_request["latitude"] == 10.0
    assert glorys.received_request["longitude"] == 20.0
    assert glorys.received_request["target_date"] == date(2020, 1, 2)
    assert glorys.received_request["depth"] == 100.0


def test_comparison_handles_signed_and_zero_differences():
    positive = get_comparison(1.0, 2.0, date(2020, 1, 3), 50.0, model=FakeComparisonModel(10.0), glorys_source=FakeGlorysSource(7.0))
    negative = get_comparison(1.0, 2.0, date(2020, 1, 3), 50.0, model=FakeComparisonModel(7.0), glorys_source=FakeGlorysSource(10.0))
    zero = get_comparison(1.0, 2.0, date(2020, 1, 3), 50.0, model=FakeComparisonModel(8.0), glorys_source=FakeGlorysSource(8.0))

    assert positive.difference == 3.0
    assert negative.difference == -3.0
    assert zero.difference == 0.0


def test_comparison_handles_missing_values():
    missing_oceanembed = get_comparison(
        1.0,
        2.0,
        date(2020, 1, 4),
        25.0,
        model=FakeComparisonModel(None),
        glorys_source=FakeGlorysSource(6.0),
    )
    missing_glorys = get_comparison(
        1.0,
        2.0,
        date(2020, 1, 4),
        25.0,
        model=FakeComparisonModel(6.0),
        glorys_source=FakeGlorysSource(None),
    )

    assert missing_oceanembed.oceanembed_temperature is None
    assert missing_oceanembed.glorys_temperature == 6.0
    assert missing_oceanembed.difference is None

    assert missing_glorys.oceanembed_temperature == 6.0
    assert missing_glorys.glorys_temperature is None
    assert missing_glorys.difference is None


def test_comparison_route_uses_dependency_injection():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_comparison_model] = lambda: FakeComparisonModel(8.0)
    app.dependency_overrides[get_comparison_glorys_source] = lambda: FakeGlorysSource(5.0)
    try:
        response = client.get("/api/comparison?latitude=11&longitude=22&date=2020-01-05&depth=75")
        assert response.status_code == 200
        payload = response.json()
        assert payload["latitude"] == 11.0
        assert payload["longitude"] == 22.0
        assert payload["date"] == "2020-01-05"
        assert payload["depth"] == 75.0
        assert payload["oceanembed_temperature"] == 8.0
        assert payload["glorys_temperature"] == 5.0
        assert payload["difference"] == 3.0
    finally:
        app.dependency_overrides.clear()


def test_service_validation_contract():
    response = get_validation(date(2024, 1, 1), 10.0)
    assert response.dataset == "ARGO"
    assert response.metrics.n_observations is None


def test_api_endpoints_return_valid_contracts():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_profile_model] = lambda: FakeProfileModel()
    app.dependency_overrides[get_comparison_model] = lambda: FakeComparisonModel(10.0)
    app.dependency_overrides[get_comparison_glorys_source] = lambda: FakeGlorysSource(7.0)
    try:
        assert client.get("/health").status_code == 200
        assert client.get("/api/metadata").status_code == 200
        assert client.get("/api/temperature?date=2020-01-01&depth=10").status_code == 200
        assert client.get("/api/profile?latitude=10&longitude=20&date=2020-01-01").status_code == 200
        assert client.get("/api/comparison?latitude=10&longitude=20&date=2020-01-01&depth=10").status_code == 200
        assert client.get("/api/validation?date=2020-01-01&depth=10").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_api_rejects_invalid_latitude_and_longitude():
    assert client.get("/api/profile?latitude=91&longitude=20&date=2020-01-01").status_code == 422
    assert client.get("/api/profile?latitude=10&longitude=181&date=2020-01-01").status_code == 422


def test_api_rejects_invalid_depth_and_date():
    assert client.get("/api/temperature?date=2020-01-01&depth=-1").status_code == 422
    assert client.get("/api/profile?latitude=10&longitude=20&date=not-a-date").status_code == 422


def test_api_rejects_invalid_geographic_bounds():
    response = client.get("/api/temperature?date=2020-01-01&depth=10&latitude_min=20&latitude_max=10")
    assert response.status_code == 400
    assert "latitude_min" in response.json()["detail"]

    response = client.get("/api/temperature?date=2020-01-01&depth=10&longitude_min=20&longitude_max=10")
    assert response.status_code == 400
    assert "longitude_min" in response.json()["detail"]
