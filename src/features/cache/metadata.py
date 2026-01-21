"""Metadata handling for cached Blendflare assets."""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Optional


METADATA_VERSION = "1.0"


@dataclass
class ProjectMetadata:
    """Project information stored in cache metadata."""

    slug: str
    title: str
    category: str
    subcategory: str
    author_nickname: str
    blender_version: str
    render_engine: str
    file_name: str
    last_updated: str  # ISO format datetime string

    @classmethod
    def from_project(cls, project: Any) -> "ProjectMetadata":
        """Create ProjectMetadata from a Project API response object."""
        return cls(
            slug=project.slug,
            title=project.project_info.title,
            category=project.category,
            subcategory=project.subcategory,
            author_nickname=project.author.nickname,
            blender_version=project.technical_specs.blender_version.full_version,
            render_engine=project.technical_specs.render_engine,
            file_name=project.file_info.file_name,
            last_updated=project.last_updated.isoformat() if isinstance(project.last_updated, datetime) else project.last_updated,
        )


@dataclass
class DownloadMetadata:
    """Download information stored in cache metadata."""

    downloaded_at: str  # ISO format datetime string
    file_size: int

    @classmethod
    def create(cls, file_size: int) -> "DownloadMetadata":
        """Create DownloadMetadata with current timestamp."""
        return cls(
            downloaded_at=datetime.utcnow().isoformat() + "Z",
            file_size=file_size,
        )


@dataclass
class CacheMetadata:
    """Complete metadata for a cached asset (bf.meta.json)."""

    version: str = field(default=METADATA_VERSION)
    project_data: Optional[ProjectMetadata] = None
    download_data: Optional[DownloadMetadata] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "project_data": asdict(self.project_data) if self.project_data else None,
            "download_data": asdict(self.download_data) if self.download_data else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheMetadata":
        """Create CacheMetadata from dictionary."""
        project_data = None
        download_data = None

        if data.get("project_data"):
            project_data = ProjectMetadata(**data["project_data"])

        if data.get("download_data"):
            download_data = DownloadMetadata(**data["download_data"])

        return cls(
            version=data.get("version", METADATA_VERSION),
            project_data=project_data,
            download_data=download_data,
        )

    @classmethod
    def from_project(cls, project: Any, file_size: int) -> "CacheMetadata":
        """Create CacheMetadata from a Project API response object."""
        return cls(
            version=METADATA_VERSION,
            project_data=ProjectMetadata.from_project(project),
            download_data=DownloadMetadata.create(file_size),
        )

    def save(self, path: str) -> None:
        """Save metadata to a JSON file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> Optional["CacheMetadata"]:
        """Load metadata from a JSON file.

        Returns:
            CacheMetadata instance or None if file doesn't exist or is invalid
        """
        if not os.path.exists(path):
            return None

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def is_outdated(self, current_last_updated: str) -> bool:
        """Check if cached version is older than the current version.

        Args:
            current_last_updated: ISO format datetime string from API

        Returns:
            True if cache is outdated and needs to be refreshed
        """
        if not self.project_data:
            return True

        try:
            # Parse both timestamps
            cached_time = datetime.fromisoformat(
                self.project_data.last_updated.replace("Z", "+00:00")
            )
            current_time = datetime.fromisoformat(
                current_last_updated.replace("Z", "+00:00")
            )
            return current_time > cached_time
        except (ValueError, AttributeError):
            # If we can't parse, assume outdated
            return True

    def get_last_updated_display(self) -> str:
        """Get a human-readable last updated string."""
        if not self.project_data:
            return "Unknown"

        try:
            dt = datetime.fromisoformat(
                self.project_data.last_updated.replace("Z", "+00:00")
            )
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, AttributeError):
            return self.project_data.last_updated
