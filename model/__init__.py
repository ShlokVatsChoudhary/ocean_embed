"""OceanEmbed v1 model package (Friend 1 / model provider).

Public entry point::

    from model.adapter import OceanEmbedV1
"""
from .adapter import OceanEmbedV1  # noqa: F401
from . import config  # noqa: F401

__all__ = ["OceanEmbedV1", "config"]
