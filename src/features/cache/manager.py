"""Cache manager for Blendflare asset storage."""

import os
from typing import Optional, Tuple

import bpy

from ...logger import cache_logger


# Singleton instance
_cache_manager: Optional["CacheManager"] = None


def get_cache_manager() -> "CacheManager":
    """Get or create the singleton CacheManager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


class CacheManager:
    """Manages local cache storage for Blendflare assets.

    Cache structure:
        {cache_path}/
        ├── materials/
        │   └── {username}/
        │       └── {project-slug}/
        │           ├── {file_name}.blend (or .zip)
        │           └── bf.meta.json
        ├── hdris/
        │   └── {username}/...
        ├── scenes/
        │   └── {username}/...
        └── 3d_models/
            └── {category}/  (architecture, character, etc.)
                └── {username}/
                    └── {project-slug}/...
    """

    METADATA_FILENAME = "bf.meta.json"

    # Top-level categories (non-3D)
    TOP_CATEGORIES = ("materials", "hdris", "scenes")

    # 3D model subcategories
    MODEL_SUBCATEGORIES = (
        "architecture", "character", "accessories", "decoration",
        "industrial", "interior", "military", "nature", "space",
        "sport_hobby", "technology", "transport"
    )

    def __init__(self):
        pass

    def _get_prefs(self):
        """Get addon preferences."""
        return bpy.context.preferences.addons[__package__.rsplit('.', 2)[0]].preferences

    def get_cache_root(self) -> str:
        """Get the root cache directory path."""
        prefs = self._get_prefs()
        return prefs.get_cache_path()

    def _is_3d_model_category(self, category: str) -> bool:
        """Check if category is a 3D model subcategory."""
        return category.lower() in self.MODEL_SUBCATEGORIES

    def get_asset_dir(self, category: str, username: str, slug: str) -> str:
        """Get the directory path for a specific asset.

        Args:
            category: Asset category (materials, hdris, scenes, or 3D model subcategory like architecture)
            username: Author's username/nickname
            slug: Project slug (unique identifier)

        Returns:
            Full path to the asset directory

        Structure:
            - materials/hdris/scenes: /{category}/{username}/{slug}/
            - 3D models: /3d_models/{subcategory}/{username}/{slug}/
        """
        cache_root = self.get_cache_root()
        category_lower = category.lower()

        if self._is_3d_model_category(category_lower):
            # 3D model: /3d_models/{subcategory}/{username}/{slug}/
            return os.path.join(cache_root, "3d_models", category_lower, username, slug)
        else:
            # Top-level category: /{category}/{username}/{slug}/
            return os.path.join(cache_root, category_lower, username, slug)

    def get_metadata_path(self, category: str, username: str, slug: str) -> str:
        """Get the path to the metadata file for an asset."""
        asset_dir = self.get_asset_dir(category, username, slug)
        return os.path.join(asset_dir, self.METADATA_FILENAME)

    def get_asset_file_path(self, category: str, username: str, slug: str, file_name: str) -> str:
        """Get the full path where the asset file should be stored."""
        asset_dir = self.get_asset_dir(category, username, slug)
        return os.path.join(asset_dir, file_name)

    def asset_exists(self, category: str, username: str, slug: str) -> bool:
        """Check if an asset exists in the cache (has metadata file)."""
        metadata_path = self.get_metadata_path(category, username, slug)
        return os.path.exists(metadata_path)

    def get_cached_asset(self, category: str, username: str, slug: str) -> Tuple[Optional[str], Optional[str]]:
        """Get paths to cached asset file and metadata if they exist.

        Returns:
            Tuple of (asset_file_path, metadata_path) or (None, None) if not cached
        """
        if not self.asset_exists(category, username, slug):
            return None, None

        metadata_path = self.get_metadata_path(category, username, slug)
        asset_dir = self.get_asset_dir(category, username, slug)

        # Find the asset file (.blend or .zip)
        asset_file = None
        if os.path.exists(asset_dir):
            for f in os.listdir(asset_dir):
                if f.endswith(('.blend', '.zip')) and f != self.METADATA_FILENAME:
                    asset_file = os.path.join(asset_dir, f)
                    break

        return asset_file, metadata_path

    def ensure_asset_dir(self, category: str, username: str, slug: str) -> str:
        """Ensure the asset directory exists, creating it if necessary.

        Returns:
            Path to the asset directory
        """
        asset_dir = self.get_asset_dir(category, username, slug)
        os.makedirs(asset_dir, exist_ok=True)
        return asset_dir

    def clear_asset_dir(self, category: str, username: str, slug: str) -> bool:
        """Clear all files in an asset directory (keeps the directory).

        Use this before downloading a new version to avoid duplicate files.

        Returns:
            True if cleared successfully
        """
        asset_dir = self.get_asset_dir(category, username, slug)
        if not os.path.exists(asset_dir):
            return True

        try:
            for f in os.listdir(asset_dir):
                file_path = os.path.join(asset_dir, f)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    cache_logger(f"Removed old file: {f}")
            return True
        except Exception as e:
            cache_logger.error(f"Error clearing asset dir: {e}")
            return False

    def delete_asset(self, category: str, username: str, slug: str) -> bool:
        """Delete an asset from the cache.

        Returns:
            True if deleted successfully, False if not found
        """
        import shutil

        asset_dir = self.get_asset_dir(category, username, slug)
        if os.path.exists(asset_dir):
            shutil.rmtree(asset_dir)
            return True
        return False

    def get_cache_size(self) -> int:
        """Get total size of the cache in bytes."""
        total_size = 0
        cache_root = self.get_cache_root()

        if not os.path.exists(cache_root):
            return 0

        for dirpath, _, filenames in os.walk(cache_root):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except OSError:
                    pass

        return total_size

    def get_cache_size_mb(self) -> float:
        """Get total size of the cache in megabytes."""
        return self.get_cache_size() / (1024 * 1024)

    def clear_cache(self) -> bool:
        """Clear the entire cache directory.

        Returns:
            True if cleared successfully
        """
        import shutil

        cache_root = self.get_cache_root()
        if os.path.exists(cache_root):
            shutil.rmtree(cache_root)
            return True
        return False
