"""
Pydantic models for Erome Scraper data contracts.

Provides type-safe data structures for albums, media items,
download progress, and API responses.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class MediaType(str, Enum):
    """Type of media item."""

    VIDEO = "video"
    IMAGE = "image"


class DownloadStatus(str, Enum):
    """Status of a download task."""

    PENDING = "pending"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


# --- Media & Album Models ---


class MediaItem(BaseModel):
    """A single media item (video or image) from an album."""

    type: MediaType
    url: str
    filename: str
    thumbnail: str | None = None

    model_config = {"populate_by_name": True}


class ScrapedAlbum(BaseModel):
    """Result of scraping an Erome album."""

    title: str
    media: list[MediaItem]
    original_url: str
    scraped_at: datetime = Field(default_factory=datetime.now)

    @property
    def video_count(self) -> int:
        return sum(1 for m in self.media if m.type == MediaType.VIDEO)

    @property
    def image_count(self) -> int:
        return sum(1 for m in self.media if m.type == MediaType.IMAGE)


# --- Download Progress Models ---


class DownloadProgress(BaseModel):
    """Real-time progress update for a single file download."""

    filename: str
    downloaded: int = 0
    total: int = 0
    percent: float = 0
    speed: float = 0  # bytes/sec
    status: DownloadStatus = DownloadStatus.PENDING
    error: str | None = None
    grid_uid: int | None = None  # For UI sync

    @property
    def is_complete(self) -> bool:
        return self.status in (DownloadStatus.COMPLETE, DownloadStatus.SKIPPED)


class DownloadResult(BaseModel):
    """Final result of a download task."""

    filename: str
    status: DownloadStatus
    filepath: str | None = None
    error: str | None = None
    size_bytes: int = 0


# --- API Request/Response Models ---


class ScrapeRequest(BaseModel):
    """Request to scrape an album URL."""

    url: str


class ScrapeResponse(BaseModel):
    """Response after scraping an album."""

    success: bool
    album: ScrapedAlbum | None = None
    folder_exists: bool = False
    error: str | None = None


class DownloadRequest(BaseModel):
    """Request to start downloading media items."""

    items: list[MediaItem]
    album_name: str
    max_concurrent: int = Field(default=5, ge=1, le=10)


class DownloadResponse(BaseModel):
    """Response after queueing downloads."""

    success: bool
    queued_count: int
    error: str | None = None


class DeleteAlbumRequest(BaseModel):
    """Request to delete an album folder."""

    album_name: str


class SettingsModel(BaseModel):
    """Application settings."""

    download_folder: str = "downloads"
    max_concurrent_downloads: int = Field(default=5, ge=1, le=10)
    video_filter: bool = True
    image_filter: bool = True
    retry_count: int = Field(default=3, ge=0, le=10)
    chunk_size: int = Field(default=8192, ge=4096)


class WebSocketMessage(BaseModel):
    """Message sent via WebSocket for real-time updates."""

    type: Literal["progress", "complete", "error", "album_info", "file_start", "file_complete", "media_added"]
    data: dict


class ErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = False
    error: str
    details: str | None = None