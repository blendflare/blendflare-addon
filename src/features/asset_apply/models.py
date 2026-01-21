"""3D Model asset applier for Blendflare.

This module handles importing 3D models from .blend files, creating a collection
structure similar to BlenderKit, relinking textures, packing them into the current
file, and positioning at the 3D cursor.

Structure created:
- Collection named after asset title
- Empty as root (marked with asset metadata, for easy positioning/scaling)
- All imported objects parented to Empty
- Positioned at 3D cursor
"""

import os
from typing import List, Optional, Dict, Set

import bpy
from mathutils import Vector

from .base import ApplyResult, BaseAssetApplier
from .utils import find_textures, is_image_loaded, get_image_filename
from ..sanitizer import cleanup_after_import


def _log(message: str):
    """Log a message to the console with Blendflare prefix."""
    print(f"[Blendflare Model] {message}")


class ModelApplier(BaseAssetApplier):
    """Applies 3D models from .blend files to the scene.

    The workflow:
    1. Prepare (extract archive + sanitize)
    2. Import objects, materials, and node groups from .blend
    3. Create a collection named after the asset
    4. Create an Empty as root parent (with metadata)
    5. Parent all root-level imported objects to the Empty
    6. Position the Empty at the 3D cursor
    7. Relink and pack textures
    """

    def __init__(self, file_path: str, sanitize: bool = True, asset_name: str = "Imported Model"):
        """Initialize the model applier.

        Args:
            file_path: Path to the asset file (.blend or .zip)
            sanitize: Whether to run the sanitizer before import (default: True)
            asset_name: Name for the collection and Empty (default: "Imported Model")
        """
        super().__init__(file_path, sanitize)
        self.asset_name = asset_name
        self.asset_metadata: Dict[str, str] = {}

    def set_metadata(self, slug: str = "", category: str = "", author: str = ""):
        """Set metadata to be stored on the root Empty.

        Args:
            slug: Project slug identifier
            category: Asset category (e.g., 'architecture', 'character')
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
        """Apply 3D model from the asset file to the scene.

        Args:
            context: The current Blender context

        Returns:
            ApplyResult with imported object names and any warnings
        """
        warnings = []

        if not self.blend_path:
            return ApplyResult(
                success=False,
                message="No .blend file prepared",
                warnings=warnings
            )

        _log(f"Importing 3D model from: {os.path.basename(self.blend_path)}")

        # Import objects and materials
        try:
            imported_objects, imported_materials, imported_node_groups = self._import_from_blend(self.blend_path)
        except Exception as e:
            return ApplyResult(
                success=False,
                message=f"Failed to import model: {str(e)}",
                warnings=warnings
            )

        if not imported_objects:
            return ApplyResult(
                success=False,
                message="No objects found in asset",
                warnings=warnings
            )

        # Filter out None values
        imported_objects = [obj for obj in imported_objects if obj is not None]
        _log(f"Found {len(imported_objects)} valid object(s)")

        if not imported_objects:
            return ApplyResult(
                success=False,
                message="All imported objects were invalid",
                warnings=warnings
            )

        # Run post-import cleanup if sanitization was disabled
        if not self.sanitize:
            _log("Running post-import cleanup (sanitize was disabled)...")
            # Get all materials from imported objects
            all_materials = self._get_all_materials_from_objects(imported_objects)
            all_materials.extend([m for m in imported_materials if m and m not in all_materials])

            cleanup_stats = cleanup_after_import(
                imported_materials=all_materials,
                imported_objects=imported_objects,
                imported_node_groups=imported_node_groups
            )
            if cleanup_stats["texts_removed"] > 0 or cleanup_stats["drivers_removed"] > 0:
                _log(f"Cleanup removed {cleanup_stats['texts_removed']} scripts, {cleanup_stats['drivers_removed']} drivers")
                warnings.append(
                    f"Removed {cleanup_stats['texts_removed']} scripts, "
                    f"{cleanup_stats['drivers_removed']} dangerous drivers"
                )

        # Create collection for the asset
        collection = self._create_collection(context)
        _log(f"Created collection: {collection.name}")

        # Check if there's already a root Empty in the imported objects
        existing_root = self._find_existing_root_empty(imported_objects)

        # Get cursor location for positioning
        cursor_location = context.scene.cursor.location.copy()

        if existing_root:
            # Use the existing Empty as root
            root_empty = existing_root
            _log(f"Using existing root Empty: {root_empty.name}")

            # Add metadata to existing empty
            for key, value in self.asset_metadata.items():
                root_empty[key] = value

            # Mark as Blender asset for Asset Browser
            self._mark_as_asset(root_empty)

            # Link objects to collection (no re-parenting needed)
            linked_count = self._link_objects_to_collection(imported_objects, collection)

            # Calculate offset to move to cursor (from current root position)
            offset = cursor_location - root_empty.location
            # Move the root empty to cursor
            root_empty.location = cursor_location
        else:
            # Create new root Empty at cursor position FIRST
            root_empty = self._create_root_empty(context, collection)
            root_empty.location = cursor_location
            _log(f"Created root Empty: {root_empty.name}")

            # Link objects to collection and parent to Empty
            # Objects will maintain their world positions relative to origin
            linked_count = self._link_and_parent_objects(imported_objects, collection, root_empty, cursor_location)

        _log(f"Linked {linked_count} object(s) to collection")
        _log(f"Positioned at 3D cursor: {cursor_location}")

        # Find and relink textures
        all_materials = self._get_all_materials_from_objects(imported_objects)
        if self.texture_search_dir and all_materials:
            _log(f"Searching for textures in: {self.texture_search_dir}")
            available_textures = find_textures(self.texture_search_dir)
            _log(f"Found {len(available_textures) // 2} texture file(s)")
            if available_textures:
                relink_count = self._relink_textures(all_materials, available_textures)
                if relink_count > 0:
                    _log(f"Relinked {relink_count} texture(s)")
                    warnings.append(f"Relinked {relink_count} texture(s)")

        # Pack textures
        if all_materials:
            _log("Packing textures...")
            pack_count = self._pack_textures(all_materials)
            if pack_count > 0:
                _log(f"Packed {pack_count} texture(s)")
                warnings.append(f"Packed {pack_count} texture(s)")

        # Mark root empty as asset (if not already marked above for existing root)
        if not existing_root:
            self._mark_as_asset(root_empty)

        # Select the root Empty
        self._select_object(context, root_empty)

        object_names = [obj.name for obj in imported_objects]
        _log(f"Imported objects: {', '.join(object_names[:5])}{'...' if len(object_names) > 5 else ''}")

        message = f"Imported {len(object_names)} object(s) into '{collection.name}'"

        return ApplyResult(
            success=True,
            message=message,
            applied_items=object_names,
            warnings=warnings
        )

    def _import_from_blend(self, blend_path: str) -> tuple:
        """Import objects and all related data from a .blend file.

        Imports all data types that a 3D model asset might use:
        - Objects (meshes, empties, armatures, etc.)
        - Materials
        - Node groups (shader nodes, geometry nodes)
        - Images/textures
        - Meshes (object data)
        - Armatures
        - Actions (animations)
        - Particle settings
        - Curves
        - Lattices
        - Shape keys (via meshes)

        Args:
            blend_path: Path to the .blend file

        Returns:
            Tuple of (imported_objects, imported_materials, imported_node_groups)
        """
        imported_objects = []
        imported_materials = []
        imported_node_groups = []

        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            # Core data
            data_to.objects = data_from.objects
            data_to.materials = data_from.materials

            # Node groups (includes both shader node groups AND geometry nodes)
            data_to.node_groups = data_from.node_groups

            # Images/textures (for materials)
            data_to.images = data_from.images

            # Object data types
            data_to.meshes = data_from.meshes
            data_to.armatures = data_from.armatures
            data_to.curves = data_from.curves
            data_to.lattices = data_from.lattices

            # Animation data
            data_to.actions = data_from.actions

            # Particle systems
            data_to.particles = data_from.particles

            # Additional data that objects might reference
            data_to.textures = data_from.textures  # Legacy texture system
            data_to.brushes = data_from.brushes    # Sculpt/paint brushes
            data_to.palettes = data_from.palettes  # Color palettes

            # Collections (preserve internal structure if asset uses them)
            data_to.collections = data_from.collections

        # Log what was imported
        _log(f"Imported data types:")
        _log(f"  Objects: {len(data_to.objects)}")
        _log(f"  Materials: {len(data_to.materials)}")
        _log(f"  Node groups: {len(data_to.node_groups)}")
        _log(f"  Images: {len(data_to.images)}")
        _log(f"  Actions: {len(data_to.actions)}")
        _log(f"  Particles: {len(data_to.particles)}")
        _log(f"  Collections: {len(data_to.collections)}")

        imported_objects = list(data_to.objects)
        imported_materials = list(data_to.materials)
        imported_node_groups = list(data_to.node_groups)

        return imported_objects, imported_materials, imported_node_groups

    def _find_existing_root_empty(self, objects: List[bpy.types.Object]) -> Optional[bpy.types.Object]:
        """Find an existing root Empty in the imported objects.

        Detects if the asset already has a root Empty that parents all other objects.
        This is common in professionally prepared assets (like BlenderKit style).

        Args:
            objects: List of imported objects

        Returns:
            The root Empty object if found, None otherwise
        """
        imported_set = set(objects)

        # Find root-level objects (no parent or parent not in imported set)
        root_objects = [
            obj for obj in objects
            if obj is not None and (obj.parent is None or obj.parent not in imported_set)
        ]

        # Check if there's exactly one root and it's an Empty
        if len(root_objects) == 1:
            root = root_objects[0]
            if root.type == 'EMPTY':
                # Verify it has children in the imported set
                children_in_import = [
                    obj for obj in objects
                    if obj is not None and obj.parent == root
                ]
                if children_in_import:
                    _log(f"Detected existing root Empty with {len(children_in_import)} children")
                    return root

        # Also check for Empty that is parent of most objects
        for obj in objects:
            if obj is None or obj.type != 'EMPTY':
                continue

            # Check if this empty is root-level
            if obj.parent is not None and obj.parent in imported_set:
                continue

            # Count how many imported objects have this as parent
            children_count = sum(
                1 for o in objects
                if o is not None and o.parent == obj
            )

            # If this Empty parents multiple objects and is root-level, use it
            if children_count >= 1:
                _log(f"Detected existing root Empty '{obj.name}' with {children_count} children")
                return obj

        return None

    def _link_objects_to_collection(
        self,
        objects: List[bpy.types.Object],
        collection: bpy.types.Collection
    ) -> int:
        """Link imported objects to collection without changing parenting.

        Used when the asset already has proper hierarchy.

        Args:
            objects: List of imported objects
            collection: Collection to link objects to

        Returns:
            Number of objects linked to collection
        """
        linked_count = 0

        for obj in objects:
            if obj is None:
                continue

            collection.objects.link(obj)
            linked_count += 1

        return linked_count

    def _create_collection(self, context: bpy.types.Context) -> bpy.types.Collection:
        """Create a new collection for the imported asset.

        Args:
            context: The current Blender context

        Returns:
            The created Collection
        """
        # Ensure unique name
        base_name = self.asset_name
        collection = bpy.data.collections.new(base_name)

        # Link to scene
        context.scene.collection.children.link(collection)

        return collection

    def _create_root_empty(
        self,
        context: bpy.types.Context,
        collection: bpy.types.Collection
    ) -> bpy.types.Object:
        """Create an Empty object as the root parent for all imported objects.

        Args:
            context: The current Blender context
            collection: Collection to link the Empty to

        Returns:
            The created Empty object
        """
        empty = bpy.data.objects.new(self.asset_name, None)
        empty.empty_display_type = 'PLAIN_AXES'
        empty.empty_display_size = 1.0

        # Link to collection
        collection.objects.link(empty)

        # Set metadata as custom properties
        for key, value in self.asset_metadata.items():
            empty[key] = value

        return empty

    def _link_and_parent_objects(
        self,
        objects: List[bpy.types.Object],
        collection: bpy.types.Collection,
        parent: bpy.types.Object,
        cursor_location: Vector = None
    ) -> int:
        """Link imported objects to collection and parent root objects to Empty.

        Objects that already have a parent (within the imported hierarchy) keep
        their original parent. Only root-level objects are parented to the Empty.

        The objects maintain their relative positions to each other, but the whole
        group is moved so the Empty (parent) is at cursor_location.

        Args:
            objects: List of imported objects
            collection: Collection to link objects to
            parent: Empty to parent root objects to
            cursor_location: Where the parent Empty is positioned

        Returns:
            Number of objects linked to collection
        """
        linked_count = 0
        imported_set = set(objects)

        # First, find the center/origin of all root objects to calculate offset
        root_objects = [
            obj for obj in objects
            if obj is not None and (obj.parent is None or obj.parent not in imported_set)
        ]

        for obj in objects:
            if obj is None:
                continue

            # Link to collection
            collection.objects.link(obj)
            linked_count += 1

            # Parent root-level objects to the Empty
            if obj.parent is None or obj.parent not in imported_set:
                # Set parent with KEEP_TRANSFORM to preserve relative positions
                obj.parent = parent
                obj.matrix_parent_inverse = parent.matrix_world.inverted()

        return linked_count

    def _get_all_materials_from_objects(self, objects: List[bpy.types.Object]) -> List[bpy.types.Material]:
        """Get all unique materials from imported objects.

        Args:
            objects: List of objects to scan

        Returns:
            List of unique Material objects
        """
        materials = set()

        for obj in objects:
            if obj is None:
                continue

            # Check object material slots
            if hasattr(obj, 'material_slots'):
                for mat_slot in obj.material_slots:
                    if mat_slot.material:
                        materials.add(mat_slot.material)

            # Check mesh data materials
            if obj.type == 'MESH' and obj.data:
                for mat in obj.data.materials:
                    if mat:
                        materials.add(mat)

        return list(materials)

    def _relink_textures(
        self,
        materials: List[bpy.types.Material],
        available_textures: Dict[str, str]
    ) -> int:
        """Find and relink broken texture paths in material nodes.

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
                        _log(f"Failed to relink texture {filename}: {e}")

        return relinked_count

    def _find_texture_path(
        self,
        filename: str,
        available_textures: Dict[str, str]
    ) -> Optional[str]:
        """Find a texture path by filename.

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

        Args:
            materials: List of materials to process

        Returns:
            Number of textures that were packed
        """
        packed_count = 0
        processed_images: Set[str] = set()

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
                    _log(f"Failed to pack texture {image.name}: {e}")

        return packed_count

    def _select_object(self, context: bpy.types.Context, obj: bpy.types.Object):
        """Select an object and make it active.

        Args:
            context: The current Blender context
            obj: Object to select
        """
        try:
            # Deselect all
            bpy.ops.object.select_all(action='DESELECT')

            # Select and make active
            obj.select_set(True)
            context.view_layer.objects.active = obj
        except Exception as e:
            _log(f"Failed to select object: {e}")

    def _mark_as_asset(self, obj: bpy.types.Object):
        """Mark an object as a Blender asset for the Asset Browser.

        This makes the asset appear in Blender's native Asset Browser under
        "Current File", similar to how BlenderKit handles imported assets.

        Args:
            obj: Object to mark as asset
        """
        try:
            # Mark as asset
            obj.asset_mark()
            _log(f"Marked '{obj.name}' as asset")

            # Generate preview thumbnail
            obj.asset_generate_preview()
            _log(f"Generated asset preview for '{obj.name}'")

            # Set asset metadata if available
            if obj.asset_data and self.asset_metadata:
                if self.asset_metadata.get("blendflare_author"):
                    obj.asset_data.author = self.asset_metadata["blendflare_author"]
                if self.asset_metadata.get("blendflare_title"):
                    obj.asset_data.description = f"Blendflare: {self.asset_metadata['blendflare_title']}"
                # Add category as tag
                if self.asset_metadata.get("blendflare_category"):
                    obj.asset_data.tags.new(self.asset_metadata["blendflare_category"])

        except Exception as e:
            _log(f"Failed to mark '{obj.name}' as asset: {e}")
