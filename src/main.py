"""
Erome Scraper - FastAPI Web Application

Main entry point for the FastAPI backend.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api.routes import router as api_router
from .utils.config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Erome Scraper...")

    # Ensure download folder exists
    download_folder = Path(config.settings.download_folder)
    download_folder.mkdir(parents=True, exist_ok=True)
    logger.info(f"Download folder: {download_folder.absolute()}")

    # 1. Cleanup partial files to ensure integrity on restart
    logger.info("Cleaning up partial files (.part)...")
    partial_files = list(download_folder.rglob("*.part"))
    for pf in partial_files:
        try:
            pf.unlink()
            logger.info(f"Deleted partial file: {pf.name}")
        except Exception as e:
            logger.error(f"Failed to delete {pf.name}: {e}")

    # 2. Initialize global DownloadManager
    from .api.routes import get_download_manager, start_download
    manager = get_download_manager()
    await manager.__aenter__()
    logger.info("DownloadManager initialized.")

    # 3. Recover persistent queue
    from .utils.queue import queue_manager
    from .scraper.models import DownloadRequest
    
    pending = queue_manager.get_all()
    if pending:
        logger.info(f"Recovering {len(pending)} pending albums from queue...")
        for album_name, items in pending.items():
            # Trigger download task for each album
            # (Mocking a DownloadRequest to call start_download internally)
            req = DownloadRequest(items=items, album_name=album_name)
            await start_download(req)
            logger.info(f"Resumed download for: {album_name}")

    yield

    # Shutdown
    logger.info("Shutting down Erome Scraper...")
    await manager.close()
    logger.info("DownloadManager closed.")


# Create FastAPI app
app = FastAPI(
    title="Erome Scraper",
    description="Modern async scraper and downloader for Erome albums",
    version="3.0.0",
    lifespan=lifespan,
)

# Include API routes
app.include_router(api_router)

# Mount static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    logger.info(f"Static files mounted from: {static_path}")


# Serve index.html at root
@app.get("/", response_class=None)
async def serve_index():
    """Serve the main HTML page."""
    from fastapi.responses import FileResponse
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Erome Scraper API - Static files not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )