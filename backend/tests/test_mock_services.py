from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.services.comparison import get_comparison
from app.services.metadata import get_metadata
from app.services.profile import get_profile
from app.services.temperature import get_temperature
from app.services.validation import get_validation


client = TestClient(app)


def test_service_metadata_contract():
    response = get_metadata()
    assert response.dataset_name == "OceanEmbed"
    assert response.supported_variables == ["temperature"]


def test_service_temperature_contract():
    response = get_temperature(date(2024, 1, 1), 10.0)
    assert response.metadata.date == date(2024, 1, 1)
    assert response.metadata.depth == 10.0


def test_service_profile_contract():
    response = get_profile(10.0, 20.0, date(2024, 1, 1))
    assert response.latitude == 10.0
    assert response.longitude == 20.0
    assert response.date == date(2024, 1, 1)


def test_service_comparison_contract():
    response = get_comparison(10.0, 20.0, date(2024, 1, 1), 10.0)
    assert response.depth == 10.0
    assert response.unit == "degC"


def test_service_validation_contract():
    response = get_validation(date(2024, 1, 1), 10.0)
    assert response.dataset == "ARGO"
    assert response.metrics.n_observations is None


def test_api_endpoints_return_valid_contracts():
    assert client.get("/health").status_code == 200
    assert client.get("/api/metadata").status_code == 200
    assert client.get("/api/temperature?date=2024-01-01&depth=10").status_code == 200
    assert client.get("/api/profile?latitude=10&longitude=20&date=2024-01-01").status_code == 200
    assert client.get("/api/comparison?latitude=10&longitude=20&date=2024-01-01&depth=10").status_code == 200
    assert client.get("/api/validation?date=2024-01-01&depth=10").status_code == 200
