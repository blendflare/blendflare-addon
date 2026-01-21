"""Utility functions for asset extraction and file discovery."""

import os
import zipfile
import tempfile
from typing import Dict, List, Optional

import bpy


# Supported texture file extensions
TEXTURE_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.tga', '.tiff', '.tif',
    '.exr', '.hdr', '.bmp', '.dds', '.psd', '.webp'
}


def extract_archive(archive_path: str, extract_dir: Optional[str] = None) -> str:
    """Extract a .zip archive and return the extraction directory.

    Args:
        archive_path: Path to the .zip file
        extract_dir: Directory to extract to. If None, creates a temp directory.

    Returns:
        Path to the extraction directory

    Raises:
        FileNotFoundError: If archive doesn't exist
        zipfile.BadZipFile: If file is not a valid zip
    """
    if not os.path.exists(archive_path):
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    if extract_dir is None:
        extract_dir = tempfile.mkdtemp(prefix="blendflare_")

    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    return extract_dir


def find_blend_files(directory: str) -> List[str]:
    """Recursively find all .blend files in a directory.

    Args:
        directory: Directory to search

    Returns:
        List of absolute paths to .blend files, sorted by modification time (newest first)
    """
    blend_files = []

    if not os.path.exists(directory):
        return blend_files

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.blend') and not file.startswith('.'):
                blend_files.append(os.path.join(root, file))

    # Sort by modification time, newest first
    blend_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

    return blend_files


def find_textures(directory: str) -> Dict[str, str]:
    """Find all texture files in a directory.

    Args:
        directory: Directory to search recursively

    Returns:
        Dict mapping lookup keys to full paths. Each texture is indexed by:
        - Full filename (lowercase): "wood_diffuse.png" -> "/path/to/wood_diffuse.png"
        - Filename without extension (lowercase): "wood_diffuse" -> "/path/to/wood_diffuse.png"

        This allows flexible matching against broken texture paths.
    """
    textures = {}

    if not os.path.exists(directory):
        return textures

    for root, dirs, files in os.walk(directory):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in TEXTURE_EXTENSIONS:
                full_path = os.path.join(root, file)
                name_lower = file.lower()
                name_no_ext = os.path.splitext(file)[0].lower()

                # Index by full filename
                textures[name_lower] = full_path
                # Index by name without extension
                textures[name_no_ext] = full_path

    return textures


def get_texture_search_folder(file_path: str, temp_dir: Optional[str] = None) -> str:
    """Get the appropriate folder to search for textures.

    For .blend files, textures are often in the same directory or a subdirectory.
    For extracted .zip files, textures are in the extraction directory.

    Args:
        file_path: Path to the .blend or .zip file
        temp_dir: Temp extraction directory if applicable

    Returns:
        Directory path to search for textures
    """
    if temp_dir and os.path.exists(temp_dir):
        return temp_dir

    return os.path.dirname(file_path)


def cleanup_temp_directory(temp_dir: str) -> bool:
    """Safely clean up a temporary directory.

    Only removes directories that are in the system temp folder to prevent
    accidental deletion of important files.

    Args:
        temp_dir: Directory to remove

    Returns:
        True if cleaned up successfully, False otherwise
    """
    import shutil

    if not temp_dir:
        return False

    # Safety check: only remove if it's in the temp directory
    system_temp = tempfile.gettempdir()
    if not temp_dir.startswith(system_temp):
        return False

    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return True
    except Exception:
        return False


def is_image_loaded(image: bpy.types.Image) -> bool:
    """Check if a Blender image is properly loaded.

    Args:
        image: A Blender Image datablock

    Returns:
        True if the image has valid pixel data or is already packed
    """
    if not image:
        return False

    # Already packed = loaded
    if image.packed_file:
        return True

    # Generated images are always "loaded"
    if image.source in ('GENERATED', 'VIEWER'):
        return True

    # Check if file exists on disk
    if image.filepath:
        filepath = bpy.path.abspath(image.filepath)
        if filepath and os.path.exists(filepath):
            return True

    # Try to access pixels - this will fail if image is not loaded
    try:
        if image.has_data and len(image.pixels) > 0:
            return True
    except (RuntimeError, AttributeError):
        pass

    return False


def get_image_filename(image: bpy.types.Image) -> Optional[str]:
    """Extract the filename from an image's filepath.

    Handles various path formats including:
    - Absolute paths: /path/to/texture.png
    - Relative paths: //textures/texture.png
    - Raw paths with backslashes or forward slashes

    Args:
        image: A Blender Image datablock

    Returns:
        The filename (e.g., "texture.png") or None if no path
    """
    if not image:
        return None

    filepath = image.filepath
    if not filepath:
        # Try image name as fallback (Blender sometimes stores filename in name)
        if image.name and '.' in image.name:
            return image.name
        return None

    # Try to get absolute path first
    try:
        abs_path = bpy.path.abspath(filepath)
        if abs_path:
            return os.path.basename(abs_path)
    except Exception:
        pass

    # Manual extraction for edge cases
    # Remove Blender's relative path prefix
    if filepath.startswith('//'):
        filepath = filepath[2:]

    # Handle both forward and backslashes
    filepath = filepath.replace('\\', '/')

    # Get the filename part
    parts = filepath.rsplit('/', 1)
    if len(parts) > 1:
        return parts[-1]

    return filepath if filepath else None
