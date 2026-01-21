"""Asset application module for Blendflare.

This module provides category-specific asset importers and appliers.
Each category (materials, HDRIs, scenes, 3D models) has its own applier
that knows how to import and apply assets to the current scene.
"""

from .base import ApplyResult, BaseAssetApplier, get_applier_for_category
from .materials import MaterialApplier
from .models import ModelApplier
from .scenes import SceneApplier
from .hdris import HdriApplier

__all__ = [
    "ApplyResult",
    "BaseAssetApplier",
    "get_applier_for_category",
    "MaterialApplier",
    "ModelApplier",
    "SceneApplier",
    "HdriApplier",
]
