"""Toast notification module for Blendflare."""

from .manager import (
    ToastManager,
    show_toast,
    show_progress_toast,
    dismiss_toast,
    dismiss_all_toasts,
)
from ...widgets.bl_ui_toast import ToastType

__all__ = [
    "ToastManager",
    "show_toast",
    "show_progress_toast",
    "dismiss_toast",
    "dismiss_all_toasts",
    "ToastType",
]


def register():
    """Register toast module."""
    pass


def unregister():
    """Unregister toast module."""
    ToastManager.cleanup()
