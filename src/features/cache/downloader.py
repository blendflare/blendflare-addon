"""Async asset downloader for Blendflare."""

import os
import threading
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional

import bpy

from .manager import get_cache_manager
from .metadata import CacheMetadata
from ..toast import show_toast, show_progress_toast, dismiss_toast, ToastType


class DownloadStatus(Enum):
    """Status of a download operation."""
    PENDING = "pending"
    CHECKING_CACHE = "checking_cache"
    DOWNLOADING = "downloading"
    SAVING = "saving"
    COMPLETED = "completed"
    CACHED = "cached"
    ERROR = "error"


@dataclass
class DownloadProgress:
    """Progress information for a download."""
    status: DownloadStatus
    progress: float  # 0.0 to 1.0
    message: str
    file_path: Optional[str] = None
    error: Optional[str] = None


class AssetDownloader:
    """Handles async downloading of Blendflare assets with caching."""

    def __init__(self):
        self._active_downloads: Dict[str, threading.Thread] = {}

    def _get_api_key(self) -> Optional[str]:
        """Get API key from preferences or environment."""
        try:
            addon_key = __package__.rsplit('.', 2)[0]
            prefs = bpy.context.preferences.addons[addon_key].preferences
            key = getattr(prefs, 'blendflare_api_key', '')
            if key:
                return key
        except Exception:
            pass
        return os.environ.get('BLENDFLARE_API_KEY')

    def _make_download_key(self, nickname: str, slug: str) -> str:
        """Create a unique key for tracking downloads."""
        return f"{nickname}/{slug}"

    def is_downloading(self, nickname: str, slug: str) -> bool:
        """Check if an asset is currently being downloaded."""
        key = self._make_download_key(nickname, slug)
        return key in self._active_downloads

    def download_asset(
        self,
        project: Any,
        on_progress: Optional[Callable[[DownloadProgress], None]] = None,
        on_complete: Optional[Callable[[DownloadProgress], None]] = None,
        force_download: bool = False,
    ) -> bool:
        """Download an asset asynchronously.

        Args:
            project: Project object from the API response
            on_progress: Callback for progress updates (called on main thread)
            on_complete: Callback when download completes (called on main thread)
            force_download: If True, download even if cached

        Returns:
            True if download started, False if already downloading
        """
        nickname = project.author.nickname
        slug = project.slug
        category = project.category

        # Check if already downloading
        if self.is_downloading(nickname, slug):
            return False

        download_key = self._make_download_key(nickname, slug)

        def notify_progress(progress: DownloadProgress):
            """Schedule progress callback on main thread."""
            if on_progress:
                def callback():
                    on_progress(progress)
                    return None
                bpy.app.timers.register(callback, first_interval=0.01)

        def notify_complete(progress: DownloadProgress):
            """Schedule complete callback on main thread and cleanup."""
            self._active_downloads.pop(download_key, None)
            if on_complete:
                def callback():
                    on_complete(progress)
                    return None
                bpy.app.timers.register(callback, first_interval=0.01)

        def worker():
            cache_mgr = get_cache_manager()

            # Import tracker here to avoid circular imports
            from .download_tracker import get_download_tracker
            tracker = get_download_tracker()

            # Notify tracker of download start
            tracker.start_download(nickname, slug)

            # Toast ID for progress updates
            toast_id = f"download_{nickname}_{slug}"
            asset_title = getattr(project.project_info, 'title', slug) if hasattr(project, 'project_info') else slug

            # Show initial progress toast
            def show_initial_toast():
                show_progress_toast(f"Downloading {asset_title}...", 0.0, toast_id)
                return None
            bpy.app.timers.register(show_initial_toast, first_interval=0.01)

            try:
                # Step 1: Check cache
                notify_progress(DownloadProgress(
                    status=DownloadStatus.CHECKING_CACHE,
                    progress=0.1,
                    message="Checking local cache..."
                ))
                tracker.update_progress(nickname, slug, 0.1, "Checking cache...")

                if not force_download:
                    asset_file, metadata_path = cache_mgr.get_cached_asset(
                        category, nickname, slug
                    )

                    if asset_file and metadata_path:
                        # Load and check metadata
                        cached_meta = CacheMetadata.load(metadata_path)

                        if cached_meta:
                            # Get current last_updated from project
                            current_updated = (
                                project.last_updated.isoformat()
                                if hasattr(project.last_updated, 'isoformat')
                                else str(project.last_updated)
                            )

                            # Check if cache is still valid
                            if not cached_meta.is_outdated(current_updated):
                                tracker.complete_download(nickname, slug, success=True)
                                # Toast: using cached
                                def show_cached_toast():
                                    dismiss_toast(toast_id)
                                    show_toast(f"Using cached: {asset_title}", ToastType.INFO, 2.0)
                                    return None
                                bpy.app.timers.register(show_cached_toast, first_interval=0.01)
                                notify_complete(DownloadProgress(
                                    status=DownloadStatus.CACHED,
                                    progress=1.0,
                                    message="Using cached version",
                                    file_path=asset_file
                                ))
                                return

                # Step 2: Get download URL from API
                notify_progress(DownloadProgress(
                    status=DownloadStatus.DOWNLOADING,
                    progress=0.2,
                    message="Getting download URL..."
                ))

                api_key = self._get_api_key()
                if not api_key:
                    tracker.complete_download(nickname, slug, success=False)
                    # Toast: error
                    def show_api_error_toast():
                        dismiss_toast(toast_id)
                        show_toast("API key not configured", ToastType.ERROR, 5.0)
                        return None
                    bpy.app.timers.register(show_api_error_toast, first_interval=0.01)
                    notify_complete(DownloadProgress(
                        status=DownloadStatus.ERROR,
                        progress=0.0,
                        message="API key not configured",
                        error="API key not configured"
                    ))
                    return

                from blendflare import BlendflareClient
                client = BlendflareClient(api_key=api_key)

                download_response = client.download_project(
                    project_slug=slug,
                    nickname=nickname
                )

                download_url = download_response.data.download_url
                file_name = download_response.data.file_name
                file_size = download_response.data.file_size

                # Step 3: Download file
                notify_progress(DownloadProgress(
                    status=DownloadStatus.DOWNLOADING,
                    progress=0.3,
                    message=f"Downloading {file_name}..."
                ))

                # Ensure directory exists
                asset_dir = cache_mgr.ensure_asset_dir(category, nickname, slug)
                file_path = os.path.join(asset_dir, file_name)

                # Download with progress reporting
                def report_hook(block_num, block_size, total_size):
                    if total_size > 0:
                        downloaded = block_num * block_size
                        progress = min(0.3 + (downloaded / total_size) * 0.6, 0.9)
                        percent = int((downloaded / total_size) * 100)
                        tracker.update_progress(nickname, slug, progress, f"{percent}%")
                        # Update progress toast
                        def update_toast():
                            show_progress_toast(f"Downloading... {percent}%", downloaded / total_size, toast_id)
                            return None
                        bpy.app.timers.register(update_toast, first_interval=0.01)
                        notify_progress(DownloadProgress(
                            status=DownloadStatus.DOWNLOADING,
                            progress=progress,
                            message=f"Downloading... {percent}%"
                        ))

                urllib.request.urlretrieve(download_url, file_path, report_hook)

                # Step 4: Save metadata
                notify_progress(DownloadProgress(
                    status=DownloadStatus.SAVING,
                    progress=0.95,
                    message="Saving metadata..."
                ))

                metadata = CacheMetadata.from_project(project, file_size)
                metadata_path = cache_mgr.get_metadata_path(category, nickname, slug)
                metadata.save(metadata_path)

                # Complete
                tracker.complete_download(nickname, slug, success=True)
                # Toast: success
                def show_success_toast():
                    dismiss_toast(toast_id)
                    show_toast(f"Downloaded: {asset_title}", ToastType.SUCCESS, 3.0)
                    return None
                bpy.app.timers.register(show_success_toast, first_interval=0.01)
                notify_complete(DownloadProgress(
                    status=DownloadStatus.COMPLETED,
                    progress=1.0,
                    message="Download complete",
                    file_path=file_path
                ))

            except Exception as e:
                tracker.complete_download(nickname, slug, success=False)
                # Toast: error
                error_msg = str(e)[:40]
                def show_error_toast():
                    dismiss_toast(toast_id)
                    show_toast(f"Download failed: {error_msg}", ToastType.ERROR, 5.0)
                    return None
                bpy.app.timers.register(show_error_toast, first_interval=0.01)
                notify_complete(DownloadProgress(
                    status=DownloadStatus.ERROR,
                    progress=0.0,
                    message=f"Download failed: {str(e)[:50]}",
                    error=str(e)
                ))

        # Start download thread
        thread = threading.Thread(target=worker, daemon=True)
        self._active_downloads[download_key] = thread
        thread.start()
        return True


# Singleton instance
_downloader: Optional[AssetDownloader] = None


def get_downloader() -> AssetDownloader:
    """Get or create the singleton AssetDownloader instance."""
    global _downloader
    if _downloader is None:
        _downloader = AssetDownloader()
    return _downloader
