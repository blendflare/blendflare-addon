"""Download dialog system for Blendflare assets."""

from ...logger import download_logger

try:
    from .operators import (
        BLENDFLARE_OT_download_dialog,
        BLENDFLARE_OT_open_download_dialog,
        BLENDFLARE_OT_download_asset,
        BLENDFLARE_OT_download_and_apply_asset,
        BLENDFLARE_OT_download_to_folder_dialog,
        BLENDFLARE_OT_select_download_folder,
        register_progress_property,
        unregister_progress_property,
    )
    from .state import get_download_state, set_download_state, clear_download_state
    _import_ok = True
except Exception as e:
    download_logger.error(f"Import error: {e}")
    import traceback
    traceback.print_exc()
    _import_ok = False
    # Define stubs
    BLENDFLARE_OT_download_dialog = None
    BLENDFLARE_OT_open_download_dialog = None
    BLENDFLARE_OT_download_asset = None
    BLENDFLARE_OT_download_and_apply_asset = None
    BLENDFLARE_OT_download_to_folder_dialog = None
    BLENDFLARE_OT_select_download_folder = None
    register_progress_property = lambda: None
    unregister_progress_property = lambda: None
    get_download_state = lambda: None
    set_download_state = lambda x: None
    clear_download_state = lambda: None

__all__ = [
    "BLENDFLARE_OT_download_dialog",
    "BLENDFLARE_OT_open_download_dialog",
    "BLENDFLARE_OT_download_asset",
    "BLENDFLARE_OT_download_and_apply_asset",
    "BLENDFLARE_OT_download_to_folder_dialog",
    "BLENDFLARE_OT_select_download_folder",
    "get_download_state",
    "set_download_state",
    "clear_download_state",
]


def register():
    """Register download dialog properties."""
    if _import_ok:
        register_progress_property()


def unregister():
    """Unregister download dialog properties."""
    if _import_ok:
        unregister_progress_property()
