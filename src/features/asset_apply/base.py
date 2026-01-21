"""Base class for category-specific asset application."""

import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

import bpy


def _log(message: str):
    """Log a message to the console with Blendflare prefix."""
    print(f"[Blendflare Asset] {message}")


@dataclass
class ApplyResult:
    """Result of an asset application operation.

    Attributes:
        success: Whether the operation completed successfully
        message: Human-readable status message
        applied_items: List of names of successfully applied items (materials, objects, etc.)
        warnings: List of warning messages (non-fatal issues)
    """
    success: bool
    message: str
    applied_items: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class BaseAssetApplier(ABC):
    """Base class for category-specific asset application.

    Subclasses implement the `apply` method to handle category-specific logic
    (materials, HDRIs, scenes, 3D models).

    Attributes:
        file_path: Path to the asset file (.blend or .zip)
        sanitize: Whether to sanitize the file before import
        temp_dir: Temporary directory for extraction (if applicable)
        blend_path: Path to the .blend file to import from
        texture_search_dir: Directory to search for textures
    """

    def __init__(self, file_path: str, sanitize: bool = True):
        """Initialize the applier.

        Args:
            file_path: Path to the asset file (.blend or .zip)
            sanitize: Whether to run the sanitizer before import (default: True)
        """
        self.file_path = file_path
        self.sanitize = sanitize
        self.temp_dir: Optional[str] = None
        self.blend_path: Optional[str] = None
        self.texture_search_dir: Optional[str] = None
        self._sanitized_path: Optional[str] = None
        self._created_temp_dir: bool = False

    def prepare(self) -> bool:
        """Prepare the asset for import.

        This method:
        1. Extracts .zip archives if needed
        2. Locates the .blend file
        3. Runs the sanitizer if enabled
        4. Sets up texture search directory

        Returns:
            True if preparation was successful, False otherwise
        """
        from .utils import extract_archive, find_blend_files

        try:
            # Handle zip files
            if self.file_path.lower().endswith('.zip'):
                _log(f"Extracting archive: {os.path.basename(self.file_path)}")
                self.temp_dir = tempfile.mkdtemp(prefix="blendflare_")
                self._created_temp_dir = True
                extract_archive(self.file_path, self.temp_dir)
                blend_files = find_blend_files(self.temp_dir)
                self.texture_search_dir = self.temp_dir
                _log(f"Extracted to: {self.temp_dir}")
            else:
                # Direct .blend file
                _log(f"Using direct .blend file: {os.path.basename(self.file_path)}")
                blend_files = [self.file_path]
                self.texture_search_dir = os.path.dirname(self.file_path)

            if not blend_files:
                _log("ERROR: No .blend files found")
                return False

            self.blend_path = blend_files[0]
            _log(f"Found .blend file: {os.path.basename(self.blend_path)}")

            # Sanitize if requested
            if self.sanitize:
                _log("Sanitization enabled, running sanitizer...")
                from ..sanitizer import get_sanitizer
                sanitizer = get_sanitizer()
                self._sanitized_path = sanitizer.sanitize_file(self.blend_path)
                self.blend_path = self._sanitized_path
            else:
                _log("Sanitization disabled by user")

            return True

        except Exception as e:
            print(f"Error preparing asset: {e}")
            return False

    @abstractmethod
    def apply(self, context: bpy.types.Context) -> ApplyResult:
        """Apply the asset to the scene.

        This method must be implemented by subclasses to handle category-specific
        import and application logic.

        Args:
            context: The current Blender context

        Returns:
            ApplyResult with success status and details
        """
        pass

    def cleanup(self):
        """Clean up temporary files created during the import process."""
        import shutil

        # Remove sanitized temp file
        if self._sanitized_path and os.path.exists(self._sanitized_path):
            try:
                os.remove(self._sanitized_path)
            except OSError:
                pass
            self._sanitized_path = None

        # Remove temp extraction directory (only if we created it)
        if self._created_temp_dir and self.temp_dir:
            system_temp = tempfile.gettempdir()
            if self.temp_dir.startswith(system_temp):
                try:
                    shutil.rmtree(self.temp_dir, ignore_errors=True)
                except Exception:
                    pass
            self.temp_dir = None
            self._created_temp_dir = False


def get_applier_for_category(
    category: str,
    file_path: str,
    sanitize: bool = True,
    asset_name: str = "Imported Asset",
    asset_metadata: dict = None
) -> BaseAssetApplier:
    """Factory function to get the appropriate applier for a category.

    Args:
        category: Asset category (materials, hdris, scenes, or 3D model subcategory)
        file_path: Path to the asset file
        sanitize: Whether to sanitize the file before import
        asset_name: Name for the asset (used for collections/objects)
        asset_metadata: Optional metadata dict with slug, author, etc.

    Returns:
        The appropriate BaseAssetApplier subclass instance

    Raises:
        NotImplementedError: If the category doesn't have an applier yet
    """
    from .materials import MaterialApplier
    from .models import ModelApplier
    from .scenes import SceneApplier
    from .hdris import HdriApplier

    category_lower = category.lower()

    # 3D model subcategories
    model_categories = {
        "architecture", "character", "accessories", "decoration",
        "industrial", "interior", "military", "nature", "space",
        "sport_hobby", "technology", "transport"
    }

    if category_lower == "materials":
        return MaterialApplier(file_path, sanitize)

    elif category_lower == "hdris":
        applier = HdriApplier(file_path, sanitize, asset_name)
        if asset_metadata:
            applier.set_metadata(
                slug=asset_metadata.get("slug", ""),
                category=asset_metadata.get("category", ""),
                author=asset_metadata.get("author", "")
            )
        return applier

    elif category_lower == "scenes":
        applier = SceneApplier(file_path, sanitize, asset_name)
        if asset_metadata:
            applier.set_metadata(
                slug=asset_metadata.get("slug", ""),
                category=asset_metadata.get("category", ""),
                author=asset_metadata.get("author", "")
            )
        return applier

    elif category_lower in model_categories:
        applier = ModelApplier(file_path, sanitize, asset_name)
        if asset_metadata:
            applier.set_metadata(
                slug=asset_metadata.get("slug", ""),
                category=asset_metadata.get("category", ""),
                author=asset_metadata.get("author", "")
            )
        return applier

    else:
        raise NotImplementedError(f"Applier for category '{category}' not yet implemented")
