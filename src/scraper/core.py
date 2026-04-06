"""
Async Erome album scraper.

Provides async HTTP scraping with BeautifulSoup parsing.
Preserves the original scraping logic with improved error handling.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ..utils.exceptions import NetworkError, ScrapeError, ValidationError
from ..utils.sanitize import get_clean_filename, sanitize_string
from .models import MediaItem, MediaType, ScrapedAlbum

logger = logging.getLogger(__name__)

# Default request headers
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class EromeScraper:
    """Async scraper for Erome albums."""

    def __init__(
        self,
        timeout: float = 30.0,
        headers: dict | None = None,
        follow_redirects: bool = True,
    ):
        """
        Initialize the scraper.

        Args:
            timeout: HTTP request timeout in seconds
            headers: Custom headers (merged with defaults)
            follow_redirects: Whether to follow HTTP redirects
        """
        self.timeout = timeout
        self.headers = {**DEFAULT_HEADERS, **(headers or {})}
        self.follow_redirects = follow_redirects
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "EromeScraper":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=self.follow_redirects,
        )
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, creating one if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=self.timeout,
                follow_redirects=self.follow_redirects,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _validate_url(self, url: str) -> None:
        """Validate that the URL is a valid Erome album URL."""
        if not url:
            raise ValidationError("URL is required", field="url")

        parsed = urlparse(url)
        if not parsed.scheme:
            raise ValidationError("URL must include scheme (https://)", field="url", value=url)

        if "erome.com" not in parsed.netloc.lower():
            raise ValidationError(
                "URL must be from erome.com domain",
                field="url",
                value=url
            )

    def _normalize_url(self, url: str) -> str:
        """Normalize URL to handle protocol-relative and relative URLs."""
        if url.startswith("//"):
            return f"https:{url}"
        return url

    async def scrape(self, url: str) -> ScrapedAlbum:
        """
        Scrape an Erome album URL for media items.

        Args:
            url: Erome album URL

        Returns:
            ScrapedAlbum with title and media items

        Raises:
            ValidationError: If URL is invalid
            NetworkError: If HTTP request fails
            ScrapeError: If parsing fails
        """
        self._validate_url(url)
        logger.info(f"Scraping album: {url}")

        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise NetworkError(
                f"HTTP error scraping album",
                status_code=e.response.status_code,
                details=str(e)
            )
        except httpx.RequestError as e:
            raise NetworkError(f"Network error scraping album", details=str(e))

        try:
            soup = BeautifulSoup(response.content, "lxml")
            album = self._parse_album(soup, url)
            logger.info(f"Found {len(album.media)} items in album '{album.title}'")
            return album
        except Exception as e:
            if isinstance(e, (ScrapeError, NetworkError, ValidationError)):
                raise
            raise ScrapeError(f"Failed to parse album page", url=url, details=str(e))

    def _parse_album(self, soup: BeautifulSoup, original_url: str) -> ScrapedAlbum:
        """Parse the HTML soup into a ScrapedAlbum."""
        # Extract title
        title_elem = soup.find("h1")
        title = sanitize_string(title_elem.get_text(strip=True)) if title_elem else "unknown_album"

        # Extract media items
        media_items: list[MediaItem] = []

        # Find videos
        for video in soup.find_all("video"):
            item = self._parse_video(video)
            if item:
                media_items.append(item)

        # Image scraping disabled as per user request (Video-Only Mode)
        # for img in soup.select(".media-group .img-back") or soup.select(".media-group img"):
        #     item = self._parse_image(img)
        #     if item:
        #         media_items.append(item)

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique_items: list[MediaItem] = []
        for item in media_items:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_items.append(item)

        return ScrapedAlbum(
            title=title,
            media=unique_items,
            original_url=original_url,
        )

    def _parse_video(self, video_elem) -> MediaItem | None:
        """Parse a video element into a MediaItem."""
        source = video_elem.find("source")
        if not source or not source.get("src"):
            return None

        src = self._normalize_url(source.get("src").strip())
        src = urljoin("https://www.erome.com/", src)

        poster = video_elem.get("poster")
        thumbnail = self._normalize_url(poster.strip()) if poster else None

        return MediaItem(
            type=MediaType.VIDEO,
            url=src,
            filename=get_clean_filename(src),
            thumbnail=thumbnail,
        )

    def _parse_image(self, img_elem) -> MediaItem | None:
        """Parse an image element into a MediaItem."""
        src = img_elem.get("data-src") or img_elem.get("src")
        if not src:
            return None

        src = self._normalize_url(src.strip())
        src = urljoin("https://www.erome.com/", src)

        return MediaItem(
            type=MediaType.IMAGE,
            url=src,
            filename=get_clean_filename(src),
            thumbnail=src,  # Images use themselves as thumbnail
        )


# Convenience function for simple usage
async def scrape_album(url: str) -> ScrapedAlbum:
    """
    Scrape an Erome album URL (convenience function).

    Args:
        url: Erome album URL

    Returns:
        ScrapedAlbum with title and media items
    """
    async with EromeScraper() as scraper:
        return await scraper.scrape(url)