"""Post-import cleanup for additional safety.

This module provides a secondary safety layer that runs after importing assets.
It removes any potentially dangerous elements that might have bypassed the
subprocess sanitizer (e.g., if sanitization was disabled by the user).
"""

import bpy
from typing import List, Optional, Any


# Patterns that indicate dangerous Python code in driver expressions
DANGEROUS_PATTERNS = [
    "__import__",
    "exec(",
    "eval(",
    "compile(",
    "os.",
    "os.system",
    "subprocess",
    "open(",
    "file(",
    "system(",
    "popen",
    "spawn",
    "builtins",
    "globals(",
    "locals(",
    "getattr(",
    "setattr(",
    "delattr(",
]


def _is_dangerous_expression(expr: str) -> bool:
    """Check if a driver expression contains dangerous patterns.

    Args:
        expr: The driver expression string

    Returns:
        True if the expression contains potentially dangerous code
    """
    if not expr:
        return False

    expr_lower = expr.lower()
    return any(pattern.lower() in expr_lower for pattern in DANGEROUS_PATTERNS)


def _clean_drivers_from_item(item: Any) -> int:
    """Remove dangerous scripted drivers from a single item.

    Args:
        item: A Blender data object that might have animation_data

    Returns:
        Number of drivers removed
    """
    if not item or not hasattr(item, 'animation_data') or not item.animation_data:
        return 0

    count = 0
    drivers_to_remove = []

    for fcurve in item.animation_data.drivers:
        driver = fcurve.driver
        if driver.type == 'SCRIPTED':
            if _is_dangerous_expression(driver.expression):
                drivers_to_remove.append(fcurve)

    for fcurve in drivers_to_remove:
        item.animation_data.drivers.remove(fcurve)
        count += 1

    return count


def cleanup_after_import(
    imported_materials: Optional[List] = None,
    imported_objects: Optional[List] = None,
    imported_node_groups: Optional[List] = None,
) -> dict:
    """Clean up potentially dangerous elements after import.

    This is a secondary safety layer in case subprocess sanitization wasn't used
    or was bypassed. It performs a lighter-weight check focusing on the most
    dangerous patterns.

    Args:
        imported_materials: List of imported Material objects
        imported_objects: List of imported Object objects
        imported_node_groups: List of imported NodeGroup objects

    Returns:
        Dict with cleanup statistics:
        - texts_removed: Number of text blocks removed
        - drivers_removed: Number of dangerous drivers removed
    """
    stats = {
        "texts_removed": 0,
        "drivers_removed": 0,
    }

    # Remove any text blocks that look like scripts
    for text in list(bpy.data.texts):
        # Only remove texts that appear to be scripts
        name_lower = text.name.lower()
        if name_lower.endswith(".py"):
            bpy.data.texts.remove(text)
            stats["texts_removed"] += 1
            continue

        # Check content for script-like patterns
        try:
            content = text.as_string()
            if "import " in content or "def " in content or "class " in content:
                bpy.data.texts.remove(text)
                stats["texts_removed"] += 1
        except Exception:
            # If we can't read it, leave it alone
            pass

    # Clean up drivers on imported materials
    if imported_materials:
        for mat in imported_materials:
            if mat:
                stats["drivers_removed"] += _clean_drivers_from_item(mat)

                # Also check node tree
                if mat.node_tree:
                    stats["drivers_removed"] += _clean_drivers_from_item(mat.node_tree)

    # Clean up drivers on imported objects
    if imported_objects:
        for obj in imported_objects:
            if obj:
                stats["drivers_removed"] += _clean_drivers_from_item(obj)

                # Also check object data (mesh, curve, etc.)
                if obj.data:
                    stats["drivers_removed"] += _clean_drivers_from_item(obj.data)

    # Clean up drivers on imported node groups
    if imported_node_groups:
        for ng in imported_node_groups:
            if ng:
                stats["drivers_removed"] += _clean_drivers_from_item(ng)

    return stats
