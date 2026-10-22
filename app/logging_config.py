"""Logging configuration for PR Chronicler.

Configures dual output to terminal (stdout) and pr_chronicler.log,
with sensitive credential sanitization and structured contextual formatting.
"""

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional


class SanitizedFormatter(logging.Formatter):
    """Formatter that masks sensitive tokens, passwords, and authorization headers in formatted output."""

    PATTERNS = [
        (re.compile(r"(Bearer\s+)[A-Za-z0-9_.\-]+", re.IGNORECASE), r"\1***REDACTED***"),
        (re.compile(r"(token\s*[:=]\s*)[A-Za-z0-9_.\-]+", re.IGNORECASE), r"\1***REDACTED***"),
        (re.compile(r"(key\s*[:=]\s*)[A-Za-z0-9_.\-]+", re.IGNORECASE), r"\1***REDACTED***"),
        (re.compile(r"(password\s*[:=]\s*)[^\s,;&]+", re.IGNORECASE), r"\1***REDACTED***"),
        (re.compile(r"(secret\s*[:=]\s*)[^\s,;&]+", re.IGNORECASE), r"\1***REDACTED***"),
        (re.compile(r"(ghp_[A-Za-z0-9]{30,})", re.IGNORECASE), r"ghp_***REDACTED***"),
        (re.compile(r"(AIza[0-9A-Za-z-_]{35})", re.IGNORECASE), r"AIza***REDACTED***"),
    ]

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        for pattern, repl in self.PATTERNS:
            formatted = pattern.sub(repl, formatted)
        return formatted


def setup_logging(
    log_file: str = "pr_chronicler.log",
    log_level: str = "INFO",
    max_bytes: int = 10_485_760,  # 10 MB
    backup_count: int = 5,
) -> logging.Logger:
    """Configures the root and application logger with stream and rotating file handlers."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = SanitizedFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers on reload
    if not root_logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File handler
        try:
            file_handler = RotatingFileHandler(
                filename=log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.warning("Failed to initialize file logger at %s: %s", log_file, e)

    # Set external libraries to warning to keep logs clean
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)

    app_logger = logging.getLogger("pr_chronicler")
    app_logger.setLevel(numeric_level)
    return app_logger


# Default module logger
logger = setup_logging()
