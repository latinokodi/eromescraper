"""
Custom exception hierarchy for Erome Scraper.

Provides structured error handling with specific exception types
for different failure modes.
"""


class EromeError(Exception):
    """Base exception for all Erome scraper errors."""

    def __init__(self, message: str, details: str | None = None):
        self.message = message
        self.details = details
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class ScrapeError(EromeError):
    """Failed to scrape album URL."""

    def __init__(self, message: str, url: str | None = None, details: str | None = None):
        self.url = url
        super().__init__(message, details)

    def __str__(self) -> str:
        base = super().__str__()
        if self.url:
            return f"{base} (URL: {self.url})"
        return base


class DownloadError(EromeError):
    """Failed to download media file."""

    def __init__(
        self,
        message: str,
        filename: str | None = None,
        url: str | None = None,
        details: str | None = None
    ):
        self.filename = filename
        self.url = url
        super().__init__(message, details)

    def __str__(self) -> str:
        base = super().__str__()
        parts = []
        if self.filename:
            parts.append(f"file={self.filename}")
        if self.url:
            parts.append(f"url={self.url}")
        if parts:
            return f"{base} ({', '.join(parts)})"
        return base


class NetworkError(EromeError):
    """Network or connectivity issues."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        details: str | None = None
    ):
        self.status_code = status_code
        super().__init__(message, details)

    def __str__(self) -> str:
        base = super().__str__()
        if self.status_code:
            return f"{base} (HTTP {self.status_code})"
        return base


class FileError(EromeError):
    """File system errors (permissions, disk full, etc)."""

    def __init__(
        self,
        message: str,
        path: str | None = None,
        details: str | None = None
    ):
        self.path = path
        super().__init__(message, details)

    def __str__(self) -> str:
        base = super().__str__()
        if self.path:
            return f"{base} (path: {self.path})"
        return base


class ValidationError(EromeError):
    """Input validation errors."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: str | None = None,
        details: str | None = None
    ):
        self.field = field
        self.value = value
        super().__init__(message, details)

    def __str__(self) -> str:
        base = super().__str__()
        if self.field:
            return f"{base} (field: {self.field})"
        return base