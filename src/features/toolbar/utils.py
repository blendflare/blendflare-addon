"""Utility helpers for toolbar components"""
from typing import Optional


def get_show_blendflare_header(context) -> bool:
    """Return addon preference if available. Defaults to False."""
    try:
        from ... import addon_key
        prefs = context.preferences.addons[addon_key].preferences
        return bool(prefs.show_blendflare_header)
    except Exception:
        return False


def toggle_show_blendflare_header(context) -> bool:
    """Toggle the global addon preference. Returns new value or False on error."""
    try:
        from ... import addon_key
        prefs = context.preferences.addons[addon_key].preferences
        prefs.show_blendflare_header = not bool(prefs.show_blendflare_header)
        try:
            context.region.tag_redraw()
        except Exception:
            pass
        return bool(prefs.show_blendflare_header)
    except Exception:
        return False


def safe_get_props(context) -> Optional[object]:
    try:
        return context.scene.blendflare_props
    except Exception:
        return None
