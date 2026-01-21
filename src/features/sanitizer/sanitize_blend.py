"""Standalone sanitizer script for Blender subprocess.

This script is executed in a separate Blender process to sanitize .blend files
before they are imported into the user's current session.

Usage:
    blender --background --python sanitize_blend.py -- input.blend output.blend

The script removes:
    - All text datablocks (potential scripts)
    - Scripted drivers with Python expressions
    - Registered app handlers
"""

import bpy
import sys


def _log(message: str):
    """Log with prefix for easy filtering."""
    print(f"[Sanitizer] {message}")


def _remove_text_blocks():
    """Remove all text datablocks from the file."""
    count = 0
    for text in list(bpy.data.texts):
        _log(f"  Removing text block: {text.name}")
        bpy.data.texts.remove(text)
        count += 1
    return count


def _remove_scripted_drivers_from_data(data_collection, collection_name: str) -> int:
    """Remove scripted drivers from a data collection.

    Args:
        data_collection: A bpy.data collection (e.g., bpy.data.objects)
        collection_name: Name for logging purposes

    Returns:
        Number of drivers removed
    """
    count = 0
    for item in data_collection:
        if not hasattr(item, 'animation_data') or not item.animation_data:
            continue

        drivers_to_remove = []
        for fcurve in item.animation_data.drivers:
            driver = fcurve.driver
            if driver.type == 'SCRIPTED':
                drivers_to_remove.append(fcurve)

        for fcurve in drivers_to_remove:
            item.animation_data.drivers.remove(fcurve)
            count += 1

    return count


def _remove_all_scripted_drivers() -> int:
    """Remove all scripted drivers from the blend file."""
    total = 0

    # Objects
    total += _remove_scripted_drivers_from_data(bpy.data.objects, "objects")

    # Materials
    total += _remove_scripted_drivers_from_data(bpy.data.materials, "materials")

    # Node trees (shader nodes, compositor, etc.)
    total += _remove_scripted_drivers_from_data(bpy.data.node_groups, "node_groups")

    # Meshes
    total += _remove_scripted_drivers_from_data(bpy.data.meshes, "meshes")

    # Armatures
    total += _remove_scripted_drivers_from_data(bpy.data.armatures, "armatures")

    # Cameras
    total += _remove_scripted_drivers_from_data(bpy.data.cameras, "cameras")

    # Lights
    total += _remove_scripted_drivers_from_data(bpy.data.lights, "lights")

    # Worlds
    total += _remove_scripted_drivers_from_data(bpy.data.worlds, "worlds")

    # Scenes
    total += _remove_scripted_drivers_from_data(bpy.data.scenes, "scenes")

    return total


def _clear_app_handlers():
    """Clear all registered app handlers that could run malicious code."""
    handler_lists = [
        bpy.app.handlers.frame_change_post,
        bpy.app.handlers.frame_change_pre,
        bpy.app.handlers.load_factory_preferences_post,
        bpy.app.handlers.load_factory_startup_post,
        bpy.app.handlers.load_post,
        bpy.app.handlers.load_pre,
        bpy.app.handlers.redo_post,
        bpy.app.handlers.redo_pre,
        bpy.app.handlers.render_cancel,
        bpy.app.handlers.render_complete,
        bpy.app.handlers.render_init,
        bpy.app.handlers.render_post,
        bpy.app.handlers.render_pre,
        bpy.app.handlers.render_stats,
        bpy.app.handlers.render_write,
        bpy.app.handlers.save_post,
        bpy.app.handlers.save_pre,
        bpy.app.handlers.undo_post,
        bpy.app.handlers.undo_pre,
        bpy.app.handlers.version_update,
        bpy.app.handlers.depsgraph_update_post,
        bpy.app.handlers.depsgraph_update_pre,
    ]

    count = 0
    for handler_list in handler_lists:
        count += len(handler_list)
        handler_list.clear()

    return count


def sanitize():
    """Main sanitization function."""
    argv = sys.argv
    separator_idx = argv.index("--") if "--" in argv else -1

    if separator_idx == -1 or len(argv) < separator_idx + 3:
        print("ERROR: Invalid arguments")
        print("Usage: blender --background --python sanitize_blend.py -- input.blend output.blend")
        sys.exit(1)

    input_path = argv[separator_idx + 1]
    output_path = argv[separator_idx + 2]

    _log(f"Input: {input_path}")

    # Open the blend file
    try:
        _log("Opening file...")
        bpy.ops.wm.open_mainfile(filepath=input_path)
        _log("File opened successfully")
    except Exception as e:
        _log(f"ERROR: Failed to open file: {e}")
        sys.exit(1)

    # Remove text blocks
    _log("Checking for text blocks...")
    text_count = _remove_text_blocks()
    _log(f"Text blocks removed: {text_count}")

    # Remove scripted drivers
    _log("Checking for scripted drivers...")
    driver_count = _remove_all_scripted_drivers()
    _log(f"Scripted drivers removed: {driver_count}")

    # Clear app handlers
    _log("Checking app handlers...")
    handler_count = _clear_app_handlers()
    _log(f"App handlers cleared: {handler_count}")

    # Save sanitized file
    try:
        _log("Saving sanitized file...")
        bpy.ops.wm.save_as_mainfile(filepath=output_path)
        _log(f"Done! Output: {output_path}")
    except Exception as e:
        print(f"ERROR: Failed to save file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sanitize()
