"""
Filename and string sanitization utilities.

Provides safe filename generation for cross-platform compatibility.
"""

import re
from pathlib import Path


# Characters not allowed in Windows filenames
FORBIDDEN_CHARS = r'[<>:"/\\|?*\x00-\x1f]'

# Maximum filename length (conservative for most filesystems)
MAX_FILENAME_LENGTH = 200


def sanitize_string(s: str | None) -> str:
    """
    Sanitize a string to be safe for filenames/folders.

    - Replaces spaces with underscores
    - Removes non-alphanumeric characters (except underscores)
    - Collapses multiple underscores
    - Converts to lowercase

    Args:
        s: Input string to sanitize

    Returns:
        Sanitized string safe for filesystem use
    """
    if not s:
        return "unknown"

    # Replace spaces and common separators with underscores
    s = s.replace(" ", "_").replace("-", "_").replace(".", "_")

    # Remove everything except alphanumeric and underscores
    s = re.sub(r"[^a-zA-Z0-9_]", "", s)

    # Collapse multiple underscores
    s = re.sub(r"_+", "_", s)

    # Strip leading/trailing underscores and convert to lowercase
    result = s.strip("_").lower()

    return result if result else "unknown"


def sanitize_filename(filename: str, max_length: int = MAX_FILENAME_LENGTH) -> str:
    """
    Sanitize a complete filename while preserving extension.

    Args:
        filename: Original filename (may include extension)
        max_length: Maximum allowed length

    Returns:
        Sanitized filename with original extension preserved
    """
    if not filename:
        return "unknown_file"

    # Split into stem and extension
    path = Path(filename)
    stem = path.stem
    ext = path.suffix.lower()

    # Fix jpeg -> jpg
    if ext == ".jpeg":
        ext = ".jpg"

    # Sanitize the stem
    clean_stem = sanitize_string(stem)
    if not clean_stem:
        clean_stem = "file"

    # Truncate if necessary
    if len(clean_stem) + len(ext) > max_length:
        available = max_length - len(ext)
        clean_stem = clean_stem[:available]

    return f"{clean_stem}{ext}"


def get_clean_filename(url: str) -> str:
    """
    Extract and sanitize filename from a URL.

    Args:
        url: Full URL to extract filename from

    Returns:
        Sanitized filename
    """
    from urllib.parse import urlparse

    path = urlparse(url).path
    basename = Path(path).name

    return sanitize_filename(basename)


def safe_folder_name(name: str) -> str:
    """
    Create a safe folder name from any string.

    Args:
        name: Original folder name

    Returns:
        Sanitized folder name
    """
    return sanitize_string(name)