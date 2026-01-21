"""HDRI asset applier for Blendflare.

This module handles importing HDRIs from .blend files or .zip archives containing
HDRI image files (.exr, .hdr) and applying them to the current scene's World.

HDRIs on Blendflare always come with a .blend file. There are two scenarios:
1. ZIP contains .exr/.hdr files + .blend file: Use the HDRI images directly
2. Only .blend file: Extract the HDRI from the World nodes and apply it

The workflow:
1. Extract archive if needed
2. Find .blend file and optionally .exr/.hdr files
3. If HDRI images exist, load them directly and set up World nodes
4. If only .blend, import World datablock and extract HDRI configuration
5. Pack all HDRI textures to avoid relative paths
"""

import os
from typing import List, Optional, Dict, Set

import bpy

from .base import ApplyResult, BaseAssetApplier
from .utils import find_blend_files, TEXTURE_EXTENSIONS


def _log(message: str):
    """Log a message to the console with Blendflare prefix."""
    print(f"[Blendflare HDRI] {message}")


# HDRI-specific extensions
HDRI_EXTENSIONS = {'.exr', '.hdr'}


def find_hdri_files(directory: str) -> List[str]:
    """Find all HDRI files (.exr, .hdr) in a directory.

    Args:
        directory: Directory to search recursively

    Returns:
        List of absolute paths to HDRI files
    """
    hdri_files = []

    if not os.path.exists(directory):
        return hdri_files

    for root, dirs, files in os.walk(directory):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in HDRI_EXTENSIONS:
                hdri_files.append(os.path.join(root, file))

    # Sort by file size (largest first, usually higher resolution)
    hdri_files.sort(key=lambda x: os.path.getsize(x), reverse=True)

    return hdri_files


class HdriApplier(BaseAssetApplier):
    """Applies HDRIs from .blend files or image files to the current scene.

    The workflow:
    1. Prepare (extract archive + sanitize .blend if present)
    2. Check for direct HDRI images (.exr, .hdr) in the archive
    3. If HDRI images found: Load directly and set up World nodes
    4. If only .blend: Import World datablock and apply to scene
    5. Pack all HDRI textures into the current file
    """

    def __init__(self, file_path: str, sanitize: bool = True, asset_name: str = "Imported HDRI"):
        """Initialize the HDRI applier.

        Args:
            file_path: Path to the asset file (.blend or .zip)
            sanitize: Whether to run the sanitizer before import
            asset_name: Name for metadata tracking
        """
        super().__init__(file_path, sanitize)
        self.asset_name = asset_name
        self.asset_metadata: Dict[str, str] = {}
        self.hdri_files: List[str] = []

    def set_metadata(self, slug: str = "", category: str = "", author: str = ""):
        """Set metadata to be stored on the World.

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
        1. Handle zip extraction
        2. Find both .blend and HDRI image files
        3. Sanitize .blend if present and sanitization is enabled
        """
        import tempfile
        from .utils import extract_archive

        try:
            # Handle zip files
            if self.file_path.lower().endswith('.zip'):
                _log(f"Extracting archive: {os.path.basename(self.file_path)}")
                self.temp_dir = tempfile.mkdtemp(prefix="blendflare_hdri_")
                self._created_temp_dir = True
                extract_archive(self.file_path, self.temp_dir)
                self.texture_search_dir = self.temp_dir
                _log(f"Extracted to: {self.temp_dir}")

                # Find HDRI image files
                self.hdri_files = find_hdri_files(self.temp_dir)
                if self.hdri_files:
                    _log(f"Found {len(self.hdri_files)} HDRI file(s): {[os.path.basename(f) for f in self.hdri_files]}")

                # Find .blend files
                blend_files = find_blend_files(self.temp_dir)
                if blend_files:
                    self.blend_path = blend_files[0]
                    _log(f"Found .blend file: {os.path.basename(self.blend_path)}")

            elif self.file_path.lower().endswith('.blend'):
                # Direct .blend file
                _log(f"Using direct .blend file: {os.path.basename(self.file_path)}")
                self.blend_path = self.file_path
                self.texture_search_dir = os.path.dirname(self.file_path)

            elif self.file_path.lower().endswith(('.exr', '.hdr')):
                # Direct HDRI file
                _log(f"Using direct HDRI file: {os.path.basename(self.file_path)}")
                self.hdri_files = [self.file_path]
                self.texture_search_dir = os.path.dirname(self.file_path)

            else:
                _log(f"ERROR: Unsupported file format: {self.file_path}")
                return False

            # We need either HDRI files or a .blend file
            if not self.hdri_files and not self.blend_path:
                _log("ERROR: No HDRI files (.exr, .hdr) or .blend files found")
                return False

            # Sanitize .blend if present and sanitization enabled
            if self.blend_path and self.sanitize:
                _log("Sanitization enabled, running sanitizer on .blend...")
                from ..sanitizer import get_sanitizer
                sanitizer = get_sanitizer()
                self._sanitized_path = sanitizer.sanitize_file(self.blend_path)
                self.blend_path = self._sanitized_path
            elif self.blend_path:
                _log("Sanitization disabled by user")

            return True

        except Exception as e:
            _log(f"Error preparing asset: {e}")
            return False

    def apply(self, context: bpy.types.Context) -> ApplyResult:
        """Apply the HDRI to the current scene.

        Strategy:
        1. If HDRI image files exist (.exr, .hdr): Load directly and set up World
        2. If only .blend file: Import World and apply it

        Args:
            context: The current Blender context

        Returns:
            ApplyResult with success status and details
        """
        warnings = []

        # Determine which approach to use
        if self.hdri_files:
            # Direct HDRI files available - use them
            _log("Using direct HDRI image files")
            return self._apply_from_image_files(context, warnings)
        elif self.blend_path:
            # Only .blend file - extract World from it
            _log("Extracting HDRI from .blend file")
            return self._apply_from_blend_file(context, warnings)
        else:
            return ApplyResult(
                success=False,
                message="No HDRI files or .blend file available",
                warnings=warnings
            )

    def _apply_from_image_files(
        self,
        context: bpy.types.Context,
        warnings: List[str]
    ) -> ApplyResult:
        """Apply HDRI from direct image files (.exr, .hdr).

        Creates or updates the World node tree with an Environment Texture.

        Args:
            context: The current Blender context
            warnings: List to append warnings to

        Returns:
            ApplyResult with success status
        """
        if not self.hdri_files:
            return ApplyResult(
                success=False,
                message="No HDRI files found",
                warnings=warnings
            )

        # Use the first (largest) HDRI file
        hdri_path = self.hdri_files[0]
        hdri_filename = os.path.basename(hdri_path)
        _log(f"Loading HDRI: {hdri_filename}")

        try:
            # Load the image
            image = bpy.data.images.load(hdri_path, check_existing=True)
            image.colorspace_settings.name = 'Linear Rec.709'  # HDRIs should be linear
            _log(f"Loaded image: {image.name}")

            # Set up World nodes
            world = self._setup_world_nodes(context, image)

            # Apply metadata to World
            for key, value in self.asset_metadata.items():
                world[key] = value

            # Mark as Blender asset for Asset Browser
            self._mark_as_asset(world)

            # Pack the HDRI
            if not image.packed_file:
                try:
                    image.pack()
                    _log(f"Packed HDRI: {image.name}")
                    warnings.append("Packed HDRI texture")
                except Exception as e:
                    _log(f"Failed to pack HDRI: {e}")
                    warnings.append(f"Failed to pack HDRI: {e}")

            return ApplyResult(
                success=True,
                message=f"Applied HDRI '{hdri_filename}' to scene",
                applied_items=[hdri_filename],
                warnings=warnings
            )

        except Exception as e:
            _log(f"Error loading HDRI: {e}")
            return ApplyResult(
                success=False,
                message=f"Failed to load HDRI: {str(e)}",
                warnings=warnings
            )

    def _apply_from_blend_file(
        self,
        context: bpy.types.Context,
        warnings: List[str]
    ) -> ApplyResult:
        """Apply HDRI by importing World datablock from .blend file.

        Args:
            context: The current Blender context
            warnings: List to append warnings to

        Returns:
            ApplyResult with success status
        """
        if not self.blend_path:
            return ApplyResult(
                success=False,
                message="No .blend file available",
                warnings=warnings
            )

        _log(f"Importing World from: {os.path.basename(self.blend_path)}")

        try:
            # Track existing Worlds before import
            existing_worlds = set(bpy.data.worlds.keys())
            existing_images = set(bpy.data.images.keys())

            # Import Worlds from the .blend file
            imported_worlds = self._import_worlds(self.blend_path)

            if not imported_worlds:
                return ApplyResult(
                    success=False,
                    message="No Worlds found in .blend file",
                    warnings=warnings
                )

            # Filter out None values
            imported_worlds = [w for w in imported_worlds if w is not None]
            if not imported_worlds:
                return ApplyResult(
                    success=False,
                    message="All imported Worlds were invalid",
                    warnings=warnings
                )

            # Use the first imported World
            new_world = imported_worlds[0]
            _log(f"Imported World: {new_world.name}")

            # Apply to current scene
            context.scene.world = new_world

            # Apply metadata
            for key, value in self.asset_metadata.items():
                new_world[key] = value

            # Mark as Blender asset for Asset Browser
            self._mark_as_asset(new_world)

            # Find and relink/pack HDRI textures
            pack_count = self._pack_world_textures(new_world)
            if pack_count > 0:
                _log(f"Packed {pack_count} texture(s)")
                warnings.append(f"Packed {pack_count} texture(s)")

            # Log World info
            self._log_world_info(new_world)

            return ApplyResult(
                success=True,
                message=f"Applied World '{new_world.name}' with HDRI to scene",
                applied_items=[new_world.name],
                warnings=warnings
            )

        except Exception as e:
            _log(f"Error importing World: {e}")
            return ApplyResult(
                success=False,
                message=f"Failed to import World: {str(e)}",
                warnings=warnings
            )

    def _import_worlds(self, blend_path: str) -> List[bpy.types.World]:
        """Import all World datablocks from a .blend file.

        Args:
            blend_path: Path to the .blend file

        Returns:
            List of imported World objects
        """
        imported = []

        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            # Import all Worlds and Images (for HDRI textures)
            data_to.worlds = data_from.worlds
            data_to.images = data_from.images
            # Also import node groups in case World uses custom shader groups
            data_to.node_groups = data_from.node_groups

        imported = list(data_to.worlds)
        _log(f"Imported {len(imported)} World(s), {len(data_to.images)} Image(s)")

        return imported

    def _setup_world_nodes(
        self,
        context: bpy.types.Context,
        hdri_image: bpy.types.Image
    ) -> bpy.types.World:
        """Set up World node tree with HDRI Environment Texture.

        Creates a standard HDRI setup:
        Environment Texture -> Background -> World Output

        Args:
            context: The current Blender context
            hdri_image: The HDRI image to use

        Returns:
            The configured World
        """
        scene = context.scene

        # Get or create World
        if scene.world is None:
            world = bpy.data.worlds.new(name=self.asset_name)
            scene.world = world
        else:
            world = scene.world

        # Enable nodes
        world.use_nodes = True
        nodes = world.node_tree.nodes
        links = world.node_tree.links

        # Clear existing nodes
        nodes.clear()

        # Create nodes
        node_env = nodes.new(type='ShaderNodeTexEnvironment')
        node_env.image = hdri_image
        node_env.location = (-300, 300)

        node_background = nodes.new(type='ShaderNodeBackground')
        node_background.location = (0, 300)

        node_output = nodes.new(type='ShaderNodeOutputWorld')
        node_output.location = (200, 300)

        # Link nodes
        links.new(node_env.outputs['Color'], node_background.inputs['Color'])
        links.new(node_background.outputs['Background'], node_output.inputs['Surface'])

        _log(f"Set up World nodes with HDRI: {hdri_image.name}")

        return world

    def _pack_world_textures(self, world: bpy.types.World) -> int:
        """Pack all HDRI textures used by a World.

        Args:
            world: The World to process

        Returns:
            Number of textures packed
        """
        packed_count = 0
        processed_images: Set[str] = set()

        if not world or not world.use_nodes:
            return packed_count

        for node in world.node_tree.nodes:
            if node.type not in ('TEX_IMAGE', 'TEX_ENVIRONMENT'):
                continue

            image = node.image
            if not image or image.name in processed_images:
                continue

            processed_images.add(image.name)

            # Skip if already packed
            if image.packed_file:
                _log(f"  Image '{image.name}' already packed")
                continue

            # Skip generated images
            if image.source in ('GENERATED', 'VIEWER'):
                continue

            try:
                image.pack()
                _log(f"  Packed image: {image.name}")
                packed_count += 1
            except Exception as e:
                _log(f"  Failed to pack image {image.name}: {e}")

        return packed_count

    def _log_world_info(self, world: bpy.types.World):
        """Log information about the imported World for debugging."""
        _log("=== World Info ===")
        _log(f"  Name: {world.name}")

        if world.use_nodes:
            _log(f"  Node count: {len(world.node_tree.nodes)}")
            for node in world.node_tree.nodes:
                if node.type == 'TEX_ENVIRONMENT':
                    img_name = node.image.name if node.image else "None"
                    _log(f"  HDRI: {img_name}")
                    if node.image:
                        _log(f"    Size: {node.image.size[0]}x{node.image.size[1]}")
                        _log(f"    Packed: {bool(node.image.packed_file)}")

        _log("==================")

    def _mark_as_asset(self, world: bpy.types.World):
        """Mark a World as a Blender asset for the Asset Browser.

        This makes the HDRI/World appear in Blender's native Asset Browser under
        "Current File", similar to how BlenderKit handles imported HDRIs.

        Args:
            world: World to mark as asset
        """
        if not world:
            return

        try:
            # Mark as asset
            world.asset_mark()
            _log(f"Marked World '{world.name}' as asset")

            # Generate preview thumbnail
            world.asset_generate_preview()
            _log(f"Generated asset preview for World '{world.name}'")

            # Set asset metadata if available
            if world.asset_data and self.asset_metadata:
                if self.asset_metadata.get("blendflare_author"):
                    world.asset_data.author = self.asset_metadata["blendflare_author"]
                if self.asset_metadata.get("blendflare_title"):
                    world.asset_data.description = f"Blendflare: {self.asset_metadata['blendflare_title']}"
                # Add category as tag
                if self.asset_metadata.get("blendflare_category"):
                    world.asset_data.tags.new(self.asset_metadata["blendflare_category"])
                # Add "hdri" tag for easy filtering
                world.asset_data.tags.new("hdri")

        except Exception as e:
            _log(f"Failed to mark World '{world.name}' as asset: {e}")
