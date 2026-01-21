"""State management for download dialogs."""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class DownloadDialogState:
    """State for the download dialog."""
    project: Any = None
    is_downloading: bool = False
    download_progress: float = 0.0
    download_message: str = ""
    download_error: Optional[str] = None
    downloaded_file_path: Optional[str] = None


# Global state for current download dialog
_current_state: Optional[DownloadDialogState] = None


def get_download_state() -> DownloadDialogState:
    """Get or create the current download state."""
    global _current_state
    if _current_state is None:
        _current_state = DownloadDialogState()
    return _current_state


def set_download_state(project: Any) -> DownloadDialogState:
    """Set a new download state with the given project."""
    global _current_state
    _current_state = DownloadDialogState(project=project)
    return _current_state


def clear_download_state() -> None:
    """Clear the current download state."""
    global _current_state
    _current_state = None
