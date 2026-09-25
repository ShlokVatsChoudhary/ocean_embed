import pytest

from datetime import date

from app.data.argo import ArgoDataAccessor
from app.data.glorys import GlorysDataAccessor
from app.data.interfaces import ArgoDataSource, DataLoader, DataSource, GlorysDataSource
from app.data.loader import ScientificDataLoader


def test_data_interfaces_exist():
    assert issubclass(ArgoDataSource, DataSource)
    assert issubclass(GlorysDataSource, DataSource)
    assert issubclass(DataLoader, object)


def test_argo_placeholder_raises_not_implemented():
    accessor = ArgoDataAccessor()
    with pytest.raises(NotImplementedError):
        accessor.get_profile_by_id("profile-1")
    with pytest.raises(NotImplementedError):
        accessor.get_validation_observations(date=None)


def test_glorys_placeholder_raises_not_implemented():
    accessor = GlorysDataAccessor()
    with pytest.raises(NotImplementedError):
        accessor.get_temperature_field(target_date=date(2024, 1, 1), depth=10.0)


def test_loader_placeholder_raises_not_implemented():
    loader = ScientificDataLoader()
    with pytest.raises(NotImplementedError):
        loader.load_metadata()
    with pytest.raises(NotImplementedError):
        loader.load_available_dates()
