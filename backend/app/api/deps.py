"""Shared FastAPI dependencies.

Model weights and the ARGO archive are expensive to construct and are read-only,
so they are built once per process and reused. Building them per request would
reload TensorFlow on every call (seconds of latency and a new graph each time).
"""

from __future__ import annotations

from functools import lru_cache

from app.data.argo import ArgoDataAccessor
from app.data.glorys import GlorysDataAccessor
from app.data.interfaces import ArgoDataSource, GlorysDataSource
from app.model.adapter import OceanEmbedModelAdapter
from app.model.interface import OceanEmbedModel


@lru_cache(maxsize=1)
def _model_singleton() -> OceanEmbedModel:
    return OceanEmbedModelAdapter()


@lru_cache(maxsize=1)
def _glorys_singleton() -> GlorysDataSource:
    return GlorysDataAccessor()


@lru_cache(maxsize=1)
def _argo_singleton() -> ArgoDataSource:
    return ArgoDataAccessor()


def get_model() -> OceanEmbedModel:
    """Return the shared OceanEmbed model adapter."""
    return _model_singleton()


def get_glorys_source() -> GlorysDataSource:
    """Return the shared GLORYS reference accessor."""
    return _glorys_singleton()


def get_argo_source() -> ArgoDataSource:
    """Return the shared ARGO validation accessor."""
    return _argo_singleton()
