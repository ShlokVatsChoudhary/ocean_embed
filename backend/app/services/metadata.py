from app.schemas.oceanembed import MetadataResponse


def get_metadata() -> MetadataResponse:
    """Return deterministic mock metadata for development and API-contract testing.

    This is intentionally placeholder data only; it is not a real OceanEmbed dataset
    inventory or scientific metadata source.
    """
    return MetadataResponse(
        dataset_name="OceanEmbed",
        project="OceanEmbed",
        description="Mock development metadata for OceanEmbed backend API contracts.",
        available_dates=["2024-01-01", "2024-01-15", "2024-02-01"],
        available_depths=[0.0, 10.0, 25.0, 50.0, 100.0, 200.0],
        spatial_resolution={
            "latitude": 0.25,
            "longitude": 0.25,
            "units": "degrees",
        },
        supported_variables=["temperature"],
    )
