"""Scene asset applier for Blendflare.

This module handles importing complete scenes from .blend files by appending
the entire Scene datablock, which preserves:
- Collection hierarchy structure
- Compositor nodes
- Camera settings (resolution, aspect ratio, etc.)
- World/HDRI settings
- All render settings
- Object relationships and parenting

This is the most accurate way to clone a scene from an external .blend file.
"""

import os
from typing import List, Optional, Dict, Set

import bpy

from .base import ApplyResult, BaseAssetApplier
from .utils import find_blend_files
from ...logger import scene_logger as _log


class SceneApplier(BaseAssetApplier):
    """Applies complete scenes from .blend files to the user's project.

    This applier uses the "append Scene datablock" approach which creates
    an exact copy of the source scene, preserving:
    - All collections and their hierarchy
    - Compositor node setup
    - Camera settings (resolution, orientation, etc.)
    - World/HDRI with textures
    - Render settings
    - All object relationships

    The workflow:
    1. Prepare (extract archive + identify main file + sanitize)
    2. Append the entire Scene datablock from the source file
    3. Rename the scene to the asset name
    4. Pack all external textures
    5. Switch context to the new scene
    """

    def __init__(self, file_path: str, sanitize: bool = True, asset_name: str = "Imported Scene"):
        """Initialize the scene applier.

        Args:
            file_path: Path to the asset file (.blend or .zip)
            sanitize: Whether to run the sanitizer before import
            asset_name: Name for the new scene
        """
        super().__init__(file_path, sanitize)
        self.asset_name = asset_name
        self.asset_metadata: Dict[str, str] = {}
        self.available_scenes: List[str] = []
        self.selected_scene: Optional[str] = None

    def set_metadata(self, slug: str = "", category: str = "", author: str = ""):
        """Set metadata to be stored on the scene.

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

    def prepare(self) -> bool:
        """Prepare the asset for import.

        Overrides BaseAssetApplier.prepare() to:
        1. Identify the main .blend file when dealing with multi-file archives
        2. List available scenes in the file
        """
        import tempfile
        from .utils import extract_archive

        try:
            # Handle zip files
            if self.file_path.lower().endswith('.zip'):
                _log(f"Extracting archive: {os.path.basename(self.file_path)}")
                self.temp_dir = tempfile.mkdtemp(prefix="blendflare_scene_")
                self._created_temp_dir = True
                extract_archive(self.file_path, self.temp_dir)
                blend_files = find_blend_files(self.temp_dir)
                self.texture_search_dir = self.temp_dir
                _log(f"Extracted to: {self.temp_dir}")
                _log(f"Found {len(blend_files)} .blend file(s)")
            else:
                # Direct .blend file
                _log(f"Using direct .blend file: {os.path.basename(self.file_path)}")
                blend_files = [self.file_path]
                self.texture_search_dir = os.path.dirname(self.file_path)

            if not blend_files:
                _log("ERROR: No .blend files found")
                return False

            # Identify the main file (by size for scenes)
            self.blend_path = self._identify_main_blend(blend_files)
            _log(f"Using main .blend file: {os.path.basename(self.blend_path)}")

            # List available scenes
            self.available_scenes = self._list_available_scenes(self.blend_path)
            if self.available_scenes:
                _log(f"Available scenes: {', '.join(self.available_scenes)}")
                self.selected_scene = self.available_scenes[0]
            else:
                _log("WARNING: No scenes found in file")

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
            _log(f"Error preparing asset: {e}")
            return False

    def apply(self, context: bpy.types.Context) -> ApplyResult:
        """Apply the scene from the asset file.

        Appends the entire Scene datablock which preserves all settings,
        collections, compositor nodes, and camera configuration.

        Args:
            context: The current Blender context

        Returns:
            ApplyResult with success status and details
        """
        warnings = []

        if not self.blend_path:
            return ApplyResult(
                success=False,
                message="No .blend file prepared",
                warnings=warnings
            )

        if not self.selected_scene:
            return ApplyResult(
                success=False,
                message="No scene selected for import",
                warnings=warnings
            )

        _log(f"Appending scene '{self.selected_scene}' from: {os.path.basename(self.blend_path)}")

        # Track existing scenes before append
        existing_scenes = set(bpy.data.scenes.keys())
        existing_images = set(bpy.data.images.keys())

        # Step 1: Append the entire Scene datablock
        try:
            appended_scene = self._append_scene_datablock(self.blend_path, self.selected_scene)
        except Exception as e:
            return ApplyResult(
                success=False,
                message=f"Failed to append scene: {str(e)}",
                warnings=warnings
            )

        if not appended_scene:
            return ApplyResult(
                success=False,
                message="Scene was not appended correctly",
                warnings=warnings
            )

        _log(f"Successfully appended scene: {appended_scene.name}")

        # Step 2: Rename scene to asset name (with unique suffix if needed)
        original_name = appended_scene.name
        new_name = self._get_unique_scene_name(self.asset_name)
        appended_scene.name = new_name
        _log(f"Renamed scene from '{original_name}' to '{new_name}'")

        # Step 3: Set metadata on scene
        for key, value in self.asset_metadata.items():
            appended_scene[key] = value

        # Step 3.5: Mark scene as Blender asset for Asset Browser
        self._mark_as_asset(appended_scene)

        # Step 4: Collect newly imported images
        imported_images = [
            img for img in bpy.data.images
            if img.name not in existing_images and img is not None
        ]
        _log(f"Imported {len(imported_images)} image(s)")

        # Step 5: Pack all textures to make scene self-contained
        _log("Packing textures...")
        pack_count = self._pack_all_scene_textures(appended_scene, imported_images)
        if pack_count > 0:
            _log(f"Packed {pack_count} texture(s)")
            warnings.append(f"Packed {pack_count} texture(s)")

        # Step 6: Switch context to new scene
        context.window.scene = appended_scene
        _log(f"Switched to scene: {appended_scene.name}")

        # Step 7: Log scene info
        self._log_scene_info(appended_scene)

        # Count objects in scene
        object_count = len(appended_scene.collection.all_objects)
        collection_count = len(appended_scene.collection.children_recursive) + 1

        message = f"Imported scene '{new_name}' with {object_count} object(s) in {collection_count} collection(s)"

        return ApplyResult(
            success=True,
            message=message,
            applied_items=[new_name],
            warnings=warnings
        )

    def _identify_main_blend(self, blend_files: List[str]) -> str:
        """Identify the main .blend file from multiple files.

        For scenes, we prioritize by file size since the main scene file
        typically contains more data than linked library files.

        Priority:
        1. Files with conventional names (main, master, scene)
        2. Largest file by size
        3. First file if only one exists
        """
        if len(blend_files) == 1:
            return blend_files[0]

        # Check for conventional names
        conventional_names = {'main.blend', 'scene.blend', 'master.blend'}
        for blend_file in blend_files:
            filename = os.path.basename(blend_file).lower()
            if filename in conventional_names:
                _log(f"Found conventionally named main file: {filename}")
                return blend_file

        # Use largest file (main scene typically has most data)
        largest = max(blend_files, key=lambda x: os.path.getsize(x))
        largest_size = os.path.getsize(largest) / (1024 * 1024)  # MB
        _log(f"Using largest file as main: {os.path.basename(largest)} ({largest_size:.2f} MB)")
        return largest

    def _list_available_scenes(self, blend_path: str) -> List[str]:
        """List all scenes available in a .blend file."""
        scenes = []
        try:
            with bpy.data.libraries.load(blend_path) as (data_from, data_to):
                scenes = list(data_from.scenes)
        except Exception as e:
            _log(f"Error listing scenes: {e}")

        return scenes

    def _append_scene_datablock(self, blend_path: str, scene_name: str) -> Optional[bpy.types.Scene]:
        """Append an entire Scene datablock from an external .blend file.

        This method appends the scene with all its dependencies:
        - Collections and their hierarchy
        - Objects with materials and textures
        - World/HDRI settings
        - Compositor node setup
        - Camera and render settings

        Args:
            blend_path: Path to the .blend file
            scene_name: Name of the scene to append

        Returns:
            The appended Scene, or None if failed
        """
        # Track existing scenes
        existing_scenes = set(bpy.data.scenes.keys())

        # Normalize path for Blender
        blend_path_normalized = blend_path.replace('\\', '/')

        _log(f"Appending scene datablock using bpy.ops.wm.append...")

        try:
            # Use bpy.ops.wm.append to append the Scene datablock
            # This is the most reliable method to get an exact copy
            result = bpy.ops.wm.append(
                filepath=f"{blend_path_normalized}/Scene/{scene_name}",
                directory=f"{blend_path_normalized}/Scene/",
                filename=scene_name,
                link=False,
                autoselect=False,
                active_collection=False,
                instance_collections=False,
                instance_object_data=False,
                set_fake=False,
                use_recursive=True,  # Important: recursively append dependencies
            )

            if result != {'FINISHED'}:
                _log(f"wm.append returned: {result}")

        except Exception as e:
            _log(f"Error during append: {e}")
            raise

        # Find the newly appended scene
        new_scenes = [
            scene for scene in bpy.data.scenes
            if scene.name not in existing_scenes
        ]

        if not new_scenes:
            _log("ERROR: No new scene found after append")
            return None

        # Return the first new scene (should be the one we appended)
        appended_scene = new_scenes[0]
        _log(f"Found appended scene: {appended_scene.name}")

        return appended_scene

    def _get_unique_scene_name(self, base_name: str) -> str:
        """Get a unique scene name, adding suffix if needed.

        Args:
            base_name: Desired scene name

        Returns:
            Unique scene name
        """
        if base_name not in bpy.data.scenes:
            return base_name

        # Add numeric suffix
        counter = 1
        while f"{base_name}.{counter:03d}" in bpy.data.scenes:
            counter += 1

        return f"{base_name}.{counter:03d}"

    def _pack_all_scene_textures(
        self,
        scene: bpy.types.Scene,
        imported_images: List[bpy.types.Image]
    ) -> int:
        """Pack all textures used by the scene.

        Iterates through all materials, world, and compositor to find
        and pack all image textures.

        Args:
            scene: The scene to process
            imported_images: List of imported images

        Returns:
            Number of textures packed
        """
        packed_count = 0
        processed_images: Set[str] = set()

        def pack_image(image: bpy.types.Image) -> bool:
            """Try to pack a single image. Returns True if packed."""
            if not image or image.name in processed_images:
                return False

            processed_images.add(image.name)

            # Skip if already packed
            if image.packed_file:
                _log(f"  Image '{image.name}' already packed")
                return False

            # Skip generated/render result images
            if image.source in ('GENERATED', 'VIEWER'):
                return False

            try:
                image.pack()
                _log(f"  Packed image: {image.name}")
                return True
            except Exception as e:
                _log(f"  Failed to pack image {image.name}: {e}")
                return False

        # Pack from materials in the scene
        _log("Checking materials for textures...")
        for obj in scene.collection.all_objects:
            if not hasattr(obj, 'material_slots'):
                continue

            for slot in obj.material_slots:
                if not slot.material or not slot.material.use_nodes:
                    continue

                for node in slot.material.node_tree.nodes:
                    if node.type in ('TEX_IMAGE', 'TEX_ENVIRONMENT') and node.image:
                        if pack_image(node.image):
                            packed_count += 1

        # Pack from World (HDRI)
        if scene.world and scene.world.use_nodes:
            _log(f"Checking World '{scene.world.name}' for HDRI...")
            for node in scene.world.node_tree.nodes:
                if node.type in ('TEX_IMAGE', 'TEX_ENVIRONMENT') and node.image:
                    _log(f"  Found World texture: {node.image.name}")
                    if pack_image(node.image):
                        packed_count += 1

        # Pack from Compositor (handle Blender 5.0+ API change)
        compositor_tree = self._get_compositor_node_tree(scene)
        if compositor_tree:
            _log("Checking Compositor for textures...")
            for node in compositor_tree.nodes:
                if node.type == 'IMAGE' and node.image:
                    if pack_image(node.image):
                        packed_count += 1

        # Pack any remaining imported images
        _log("Packing remaining imported images...")
        for image in imported_images:
            if pack_image(image):
                packed_count += 1

        return packed_count

    def _get_compositor_node_tree(self, scene: bpy.types.Scene):
        """Get the compositor node tree, handling Blender version differences.

        In Blender 5.0+, scene.node_tree was removed and replaced with
        scene.compositing_node_group.

        Args:
            scene: The scene to get compositor from

        Returns:
            The compositor NodeTree, or None if not available
        """
        # Blender 5.0+ uses compositing_node_group
        if hasattr(scene, 'compositing_node_group') and scene.compositing_node_group:
            return scene.compositing_node_group

        # Blender 4.x and earlier uses node_tree
        if hasattr(scene, 'node_tree') and scene.node_tree:
            # Check if use_nodes is enabled (pre-5.0)
            if hasattr(scene, 'use_nodes') and scene.use_nodes:
                return scene.node_tree

        return None

    def _log_scene_info(self, scene: bpy.types.Scene):
        """Log information about the imported scene for debugging."""
        _log("=== Scene Info ===")
        _log(f"  Name: {scene.name}")

        # Collections
        collection_count = len(scene.collection.children_recursive) + 1
        _log(f"  Collections: {collection_count}")
        for coll in scene.collection.children:
            _log(f"    - {coll.name}")

        # Objects
        object_count = len(scene.collection.all_objects)
        _log(f"  Objects: {object_count}")

        # World
        if scene.world:
            _log(f"  World: {scene.world.name}")
            if scene.world.use_nodes:
                for node in scene.world.node_tree.nodes:
                    if node.type == 'TEX_ENVIRONMENT':
                        img_name = node.image.name if node.image else "None"
                        _log(f"    HDRI: {img_name}")

        # Camera
        if scene.camera:
            _log(f"  Camera: {scene.camera.name}")
            _log(f"    Resolution: {scene.render.resolution_x}x{scene.render.resolution_y}")

        # Compositor (handle Blender 5.0+ API change)
        compositor_tree = self._get_compositor_node_tree(scene)
        if compositor_tree:
            _log(f"  Compositor: Active ({len(compositor_tree.nodes)} nodes)")
        else:
            _log("  Compositor: Not active")

        _log("==================")

    def _mark_as_asset(self, scene: bpy.types.Scene):
        """Mark a Scene as a Blender asset for the Asset Browser.

        This makes the scene appear in Blender's native Asset Browser under
        "Current File", similar to how BlenderKit handles imported scenes.

        Args:
            scene: Scene to mark as asset
        """
        if not scene:
            return

        try:
            # Mark as asset
            scene.asset_mark()
            _log(f"Marked Scene '{scene.name}' as asset")

            # NOTE: We skip asset_generate_preview() for Scenes because it causes
            # a crash in Blender 5.0.x (EXCEPTION_ACCESS_VIOLATION in icon_preview_startjob_all_sizes).
            # Blender will generate a default preview icon automatically.
            _log(f"Skipping preview generation for Scene (known Blender 5.x issue)")

            # Set asset metadata if available
            if scene.asset_data and self.asset_metadata:
                if self.asset_metadata.get("blendflare_author"):
                    scene.asset_data.author = self.asset_metadata["blendflare_author"]
                if self.asset_metadata.get("blendflare_title"):
                    scene.asset_data.description = f"Blendflare: {self.asset_metadata['blendflare_title']}"
                # Add category as tag
                if self.asset_metadata.get("blendflare_category"):
                    scene.asset_data.tags.new(self.asset_metadata["blendflare_category"])
                # Add "scene" tag for easy filtering
                scene.asset_data.tags.new("scene")

        except Exception as e:
            _log(f"Failed to mark Scene '{scene.name}' as asset: {e}")
