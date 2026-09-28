from __future__ import annotations

from datetime import date

from app.core.constants import STANDARD_DEPTHS
from app.model.interface import ModelInferenceInput


def test_real_model_contract_matches_trained_artifact():
    from app.model.adapter import OceanEmbedModelAdapter

    adapter = OceanEmbedModelAdapter()

    assert adapter.input_channels == ["sst", "sss", "sla", "ugos", "vgos"]
    assert adapter.output_depths == STANDARD_DEPTHS
    assert len(adapter.output_depths) == 15
    assert adapter.grid_shape == (101, 241)

    request = ModelInferenceInput(date=date(2020, 1, 1), latitude=10.0, longitude=60.0)
    profile = adapter.infer_profile(request)
    assert len(profile.temperatures) == 15
    assert all(value is None or (isinstance(value, (int, float)) and value == value) for value in profile.temperatures)

    field = adapter.infer_temperature_field(ModelInferenceInput(date=date(2020, 1, 1), depth=10.0))
    assert len(field.values) == 101
    assert len(field.values[0]) == 241
