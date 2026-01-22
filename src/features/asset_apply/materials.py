"""Material asset applier for Blendflare.

This module handles importing materials from .blend files, relinking textures,
packing them into the current file, and applying materials to selected objects.
"""

import os
from typing import List, Optional, Dict

import bpy

from .base import ApplyResult, BaseAssetApplier
from .utils import find_textures, is_image_loaded, get_image_filename
from ..sanitizer import cleanup_after_import
from ...logger import material_logger as _log


class MaterialApplier(BaseAssetApplier):
    """Applies materials from .blend files to selected objects.

    The workflow:
    1. Prepare (extract archive + sanitize)
    2. Import materials from .blend using bpy.data.libraries.load()
    3. Find textures in the extracted/source directory
    4. Relink broken texture paths in material nodes
    5. Pack textures into the current .blend
    6. Mark materials as Blender assets for Asset Browser
    7. Optionally apply first material to the active object
    """

    def __init__(self, file_path: str, sanitize: bool = True, asset_name: str = "Imported Material"):
        """Initialize the material applier.

        Args:
            file_path: Path to the asset file (.blend or .zip)
            sanitize: Whether to run the sanitizer before import (default: True)
            asset_name: Name for metadata tracking (default: "Imported Material")
        """
        super().__init__(file_path, sanitize)
        self.asset_name = asset_name
        self.asset_metadata: Dict[str, str] = {}

    def set_metadata(self, slug: str = "", category: str = "", author: str = ""):
        """Set metadata to be stored on materials.

        Args:
            slug: Project slug identifier
            category: Asset category
            author: Author username
        """
        self.asset_metadata = {
            "blendflare_asset": True,
            "blendflare_slug": slug,
            "blendflare_category": category,
            "blendflare_author": author,
            "blendflare_title": self.asset_name,
        }

    def apply(self, context: bpy.types.Context) -> ApplyResult:
        """Apply materials from the asset file to the scene.

        Args:
            context: The current Blender context

        Returns:
            ApplyResult with imported material names and any warnings
        """
        warnings = []

        if not self.blend_path:
            return ApplyResult(
                success=False,
                message="No .blend file prepared",
                warnings=warnings
            )

        _log(f"Importing materials from: {os.path.basename(self.blend_path)}")

        # Import materials
        try:
            imported_materials = self._import_materials(self.blend_path)
        except Exception as e:
            return ApplyResult(
                success=False,
                message=f"Failed to import materials: {str(e)}",
                warnings=warnings
            )

        if not imported_materials:
            return ApplyResult(
                success=False,
                message="No materials found in asset",
                warnings=warnings
            )

        # Filter out None values (can happen with broken assets)
        imported_materials = [m for m in imported_materials if m is not None]
        _log(f"Found {len(imported_materials)} valid material(s)")

        if not imported_materials:
            return ApplyResult(
                success=False,
                message="All imported materials were invalid",
                warnings=warnings
            )

        # Run post-import cleanup if sanitization was disabled
        if not self.sanitize:
            _log("Running post-import cleanup (sanitize was disabled)...")
            cleanup_stats = cleanup_after_import(imported_materials=imported_materials)
            if cleanup_stats["texts_removed"] > 0 or cleanup_stats["drivers_removed"] > 0:
                _log(f"Cleanup removed {cleanup_stats['texts_removed']} scripts, {cleanup_stats['drivers_removed']} drivers")
                warnings.append(
                    f"Removed {cleanup_stats['texts_removed']} scripts, "
                    f"{cleanup_stats['drivers_removed']} dangerous drivers"
                )

        # Find and relink textures
        if self.texture_search_dir:
            _log(f"Searching for textures in: {self.texture_search_dir}")
            available_textures = find_textures(self.texture_search_dir)
            _log(f"Found {len(available_textures) // 2} texture file(s)")  # Divided by 2 because we index by name and name+ext
            if available_textures:
                relink_count = self._relink_textures(imported_materials, available_textures)
                if relink_count > 0:
                    _log(f"Relinked {relink_count} texture(s)")
                    warnings.append(f"Relinked {relink_count} texture(s)")

        # Pack textures
        _log("Packing textures...")
        pack_count = self._pack_textures(imported_materials)
        if pack_count > 0:
            _log(f"Packed {pack_count} texture(s)")
            warnings.append(f"Packed {pack_count} texture(s)")

        # Mark materials as Blender assets for Asset Browser
        for material in imported_materials:
            self._mark_as_asset(material)

        # Apply to selected object if applicable
        applied_to_object = False
        if context.active_object and context.active_object.type == 'MESH':
            _log(f"Applying material to selected object: {context.active_object.name}")
            applied_to_object = self._apply_to_selected(imported_materials[0], context)

        material_names = [m.name for m in imported_materials]
        _log(f"Imported materials: {', '.join(material_names)}")

        message = f"Imported {len(material_names)} material(s)"
        if applied_to_object:
            message += f" and applied '{material_names[0]}' to {context.active_object.name}"
            _log(f"Applied '{material_names[0]}' to {context.active_object.name}")

        return ApplyResult(
            success=True,
            message=message,
            applied_items=material_names,
            warnings=warnings
        )

    def _import_materials(self, blend_path: str) -> List[bpy.types.Material]:
        """Import all materials from a .blend file.

        Args:
            blend_path: Path to the .blend file

        Returns:
            List of imported Material objects
        """
        imported = []

        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            # Import all materials found in the file
            data_to.materials = data_from.materials

        # data_to.materials now contains the imported materials
        imported = list(data_to.materials)

        return imported

    def _relink_textures(
        self,
        materials: List[bpy.types.Material],
        available_textures: Dict[str, str]
    ) -> int:
        """Find and relink broken texture paths in material nodes.

        Searches through all Image Texture nodes in the materials and attempts
        to relink images that aren't properly loaded.

        Args:
            materials: List of materials to process
            available_textures: Dict mapping texture names to paths

        Returns:
            Number of textures that were relinked
        """
        relinked_count = 0

        for material in materials:
            if not material or not material.use_nodes:
                continue

            for node in material.node_tree.nodes:
                if node.type != 'TEX_IMAGE':
                    continue

                image = node.image
                if not image:
                    continue

                # Check if image is already loaded correctly
                if is_image_loaded(image):
                    continue

                # Get the original filename
                filename = get_image_filename(image)
                if not filename:
                    continue

                # Try to find the texture
                found_path = self._find_texture_path(filename, available_textures)
                if found_path:
                    try:
                        image.filepath = found_path
                        image.reload()
                        relinked_count += 1
                    except Exception as e:
                        _log.error(f"Failed to relink texture {filename}: {e}")

        return relinked_count

    def _find_texture_path(
        self,
        filename: str,
        available_textures: Dict[str, str]
    ) -> Optional[str]:
        """Find a texture path by filename.

        Tries multiple matching strategies:
        1. Exact filename match (case-insensitive)
        2. Filename without extension match

        Args:
            filename: Original texture filename
            available_textures: Dict of available textures

        Returns:
            Path to the found texture, or None if not found
        """
        if not filename:
            return None

        filename_lower = filename.lower()
        name_no_ext = os.path.splitext(filename)[0].lower()

        # Try exact filename match
        if filename_lower in available_textures:
            return available_textures[filename_lower]

        # Try name without extension
        if name_no_ext in available_textures:
            return available_textures[name_no_ext]

        return None

    def _pack_textures(self, materials: List[bpy.types.Material]) -> int:
        """Pack all textures used by materials into the .blend file.

        This ensures the textures are embedded and don't depend on external paths.

        Args:
            materials: List of materials to process

        Returns:
            Number of textures that were packed
        """
        packed_count = 0
        processed_images = set()  # Avoid processing same image twice

        for material in materials:
            if not material or not material.use_nodes:
                continue

            for node in material.node_tree.nodes:
                if node.type != 'TEX_IMAGE':
                    continue

                image = node.image
                if not image or image.name in processed_images:
                    continue

                processed_images.add(image.name)

                # Skip if already packed
                if image.packed_file:
                    continue

                # Only pack if image is loaded
                if not is_image_loaded(image):
                    continue

                try:
                    image.pack()
                    packed_count += 1
                except Exception as e:
                    _log.error(f"Failed to pack texture {image.name}: {e}")

        return packed_count

    def _apply_to_selected(
        self,
        material: bpy.types.Material,
        context: bpy.types.Context
    ) -> bool:
        """Apply a material to the active object.

        Args:
            material: Material to apply
            context: Blender context

        Returns:
            True if material was applied successfully
        """
        obj = context.active_object

        if not obj:
            return False

        if obj.type != 'MESH':
            return False

        try:
            # Check if object has material slots
            if len(obj.data.materials) == 0:
                obj.data.materials.append(material)
            else:
                # Replace the first material slot
                obj.data.materials[0] = material

            return True

        except Exception as e:
            _log.error(f"Failed to apply material to {obj.name}: {e}")
            return False

    def _mark_as_asset(self, material: bpy.types.Material):
        """Mark a material as a Blender asset for the Asset Browser.

        This makes the material appear in Blender's native Asset Browser under
        "Current File", similar to how BlenderKit handles imported materials.

        Args:
            material: Material to mark as asset
        """
        if not material:
            return

        try:
            # Mark as asset
            material.asset_mark()
            _log(f"Marked material '{material.name}' as asset")

            # Generate preview thumbnail
            material.asset_generate_preview()
            _log(f"Generated asset preview for material '{material.name}'")

            # Set asset metadata if available
            if material.asset_data and self.asset_metadata:
                if self.asset_metadata.get("blendflare_author"):
                    material.asset_data.author = self.asset_metadata["blendflare_author"]
                if self.asset_metadata.get("blendflare_title"):
                    material.asset_data.description = f"Blendflare: {self.asset_metadata['blendflare_title']}"
                # Add category as tag
                if self.asset_metadata.get("blendflare_category"):
                    material.asset_data.tags.new(self.asset_metadata["blendflare_category"])
                # Add "material" tag for easy filtering
                material.asset_data.tags.new("material")

            # Also store custom properties on material for backwards compatibility
            for key, value in self.asset_metadata.items():
                material[key] = value

        except Exception as e:
            _log(f"Failed to mark material '{material.name}' as asset: {e}")
