"""Toast notification manager singleton."""

import bpy
import time
from typing import Dict, Optional

from ...widgets.bl_ui_toast import BL_UI_Toast, ToastType
from ...logger import toast_logger


class ToastManager:
    """Singleton manager for toast notifications.

    Handles:
    - Toast queue and lifecycle
    - Drawing toasts at center-bottom of viewport
    - Auto-dismiss with configurable duration
    - Progress updates (reusing same toast ID)
    - Stacking multiple toasts vertically
    """

    _instance = None

    # Layout constants
    BOTTOM_MARGIN = 10
    TOAST_SPACING = 6
    MAX_VISIBLE_TOASTS = 5

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._toasts: Dict[str, BL_UI_Toast] = {}
            cls._instance._draw_handler = None
            cls._instance._timer_running = False
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'ToastManager':
        """Get or create the singleton instance."""
        return cls()

    def show(
        self,
        message: str,
        toast_type: str = ToastType.INFO,
        duration: float = 3.0,
        toast_id: Optional[str] = None,
    ) -> str:
        """Show a toast notification.

        Args:
            message: Text message to display
            toast_type: One of ToastType constants
            duration: Auto-dismiss time in seconds (0 = manual dismiss only)
            toast_id: Optional ID for updates (auto-generated if not provided)

        Returns:
            The toast ID (for later updates or dismissal)
        """
        if toast_id is None:
            toast_id = f"toast_{int(time.time() * 1000)}"

        if toast_id in self._toasts:
            toast = self._toasts[toast_id]
            toast.message = message
            toast.toast_type = toast_type
            toast._duration = duration
            toast.reset_timer()
        else:
            toast = BL_UI_Toast(toast_id, message, toast_type, duration)
            self._toasts[toast_id] = toast

        self._ensure_handlers()
        self._force_redraw()

        return toast_id

    def show_progress(
        self,
        message: str,
        progress: float,
        toast_id: str,
        duration: float = 0.0,
    ) -> str:
        """Show or update a progress toast.

        Args:
            message: Text message to display
            progress: Progress value 0.0 to 1.0
            toast_id: ID for this progress toast (required for updates)
            duration: Auto-dismiss time (0 = no auto-dismiss while in progress)

        Returns:
            The toast ID
        """
        if toast_id in self._toasts:
            toast = self._toasts[toast_id]
            toast.message = message
            toast.progress = progress
            toast.reset_timer()
        else:
            toast = BL_UI_Toast(toast_id, message, ToastType.PROGRESS, duration)
            toast.progress = progress
            self._toasts[toast_id] = toast

        self._ensure_handlers()
        self._force_redraw()

        return toast_id

    def dismiss(self, toast_id: str):
        """Dismiss a toast by ID."""
        if toast_id in self._toasts:
            del self._toasts[toast_id]
            self._force_redraw()

            if not self._toasts:
                self._unregister_handlers()

    def dismiss_all(self):
        """Dismiss all toasts."""
        self._toasts.clear()
        self._unregister_handlers()
        self._force_redraw()

    def _ensure_handlers(self):
        """Ensure draw handler and timer are registered."""
        if self._draw_handler is None:
            self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                self._draw_callback, (), 'WINDOW', 'POST_PIXEL'
            )

        if not self._timer_running:
            self._timer_running = True
            bpy.app.timers.register(self._timer_callback, first_interval=0.1, persistent=True)

    def _unregister_handlers(self):
        """Unregister draw handler."""
        if self._draw_handler is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            except Exception:
                pass
            self._draw_handler = None

        self._timer_running = False

    def _timer_callback(self) -> Optional[float]:
        """Timer callback for auto-dismiss."""
        if not self._toasts or not self._timer_running:
            self._timer_running = False
            return None

        expired = [tid for tid, toast in self._toasts.items() if toast.is_expired]
        for tid in expired:
            del self._toasts[tid]

        if expired:
            self._force_redraw()

        if not self._toasts:
            self._unregister_handlers()
            return None

        return 0.1

    def _draw_callback(self):
        """Draw callback for rendering toasts."""
        if not self._toasts:
            return

        try:
            area_width, area_height = self._get_area_size()

            sorted_toasts = sorted(
                self._toasts.values(),
                key=lambda t: t._created_at
            )[:self.MAX_VISIBLE_TOASTS]

            current_y = self.BOTTOM_MARGIN

            for toast in sorted_toasts:
                toast_x = (area_width - toast.width) / 2
                toast.update(toast_x, current_y)
                toast.draw()
                current_y += toast.height + self.TOAST_SPACING

        except Exception as e:
            toast_logger.error(f"Draw error: {e}")

    def _get_area_size(self):
        """Get current viewport size."""
        try:
            if bpy.context and bpy.context.area:
                return bpy.context.area.width, bpy.context.area.height
        except Exception:
            pass
        return 800, 600

    def _force_redraw(self):
        """Force redraw of all 3D viewports."""
        try:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
        except Exception:
            pass

    @classmethod
    def cleanup(cls):
        """Cleanup on addon unregister."""
        if cls._instance:
            cls._instance.dismiss_all()
            cls._instance._unregister_handlers()
            cls._instance = None


# Convenience functions
def show_toast(
    message: str,
    toast_type: str = ToastType.INFO,
    duration: float = 3.0,
    toast_id: Optional[str] = None,
) -> str:
    """Show a toast notification."""
    return ToastManager.get_instance().show(message, toast_type, duration, toast_id)


def show_progress_toast(
    message: str,
    progress: float,
    toast_id: str,
    duration: float = 0.0,
) -> str:
    """Show or update a progress toast."""
    return ToastManager.get_instance().show_progress(message, progress, toast_id, duration)


def dismiss_toast(toast_id: str):
    """Dismiss a toast by ID."""
    ToastManager.get_instance().dismiss(toast_id)


def dismiss_all_toasts():
    """Dismiss all toasts."""
    ToastManager.get_instance().dismiss_all()
