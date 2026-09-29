import numpy as np
import pytest

from datetime import date

from app.data.argo import ArgoDataAccessor
from app.data.glorys import GlorysDataAccessor
from app.data.interfaces import ArgoDataSource, DataLoader, DataSource, DataSourceStatus, GlorysDataSource
from app.data.loader import ScientificDataLoader


def test_data_interfaces_exist():
    assert issubclass(ArgoDataSource, DataSource)
    assert issubclass(GlorysDataSource, DataSource)
    assert issubclass(DataLoader, object)


def test_argo_accessor_never_fabricates_observations():
    """Without a reference file the accessor must report unavailability and return no data.

    The previous behaviour was to raise NotImplementedError; the accessor is now real, so
    what matters is that a missing archive degrades honestly instead of inventing values.
    """
    accessor = ArgoDataAccessor()
    if accessor.is_available():
        pytest.skip("Bundled ARGO archive is present; see test_argo_validation.py for the real path.")

    assert accessor.status.value == "unavailable"
    assert accessor.temperature_field(date(2020, 1, 1)) is None
    assert accessor.observed_cells(date(2020, 1, 1)) == []
    assert accessor.get_validation_observations(date=date(2020, 1, 1)) == []


def test_glorys_sample_accessor_is_available_and_returns_field():
    accessor = GlorysDataAccessor()
    assert accessor.is_available() is True
    assert accessor.status == DataSourceStatus.BUNDLED_SAMPLE
    assert "not live glorys data" in accessor.provenance.lower()
    payload = accessor.get_temperature_field(target_date=date(2020, 1, 1), depth=10.0)
    assert isinstance(payload["values"], list)
    assert len(payload["values"]) > 0
    assert len(payload["values"][0]) > 0
    assert "temperature" in accessor.get_point_temperature(latitude=10.0, longitude=60.0, target_date=date(2020, 1, 1), depth=10.0)
    assert len(payload["lats"]) == len(payload["values"])
    assert len(payload["lons"]) == len(payload["values"][0])


def test_glorys_rejects_unsupported_date():
    accessor = GlorysDataAccessor()
    with pytest.raises(ValueError, match="outside the supported demo range"):
        accessor.get_temperature_field(target_date=date(2020, 1, 8), depth=10.0)


def test_glorys_unavailable_status_for_missing_bundle(tmp_path):
    accessor = GlorysDataAccessor(model_root=tmp_path)
    assert accessor.status == DataSourceStatus.UNAVAILABLE
    assert accessor.is_available() is False
    assert "unavailable" in accessor.provenance.lower()


def test_glorys_uses_processed_y_when_present(tmp_path):
    processed_dir = tmp_path / "data" / "processed"
    processed_dir.mkdir(parents=True)
    np.save(processed_dir / "Y_2020.npy", np.zeros((7, 15, 101, 241), dtype=np.float32))

    accessor = GlorysDataAccessor(model_root=tmp_path)
    assert accessor.is_available() is True
    assert accessor.status == DataSourceStatus.BUNDLED_SAMPLE
    payload = accessor.get_point_temperature(latitude=10.0, longitude=60.0, target_date=date(2020, 1, 1), depth=10.0)
    assert payload["temperature"] == 0.0


def test_comparison_handles_missing_glorys_gracefully(tmp_path):
    accessor = GlorysDataAccessor(model_root=tmp_path)
    assert accessor.is_available() is False

    class DummyModel:
        def point_temperature(self, *, latitude, longitude, date, depth):
            return 12.5

    response = __import__("app.services.comparison", fromlist=["get_comparison"]).get_comparison(
        latitude=10.0,
        longitude=60.0,
        selected_date=date(2020, 1, 1),
        depth=10.0,
        model=DummyModel(),
        glorys_source=accessor,
    )

    assert response.oceanembed_temperature == 12.5
    assert response.glorys_temperature is None
    assert response.difference is None


def test_glorys_live_status_when_env_root_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("OCEANEMBED_GLORYS_ROOT", str(tmp_path))
    sample_dir = tmp_path / "samples"
    sample_dir.mkdir(parents=True, exist_ok=True)
    np.zeros((7, 15, 101, 241), dtype=np.float32).tofile(sample_dir / "Y_2020.npy")
    accessor = GlorysDataAccessor(model_root=tmp_path)
    assert accessor.status == DataSourceStatus.BUNDLED_SAMPLE
    assert "bundled_sample" in accessor.provenance.lower()
    assert "not live glorys data" in accessor.provenance.lower()


def test_loader_placeholder_raises_not_implemented():
    loader = ScientificDataLoader()
    with pytest.raises(NotImplementedError):
        loader.load_metadata()
    with pytest.raises(NotImplementedError):
        loader.load_available_dates()
