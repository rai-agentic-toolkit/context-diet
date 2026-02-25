"""
ContentSniffer implementation for automated strategy detection.
"""

import re

EXTENSION_MAP = {
    ".py": "python",
    ".json": "json",
    ".sql": "sql",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".txt": "text",
    ".md": "text",
    ".log": "log",
    ".csv": "text",
}


def detect_strategy(
    content: str, filename: str | None = None, extension: str | None = None
) -> str:
    """
    Detects the optimal parsing strategy explicitly by extension, falling back to structural signature.

    If no specialized structure is identified, defaults to plain text.
    """
    import os

    # 1. Deterministic Extension Matching
    if not extension and filename:
        _, ext = os.path.splitext(filename)
        extension = ext.lower()

    if extension:
        if not extension.startswith("."):
            extension = "." + extension
        mapped_strategy = EXTENSION_MAP.get(extension)
        if mapped_strategy:
            return mapped_strategy

    # 2. Heuristic Structural Sniffing
    content_stripped = content.lstrip()
    if not content_stripped:
        return "text"

    # JSON Heuristic
    if content_stripped.startswith("{") or content_stripped.startswith("["):
        return "json"

    # Python AST Heuristic
    if re.search(r"^(import |from .* import |def |class )", content, flags=re.MULTILINE):
        return "python"

    # SQL Heuristic
    if re.search(
        r"^(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE|ALTER TABLE)\b",
        content_stripped,
        flags=re.IGNORECASE,
    ):
        return "sql"

    # Log Heuristic (Looking for timestamps or log levels at start of lines)
    if re.search(
        r"^\s*(?:\d{2,4}[-/]\d{2}[-/]\d{2}|\[?\d{4}-\d{2}-\d{2}|INFO|ERROR|WARN|DEBUG|CRITICAL|Traceback)\b",
        content_stripped,
        flags=re.IGNORECASE | re.MULTILINE,
    ):
        return "log"

    # YAML Heuristic
    if re.search(r"^[\w-]+:\s*([#\n]|.*)", content_stripped, flags=re.MULTILINE):
        # YAML isn't as easily uniquely distinguishable from normal config data, but this matches keys well.
        return "yaml"

    return "text"
