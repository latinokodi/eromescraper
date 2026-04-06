"""
FastAPI routes for Erome Scraper API.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket

from ..downloader.manager import DownloadManager
from ..scraper.core import EromeScraper
from ..scraper.models import (
    DownloadRequest,
    DownloadResponse,
    MediaItem,
    ScrapeRequest,
    ScrapeResponse,
    SettingsModel,
    DeleteAlbumRequest,
)
from ..utils.config import config
from ..utils.exceptions import EromeError, ValidationError
from .websocket import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Global state
_active_downloads: dict[str, asyncio.Task] = {}
_download_manager: DownloadManager | None = None


def get_download_manager() -> DownloadManager:
    """Get or create the download manager."""
    global _download_manager
    if _download_manager is None:
        _download_manager = DownloadManager(
            max_concurrent=config.settings.max_concurrent_downloads,
            chunk_size=config.settings.chunk_size,
        )
    return _download_manager


@router.post("/api/scrape", response_model=ScrapeResponse)
async def scrape_album(request: ScrapeRequest) -> ScrapeResponse:
    """
    Scrape an Erome album URL.

    Args:
        request: Scrape request with URL

    Returns:
        Scraped album with media items
    """
    url = request.url
    try:
        async with EromeScraper() as scraper:
            album = await scraper.scrape(url)

        # Check if folder already exists in downloads
        folder_exists = False
        if album.title:
            from ..utils.config import config
            download_dir = Path(config.settings.download_folder)
            album_dir = download_dir / album.title
            
            # Exists and is not empty
            if album_dir.exists() and album_dir.is_dir():
                if any(album_dir.iterdir()):
                    folder_exists = True
                    logger.info(f"Conflict detected: Album folder '{album.title}' already exists and is not empty.")

        # Broadcast album info to WebSocket clients
        await ws_manager.broadcast_album_info(album.title, len(album.media))

        return ScrapeResponse(success=True, album=album, folder_exists=folder_exists)

    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        return ScrapeResponse(success=False, error=str(e))
    except EromeError as e:
        logger.error(f"Scrape error: {e}")
        return ScrapeResponse(success=False, error=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error scraping: {e}")
        return ScrapeResponse(success=False, error=f"Unexpected error: {e}")


@router.post("/api/download", response_model=DownloadResponse)
async def start_download(request: DownloadRequest) -> DownloadResponse:
    """
    Start downloading media items.

    Args:
        request: Download request with items and album name

    Returns:
        Response with queued count
    """
    if not request.items:
        return DownloadResponse(success=False, queued_count=0, error="No items to download")

    album_id = request.album_name
    
    # Check if download is already in progress for this album
    if album_id in _active_downloads and not _active_downloads[album_id].done():
        logger.warning(f"Download already in progress for album: {album_id}")
        return DownloadResponse(
            success=True, 
            queued_count=len(request.items), 
            error="Album is already being downloaded. Task ignored."
        )

    # Persistence: add to queue.json immediately
    from ..utils.queue import queue_manager
    queue_manager.add_album(album_id, request.items)

    async def run_download():
        """Background task to run downloads."""
        try:
            manager = get_download_manager()
            base_path = Path(config.settings.download_folder)

            # Parallelize item downloads within this album task
            async def download_item(item: MediaItem):
                try:
                    # Create save path consistently
                    safe_album = request.album_name.replace(" ", "_").lower()
                    album_folder = base_path / safe_album
                    type_folder = album_folder / ("videos" if item.type.value == "video" else "images")
                    save_path = type_folder / item.filename

                    # Broadcast file start
                    await ws_manager.broadcast_file_start(item.filename)

                    # Download file
                    result = await manager.download_file(
                        item,
                        save_path,
                        lambda p: asyncio.create_task(ws_manager.broadcast_progress(p)),
                    )

                    # Persistence: remove from queue.json when finished
                    # Only remove if it was truly finished, permanently failed, or explicitly cancelled
                    if result.status.value in ("complete", "skipped", "error", "cancelled"):
                        queue_manager.remove_item(album_id, item.filename)

                    # Broadcast file complete
                    await ws_manager.broadcast_file_complete(
                        item.filename,
                        error=result.error if result.status.value == "error" else None
                    )
                except Exception as e:
                    logger.error(f"Error downloading {item.filename}: {e}")

            # Create tasks for all items
            tasks = [download_item(item) for item in request.items]
            
            # Run all in parallel (manager controls the limit)
            await asyncio.gather(*tasks)

        except Exception as e:
            logger.exception(f"FATAL: Download error in background task: {e}")
        finally:
            # Clean up active task reference
            if album_id in _active_downloads:
                del _active_downloads[album_id]

    # Start download in background
    logger.info(f"Starting background download task for album: {album_id} ({len(request.items)} items)")
    task = asyncio.create_task(run_download())
    _active_downloads[album_id] = task

    return DownloadResponse(success=True, queued_count=len(request.items))


@router.post("/api/cancel")
async def cancel_download(album_name: str) -> dict[str, Any]:
    """
    Cancel an active download.

    Args:
        album_name: Name of the album download to cancel

    Returns:
        Success status
    """
    if album_name in _active_downloads:
        task = _active_downloads[album_name]
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        del _active_downloads[album_name]
        return {"success": True, "message": f"Cancelled {album_name}"}

    return {"success": False, "message": "Download not found"}


@router.get("/api/settings", response_model=SettingsModel)
async def get_settings() -> SettingsModel:
    """Get current application settings."""
    return config.settings


@router.post("/api/settings", response_model=SettingsModel)
async def update_settings(settings: SettingsModel) -> SettingsModel:
    """
    Update application settings.

    Args:
        settings: New settings values

    Returns:
        Updated settings
    """
    config.save(settings)
    return settings


@router.get("/api/status")
async def get_status() -> dict[str, Any]:
    """Get current download status."""
    return {
        "active_downloads": len(_active_downloads),
        "downloads": list(_active_downloads.keys()),
        "websocket_connections": ws_manager.connection_count,
    }


@router.post("/api/delete-album")
async def delete_album(request: DeleteAlbumRequest) -> Any:
    """Delete an album folder from the downloads directory."""
    try:
        album_name = request.album_name
        download_dir = Path(config.settings.download_folder)
        album_dir = download_dir / album_name
        
        # Security check: ensure the path is within the downloads folder
        # We resolve both to compare absolute paths
        abs_download_dir = download_dir.resolve()
        abs_album_dir = album_dir.resolve()
        
        if not str(abs_album_dir).startswith(str(abs_download_dir)):
            return {"success": False, "error": "Invalid album path - security violation"}

        if abs_album_dir.exists() and abs_album_dir.is_dir():
            # Perform synchronous rmtree in a thread to avoid blocking loop
            await asyncio.to_thread(shutil.rmtree, abs_album_dir)
            logger.info(f"Deleted album folder: {album_name}")
            return {"success": True}
        
        return {"success": True, "message": "Folder did not exist"}
    except Exception as e:
        logger.error(f"Failed to delete album {request.album_name}: {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/open-folder")
async def open_folder():
    """Open the downloads folder in the file manager."""
    try:
        import os
        import platform
        import subprocess
        
        folder_path = Path(config.settings.download_folder).absolute()
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
            
        if platform.system() == "Windows":
            os.startfile(folder_path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", str(folder_path)])
        else:  # Linux
            subprocess.run(["xdg-open", str(folder_path)])
            
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to open folder: {e}")
        return {"success": False, "error": str(e)}


@router.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket):
    """WebSocket endpoint for real-time progress updates."""
    from .websocket import websocket_handler
    await websocket_handler(websocket)