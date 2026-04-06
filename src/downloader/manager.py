"""
Async download manager with httpx streaming.

Provides concurrent downloads with progress callbacks, retry logic,
and cancellation support.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from ..utils.exceptions import DownloadError, FileError, NetworkError
from ..utils.sanitize import safe_folder_name
from ..scraper.models import DownloadProgress, DownloadResult, DownloadStatus, MediaItem

logger = logging.getLogger(__name__)

# Default download settings
DEFAULT_CHUNK_SIZE = 8192
DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_MAX_CONCURRENT = 5


class DownloadManager:
    """Async download manager with progress tracking and cancellation."""

    def __init__(
        self,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ):
        """
        Initialize the download manager.

        Args:
            max_concurrent: Maximum concurrent downloads
            chunk_size: Download chunk size in bytes
            timeout: HTTP request timeout
            max_retries: Number of retries on failure
            retry_delay: Base delay between retries (exponential backoff)
        """
        self.max_concurrent = max_concurrent
        self.chunk_size = chunk_size
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_downloads: dict[str, asyncio.Task] = {}
        self._cancelled: set[str] = set()
        self._downloading_files: set[str] = set()
        self._task_paths: dict[str, Path] = {}  # Tracks partial file paths for cleanup
        self._last_progress: dict[str, DownloadProgress] = {}  # Tracks most recent progress for sync
        self._client: httpx.AsyncClient | None = None
        
        logger.info(f"DownloadManager initialized with max_concurrent={max_concurrent}")

    async def __aenter__(self) -> "DownloadManager":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.erome.com/",
            }
        )
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client and cancel all active downloads."""
        for task_id in list(self._active_downloads.keys()):
            await self.cancel(task_id)

        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client."""
        if self._client is None:
            raise RuntimeError("DownloadManager not initialized. Use async context manager.")
        return self._client

    async def download_file(
        self,
        item: MediaItem,
        save_path: Path,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
        task_id: str | None = None,
    ) -> DownloadResult:
        """
        Download a single file with progress tracking.

        Args:
            item: MediaItem to download
            save_path: Full path to save the file
            progress_callback: Optional callback for progress updates
            task_id: Optional task ID for cancellation tracking

        Returns:
            DownloadResult with status and file info
        """
        task_id = task_id or item.filename

        # Check if already exists
        if save_path.exists():
            logger.info(f"File already exists: {save_path}")
            return DownloadResult(
                filename=item.filename,
                status=DownloadStatus.SKIPPED,
                filepath=str(save_path),
                size_bytes=save_path.stat().st_size,
            )

        # Create parent directory
        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise FileError(f"Failed to create directory", path=str(save_path.parent), details=str(e))

        # Download with retries
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            if task_id in self._cancelled:
                self._cancelled.discard(task_id)
                return DownloadResult(
                    filename=item.filename,
                    status=DownloadStatus.CANCELLED,
                )

            try:
                result = await self._download_with_progress(
                    item, save_path, progress_callback, task_id
                )
                if result.status == DownloadStatus.CANCELLED:
                    return result
                return result
            except Exception as e:
                # Critical: Check if the error itself was caused by a cancellation
                # we missed elsewhere, but usually result.status is the way.
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Download attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)

        # All retries failed
        error_msg = str(last_error) if last_error else "Unknown error"
        logger.error(f"Download failed after {self.max_retries} attempts: {item.filename}")
        return DownloadResult(
            filename=item.filename,
            status=DownloadStatus.ERROR,
            error=error_msg,
        )

    async def _download_with_progress(
        self,
        item: MediaItem,
        save_path: Path,
        progress_callback: Callable[[DownloadProgress], None] | None,
        task_id: str,
    ) -> DownloadResult:
        """Perform the actual download with streaming."""
        async with self._semaphore:
            try:
                async with self.client.stream("GET", item.url) as response:
                    response.raise_for_status()

                    total = int(response.headers.get("content-length", 0))
                    downloaded = 0
                    start_time = time.monotonic()
                    last_callback_time = start_time

                    # Lock check inside semaphore
                    if item.filename in self._downloading_files:
                        logger.warning(f"File already being downloaded by another task: {item.filename}")
                        return DownloadResult(
                            filename=item.filename,
                            status=DownloadStatus.SKIPPED,
                        )
                    
                    self._downloading_files.add(item.filename)
                    
                    try:
                        # Initial progress
                        if progress_callback:
                            progress_callback(DownloadProgress(
                                filename=item.filename,
                                downloaded=0,
                                total=total,
                                percent=0,
                                speed=0,
                                status=DownloadStatus.DOWNLOADING,
                            ))

                        # Write to temp file first
                        temp_path = save_path.with_suffix(save_path.suffix + ".part")
                        self._task_paths[task_id] = temp_path

                        logger.info(f"Acquired slot [{self.active_count}/{self.max_concurrent}]: {item.filename}")
                        cancelled = False
                        with open(temp_path, "wb") as f:
                            async for chunk in response.aiter_bytes(self.chunk_size):
                                # Check for cancellation
                                if task_id in self._cancelled:
                                    cancelled = True
                                    break

                                # THREADED WRITE: Keep the event loop responsive!
                                await asyncio.to_thread(f.write, chunk)
                                downloaded += len(chunk)

                                # Throttle progress updates to ~10Hz
                                now = time.monotonic()
                                if progress_callback and (now - last_callback_time) >= 0.1:
                                    elapsed = now - start_time
                                    speed = int(downloaded / elapsed) if elapsed > 0 else 0
                                    percent = round((downloaded / total) * 100, 1) if total > 0 else 0
                                    
                                    # LOG: Trace progress backend side
                                    logger.info(f"[PROGRESS] {item.filename}: {percent}%")

                                    progress_callback(DownloadProgress(
                                        filename=item.filename,
                                        downloaded=downloaded,
                                        total=total,
                                        percent=percent,
                                        speed=speed,
                                        status=DownloadStatus.DOWNLOADING,
                                    ))
                                    self._last_progress[item.filename] = DownloadProgress(
                                        filename=item.filename,
                                        downloaded=downloaded,
                                        total=total,
                                        percent=percent,
                                        speed=speed,
                                        status=DownloadStatus.DOWNLOADING,
                                    )
                                    last_callback_time = now

                            if cancelled:
                                self._cancelled.discard(task_id)
                                try:
                                    # Now safe to delete because the 'with open' block is closed
                                    await asyncio.to_thread(temp_path.unlink, missing_ok=True)
                                    logger.info(f"Deleted partial file for cancelled task: {item.filename}")
                                except Exception as e:
                                    logger.warning(f"Failed to delete partial file {temp_path.name}: {e}")
                                
                                return DownloadResult(
                                    filename=item.filename,
                                    status=DownloadStatus.CANCELLED,
                                )
                    finally:
                        if task_id in self._task_paths:
                            del self._task_paths[task_id]
                        if item.filename in self._last_progress:
                            del self._last_progress[item.filename]
                        self._downloading_files.discard(item.filename)

                    # Move temp file to final location
                    temp_path.rename(save_path)

                    # Final progress
                    if progress_callback:
                        progress_callback(DownloadProgress(
                            filename=item.filename,
                            downloaded=total,
                            total=total,
                            percent=100,
                            speed=0,
                            status=DownloadStatus.COMPLETE,
                        ))

                    return DownloadResult(
                        filename=item.filename,
                        status=DownloadStatus.COMPLETE,
                        filepath=str(save_path),
                        size_bytes=downloaded,
                    )

            except httpx.HTTPStatusError as e:
                raise NetworkError(f"HTTP error downloading file", status_code=e.response.status_code)
            except httpx.RequestError as e:
                raise NetworkError(f"Network error downloading file", details=str(e))

    async def download_album(
        self,
        items: list[MediaItem],
        album_name: str,
        base_path: Path,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
    ) -> list[DownloadResult]:
        """
        Download multiple items from an album concurrently.

        Args:
            items: List of MediaItems to download
            album_name: Album name for folder organization
            base_path: Base download directory
            progress_callback: Callback for progress updates

        Returns:
            List of DownloadResults for each item
        """
        # Create album folder
        album_folder = base_path / safe_folder_name(album_name)
        album_folder.mkdir(parents=True, exist_ok=True)

        # Separate videos and images
        results: list[DownloadResult] = []
        tasks: list[asyncio.Task] = []

        for item in items:
            # Create type-specific subfolder
            type_folder = album_folder / ("videos" if item.type.value == "video" else "images")
            save_path = type_folder / item.filename

            # Create task
            task = asyncio.create_task(
                self.download_file(item, save_path, progress_callback, item.filename)
            )
            tasks.append(task)
            self._active_downloads[item.filename] = task

        # Wait for all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        final_results: list[DownloadResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(DownloadResult(
                    filename=items[i].filename,
                    status=DownloadStatus.ERROR,
                    error=str(result),
                ))
            else:
                final_results.append(result)

            # Clean up active downloads
            if items[i].filename in self._active_downloads:
                del self._active_downloads[items[i].filename]

        return final_results

    async def cancel(self, task_id: str) -> bool:
        """
        Cancel an active download and delete its partial file.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancelled, False if not found
        """
        logger.info(f"Cancelling download: {task_id}")
        self._cancelled.add(task_id)

        # Deletion logic for .part file
        if task_id in self._task_paths:
            part_path = self._task_paths[task_id]
            if part_path.exists():
                try:
                    part_path.unlink()
                    logger.info(f"Deleted partial file on cancel: {part_path.name}")
                except Exception as e:
                    logger.error(f"Failed to delete partial file {part_path.name}: {e}")
            del self._task_paths[task_id]

        if task_id in self._active_downloads:
            task = self._active_downloads[task_id]
            task.cancel()
            return True

        return False

    async def cancel_all(self) -> None:
        """Cancel all active downloads."""
        for task_id in list(self._active_downloads.keys()):
            await self.cancel(task_id)

    @property
    def active_count(self) -> int:
        """Number of currently active downloads."""
        return len(self._active_downloads)

    @property
    def is_downloading(self) -> bool:
        """Whether any downloads are active."""
        return len(self._active_downloads) > 0