from app.core.constants import MODEL_AVAILABLE_DATES, STANDARD_DEPTHS
from app.data.argo import ArgoDataAccessor
from app.data.glorys import GlorysDataAccessor
from app.model.adapter import OceanEmbedModelAdapter
from app.schemas.oceanembed import MetadataResponse


def get_metadata() -> MetadataResponse:
    """Return metadata derived from the canonical backend/model constants."""
    model = OceanEmbedModelAdapter()
    glorys_source = GlorysDataAccessor()
    argo_source = ArgoDataAccessor()

    argo_dates = []
    if argo_source.is_available():
        try:
            argo_dates = [value.isoformat() for value in argo_source.available_times()]
        except RuntimeError:
            argo_dates = []

    parameter_count = None
    try:
        runtime = model._load_ps66_runtime()  # noqa: SLF001 - metadata needs the real count
        parameter_count = int(runtime.count_params())
    except Exception:  # noqa: BLE001 - metadata must not fail the endpoint
        parameter_count = None

    return MetadataResponse(
        dataset_name="OceanEmbed",
        project="OceanEmbed",
        description="OceanEmbed model-backed subsurface temperature reconstruction backend.",
        available_dates=[value.isoformat() for value in model.available_dates()],
        available_depths=list(STANDARD_DEPTHS),
        spatial_resolution={
            "latitude": 0.25,
            "longitude": 0.25,
            "units": "degrees",
        },
        supported_variables=["temperature"],
        glorys_status=glorys_source.status.value,
        glorys_provenance=glorys_source.provenance,
        argo_status=argo_source.status.value,
        argo_provenance=argo_source.provenance,
        argo_available_dates=argo_dates,
        model_available_dates=[value.isoformat() for value in MODEL_AVAILABLE_DATES],
        model_parameter_count=parameter_count,
    )
