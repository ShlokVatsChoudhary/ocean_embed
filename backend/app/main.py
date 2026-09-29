from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings

from app.api.routes.argo import router as argo_router
from app.api.routes.comparison import router as comparison_router
from app.api.routes.hazard import router as hazard_router
from app.api.routes.metadata import router as metadata_router
from app.api.routes.profile import router as profile_router
from app.api.routes.temperature import router as temperature_router
from app.api.routes.validation import router as validation_router

app = FastAPI(
    title="OceanEmbed API",
    description="Backend API for OceanEmbed subsurface ocean temperature reconstruction.",
    version="0.1.0",
)

# Allowed origins are configurable so the same code serves the Vite dev server and the built
# preview build. See app.core.config.Settings.cors_origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metadata_router)
app.include_router(temperature_router)
app.include_router(profile_router)
app.include_router(comparison_router)
app.include_router(validation_router)
app.include_router(hazard_router)
app.include_router(argo_router)


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