"""Blender version compatibility checking."""

from typing import Tuple

import bpy


def get_current_blender_version() -> Tuple[int, int, int]:
    """Get the current Blender version as a tuple."""
    return bpy.app.version


def get_current_blender_version_string() -> str:
    """Get the current Blender version as a string (e.g., '4.2.0')."""
    major, minor, patch = bpy.app.version
    return f"{major}.{minor}.{patch}"


def parse_version_string(version_str: str) -> Tuple[int, int, int]:
    """Parse a version string like '4.2.0' into a tuple.

    Handles various formats:
    - '4.2.0' -> (4, 2, 0)
    - '4.2' -> (4, 2, 0)
    - '4' -> (4, 0, 0)
    """
    parts = version_str.strip().split('.')
    major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return (major, minor, patch)


def is_version_compatible(required_version: str) -> bool:
    """Check if the current Blender version is compatible with the required version.

    Compatible means the current version is >= required version.

    Args:
        required_version: Version string like '4.2.0'

    Returns:
        True if compatible, False if current Blender is older
    """
    current = get_current_blender_version()
    required = parse_version_string(required_version)

    return current >= required


def get_compatibility_status(required_version: str) -> Tuple[bool, str]:
    """Get compatibility status with a descriptive message.

    Args:
        required_version: Version string like '4.2.0'

    Returns:
        Tuple of (is_compatible, message)
    """
    current_str = get_current_blender_version_string()
    is_compatible = is_version_compatible(required_version)

    if is_compatible:
        return True, f"Compatible (Blender {current_str} >= {required_version})"
    else:
        return False, f"Incompatible (Blender {current_str} < {required_version})"
