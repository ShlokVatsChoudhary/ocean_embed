from fastapi import APIRouter

from app.schemas.oceanembed import MetadataResponse
from app.services.metadata import get_metadata as get_metadata_service

router = APIRouter(prefix="/api/metadata", tags=["metadata"])


@router.get("", response_model=MetadataResponse, summary="Return project and dataset metadata")
@router.get("/", include_in_schema=False)
async def get_metadata() -> MetadataResponse:
    return get_metadata_service()
