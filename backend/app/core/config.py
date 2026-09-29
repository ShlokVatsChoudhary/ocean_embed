"""Runtime configuration for the OceanEmbed backend.

All paths are overridable through ``OCEANEMBED_*`` environment variables so the
same code runs from a developer checkout, a container, or a deployment where the
model artifacts and the ARGO archive live outside the repository.

Nothing here is required for the server to start. Missing data is reported
through each data source's explicit status rather than by crashing on import.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def repo_root() -> Path:
    """Return the repository root (the directory that contains ``backend/``)."""
    return Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Environment-driven settings.

    Environment variables use the ``OCEANEMBED_`` prefix, e.g.
    ``OCEANEMBED_MODEL_ROOT``, ``OCEANEMBED_ARGO_PATH``.
    """

    model_config = SettingsConfigDict(env_prefix="OCEANEMBED_", extra="ignore")

    #: Directory holding the exported PS66/OceanEmbed model package.
    model_root: Path = Field(default_factory=lambda: repo_root() / "model" / "PS66-Ocean-Model")

    #: Explicit NetCDF/NPZ path for the ARGO validation archive.
    argo_path: Path | None = None

    #: Directory scanned for ARGO files when ``argo_path`` is not set.
    argo_dir: Path = Field(default_factory=lambda: repo_root() / "backend" / "data" / "argo")

    #: Optional root holding a live GLORYS archive.
    glorys_root: Path | None = None

    @property
    def backend_dir(self) -> Path:
        return repo_root() / "backend"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
