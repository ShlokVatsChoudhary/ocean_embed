from fastapi import FastAPI

app = FastAPI(
    title="OceanEmbed API",
    description="Backend API for OceanEmbed subsurface ocean temperature reconstruction.",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "name": "OceanEmbed API",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }