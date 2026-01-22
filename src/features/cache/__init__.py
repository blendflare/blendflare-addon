"""Blendflare cache system for local asset storage."""

from ...logger import cache_logger

try:
    from .manager import CacheManager, get_cache_manager
    from .metadata import CacheMetadata
    from .downloader import AssetDownloader, get_downloader
    from .download_tracker import DownloadTracker, get_download_tracker
except ImportError as e:
    cache_logger.error(f"Import error: {e}")
    # Define stubs to prevent further errors
    CacheManager = None
    get_cache_manager = lambda: None
    CacheMetadata = None
    AssetDownloader = None
    get_downloader = lambda: None
    DownloadTracker = None
    get_download_tracker = lambda: None

__all__ = [
    "CacheManager",
    "get_cache_manager",
    "CacheMetadata",
    "AssetDownloader",
    "get_downloader",
    "DownloadTracker",
    "get_download_tracker",
]
