"""Download progress tracker for UI cards.

Tracks active downloads and allows UI components to subscribe to progress updates.
"""

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Set
import bpy


@dataclass
class DownloadState:
    """State of a download for UI display."""
    is_active: bool = False
    progress: float = 0.0  # 0.0 to 1.0
    message: str = ""


# Type for progress callback: (project_key, state) -> None
ProgressCallback = Callable[[str, DownloadState], None]


class DownloadTracker:
    """Singleton tracker for download progress updates.

    Allows UI cards to register for progress updates on specific assets.
    When a download starts/progresses/completes, all registered callbacks
    for that asset are notified.
    """

    def __init__(self):
        # Active download states: key -> DownloadState
        self._states: Dict[str, DownloadState] = {}
        # Callbacks per asset: key -> set of callbacks
        self._callbacks: Dict[str, Set[ProgressCallback]] = {}
        # Global callbacks (notified for all downloads)
        self._global_callbacks: Set[ProgressCallback] = set()

    @staticmethod
    def make_key(nickname: str, slug: str) -> str:
        """Create a unique key for an asset."""
        return f"{nickname}/{slug}"

    def get_state(self, nickname: str, slug: str) -> DownloadState:
        """Get current download state for an asset."""
        key = self.make_key(nickname, slug)
        return self._states.get(key, DownloadState())

    def is_downloading(self, nickname: str, slug: str) -> bool:
        """Check if an asset is currently downloading."""
        return self.get_state(nickname, slug).is_active

    def start_download(self, nickname: str, slug: str):
        """Mark a download as started."""
        key = self.make_key(nickname, slug)
        state = DownloadState(is_active=True, progress=0.0, message="Starting...")
        self._states[key] = state
        self._notify(key, state)

    def update_progress(self, nickname: str, slug: str, progress: float, message: str = ""):
        """Update download progress."""
        key = self.make_key(nickname, slug)
        state = DownloadState(is_active=True, progress=progress, message=message)
        self._states[key] = state
        self._notify(key, state)

    def complete_download(self, nickname: str, slug: str, success: bool = True):
        """Mark a download as completed."""
        key = self.make_key(nickname, slug)
        state = DownloadState(
            is_active=False,
            progress=1.0 if success else 0.0,
            message="Complete" if success else "Failed"
        )
        self._states[key] = state
        self._notify(key, state)
        # Clean up state after a short delay
        def cleanup():
            if key in self._states and not self._states[key].is_active:
                del self._states[key]
            return None
        bpy.app.timers.register(cleanup, first_interval=2.0)

    def register_callback(self, nickname: str, slug: str, callback: ProgressCallback):
        """Register a callback for a specific asset's download progress."""
        key = self.make_key(nickname, slug)
        if key not in self._callbacks:
            self._callbacks[key] = set()
        self._callbacks[key].add(callback)
        # Immediately notify with current state if downloading
        if key in self._states:
            callback(key, self._states[key])

    def unregister_callback(self, nickname: str, slug: str, callback: ProgressCallback):
        """Unregister a callback for a specific asset."""
        key = self.make_key(nickname, slug)
        if key in self._callbacks:
            self._callbacks[key].discard(callback)
            if not self._callbacks[key]:
                del self._callbacks[key]

    def register_global_callback(self, callback: ProgressCallback):
        """Register a callback that receives all download updates."""
        self._global_callbacks.add(callback)

    def unregister_global_callback(self, callback: ProgressCallback):
        """Unregister a global callback."""
        self._global_callbacks.discard(callback)

    def _notify(self, key: str, state: DownloadState):
        """Notify all registered callbacks of a state change.

        Schedules callbacks on main thread since this may be called from download thread.
        """
        def do_notify():
            # Notify specific callbacks
            if key in self._callbacks:
                for callback in list(self._callbacks[key]):
                    try:
                        callback(key, state)
                    except Exception:
                        pass

            # Notify global callbacks
            for callback in list(self._global_callbacks):
                try:
                    callback(key, state)
                except Exception:
                    pass

            # Force redraw all VIEW_3D areas
            self._force_redraw_all()
            return None

        # Schedule on main thread
        bpy.app.timers.register(do_notify, first_interval=0.01)

    def _force_redraw_all(self):
        """Force redraw of all 3D viewports."""
        try:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
        except Exception:
            pass

    def clear(self):
        """Clear all states and callbacks."""
        self._states.clear()
        self._callbacks.clear()
        self._global_callbacks.clear()


# Singleton instance
_tracker: Optional[DownloadTracker] = None


def get_download_tracker() -> DownloadTracker:
    """Get or create the singleton DownloadTracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = DownloadTracker()
    return _tracker


def reset_download_tracker():
    """Reset the download tracker (for testing/cleanup)."""
    global _tracker
    if _tracker:
        _tracker.clear()
    _tracker = None
