from fastapi import FastAPI

from app.api.routes.comparison import router as comparison_router
from app.api.routes.metadata import router as metadata_router
from app.api.routes.profile import router as profile_router
from app.api.routes.temperature import router as temperature_router
from app.api.routes.validation import router as validation_router

app = FastAPI(
    title="OceanEmbed API",
    description="Backend API for OceanEmbed subsurface ocean temperature reconstruction.",
    version="0.1.0",
)

app.include_router(metadata_router)
app.include_router(temperature_router)
app.include_router(profile_router)
app.include_router(comparison_router)
app.include_router(validation_router)


@app.get("/")
async def root():
    return {
        "name": "OceanEmbed API",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
    }