from app.core.constants import MODEL_AVAILABLE_DATES, STANDARD_DEPTHS
from app.data.glorys import GlorysDataAccessor
from app.model.adapter import OceanEmbedModelAdapter
from app.schemas.oceanembed import MetadataResponse


def get_metadata() -> MetadataResponse:
    """Return metadata derived from the canonical backend/model constants."""
    model = OceanEmbedModelAdapter()
    glorys_source = GlorysDataAccessor()
    available_dates = [date.isoformat() for date in model.available_dates()]
    return MetadataResponse(
        dataset_name="OceanEmbed",
        project="OceanEmbed",
        description="OceanEmbed model-backed temperature reconstruction backend.",
        available_dates=available_dates,
        available_depths=list(STANDARD_DEPTHS),
        spatial_resolution={
            "latitude": 0.25,
            "longitude": 0.25,
            "units": "degrees",
        },
        supported_variables=["temperature"],
        glorys_status=glorys_source.status.value,
        glorys_provenance=glorys_source.provenance,
    )
