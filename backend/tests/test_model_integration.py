from datetime import date

import pytest

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
