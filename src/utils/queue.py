"""
Persistent download queue manager.

Handles saving and loading pending downloads to/from a JSON file.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..scraper.models import DownloadRequest, MediaItem

logger = logging.getLogger(__name__)


class QueueManager:
    """Manages a persistent download queue on disk."""

    def __init__(self, queue_path: Path | None = None):
        """
        Initialize the queue manager.

        Args:
            queue_path: Path to the queue JSON file. Defaults to queue.json.
        """
        self.queue_path = queue_path or Path("queue.json")
        self._queue: dict[str, list[MediaItem]] = {}
        self.load()

    def load(self) -> dict[str, list[MediaItem]]:
        """Load the queue from disk."""
        if not self.queue_path.exists():
            self._queue = {}
            return self._queue

        try:
            with open(self.queue_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Convert back to MediaItem models
                self._queue = {
                    album: [MediaItem(**item) for item in items]
                    for album, items in data.items()
                }
            logger.info(f"Loaded persistent queue: {len(self._queue)} albums found.")
        except Exception as e:
            logger.error(f"Failed to load queue.json: {e}")
            self._queue = {}
        return self._queue

    def save(self) -> None:
        """Save the current queue to disk."""
        try:
            # Serialize MediaItem models to dicts
            data = {
                album: [item.model_dump() for item in items]
                for album, items in self._queue.items()
            }
            with open(self.queue_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save queue.json: {e}")

    def add_album(self, album_name: str, items: list[MediaItem]) -> None:
        """Add an entire album to the persistent queue."""
        if album_name not in self._queue:
            self._queue[album_name] = []
        
        # Deduplicate items by URL within the album queue
        existing_urls = {item.url for item in self._queue[album_name]}
        for item in items:
            if item.url not in existing_urls:
                self._queue[album_name].append(item)
        
        self.save()

    def remove_item(self, album_name: str, filename: str) -> None:
        """Remove a single item from an album queue."""
        if album_name in self._queue:
            initial_len = len(self._queue[album_name])
            self._queue[album_name] = [
                item for item in self._queue[album_name] 
                if item.filename != filename
            ]
            
            # If album is empty, remove it
            if not self._queue[album_name]:
                del self._queue[album_name]
                logger.info(f"Album '{album_name}' completed and removed from queue.")
            
            # Only save if something changed
            if initial_len != (len(self._queue.get(album_name, [])) if album_name in self._queue else 0):
                self.save()

    def get_all(self) -> dict[str, list[MediaItem]]:
        """Get all pending albums and items."""
        return self._queue

    def clear(self) -> None:
        """Clear the entire persistent queue."""
        self._queue = {}
        if self.queue_path.exists():
            self.queue_path.unlink()
        logger.info("Persistent queue cleared.")


# Global instance
queue_manager = QueueManager()
