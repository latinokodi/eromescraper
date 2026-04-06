"""Tests for the Erome scraper module."""

import pytest

from src.scraper.models import MediaItem, MediaType, ScrapedAlbum
from src.utils.sanitize import sanitize_string, sanitize_filename, get_clean_filename


class TestSanitization:
    """Tests for filename sanitization utilities."""

    def test_sanitize_string_basic(self):
        assert sanitize_string("Hello World") == "hello_world"

    def test_sanitize_string_special_chars(self):
        assert sanitize_string("File@Name#123!") == "filename123"

    def test_sanitize_string_empty(self):
        assert sanitize_string("") == "unknown"
        assert sanitize_string(None) == "unknown"

    def test_sanitize_string_multiple_underscores(self):
        assert sanitize_string("hello___world") == "hello_world"

    def test_sanitize_filename(self):
        assert sanitize_filename("My Video.mp4") == "my_video.mp4"

    def test_sanitize_filename_jpeg(self):
        assert sanitize_filename("image.jpeg") == "image.jpg"

    def test_sanitize_filename_empty(self):
        assert sanitize_filename("") == "unknown_file"


class TestModels:
    """Tests for Pydantic models."""

    def test_media_item_creation(self):
        item = MediaItem(
            type=MediaType.VIDEO,
            url="https://example.com/video.mp4",
            filename="video.mp4",
            thumbnail="https://example.com/thumb.jpg"
        )
        assert item.type == MediaType.VIDEO
        assert item.filename == "video.mp4"

    def test_scraped_album(self):
        items = [
            MediaItem(type=MediaType.VIDEO, url="https://example.com/v.mp4", filename="v.mp4"),
            MediaItem(type=MediaType.IMAGE, url="https://example.com/i.jpg", filename="i.jpg"),
        ]
        album = ScrapedAlbum(
            title="test_album",
            media=items,
            original_url="https://erome.com/a/abc123"
        )
        assert album.title == "test_album"
        assert album.video_count == 1
        assert album.image_count == 1
        assert len(album.media) == 2


class TestScraperIntegration:
    """Integration tests for the scraper (require network)."""

    @pytest.mark.asyncio
    async def test_scraper_context_manager(self):
        """Test that scraper can be used as async context manager."""
        from src.scraper.core import EromeScraper

        async with EromeScraper() as scraper:
            assert scraper.client is not None

    @pytest.mark.asyncio
    async def test_scraper_url_validation(self):
        """Test URL validation."""
        from src.scraper.core import EromeScraper
        from src.utils.exceptions import ValidationError

        async with EromeScraper() as scraper:
            with pytest.raises(ValidationError):
                await scraper.scrape("not-a-url")

            with pytest.raises(ValidationError):
                await scraper.scrape("https://youtube.com/watch?v=123")