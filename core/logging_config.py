"""
Centralized logging configuration for the grammar enforcement pipeline.

Usage:
    from core.logging_config import setup_logging
    setup_logging()           # INFO level, colored console
    setup_logging("DEBUG")    # DEBUG level
    setup_logging("INFO", log_file="pipeline.log")  # Also log to file
"""

import logging
import sys
from pathlib import Path
from typing import Optional

try:
    from colorama import init as colorama_init, Fore, Style

    colorama_init()
    _HAS_COLOR = True
except ImportError:
    _HAS_COLOR = False


# ── Color formatter ──────────────────────────────────────────────────────

class ColoredFormatter(logging.Formatter):
    """Formatter that adds ANSI color codes (Windows-safe via colorama)."""

    LEVEL_COLORS = {
        logging.DEBUG: Fore.CYAN if _HAS_COLOR else "",
        logging.INFO: Fore.GREEN if _HAS_COLOR else "",
        logging.WARNING: Fore.YELLOW if _HAS_COLOR else "",
        logging.ERROR: Fore.RED if _HAS_COLOR else "",
        logging.CRITICAL: Fore.RED + Style.BRIGHT if _HAS_COLOR else "",
    }
    RESET = Style.RESET_ALL if _HAS_COLOR else ""

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, "")
        record.levelname = f"{color}{record.levelname:<8}{self.RESET}"
        return super().format(record)


# ── Setup ────────────────────────────────────────────────────────────────

_CONFIGURED = False


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    fmt: str = "%(asctime)s │ %(levelname)s │ %(name)-30s │ %(message)s",
    datefmt: str = "%H:%M:%S",
) -> None:
    """Configure logging for the entire pipeline.

    Call once at program startup (e.g. in ``run_pipeline.py``).
    Subsequent calls are no-ops unless the root logger has no handlers.

    Args:
        level: Logging level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional path to a log file. If provided, logs are also
                  written to this file at DEBUG level regardless of *level*.
        fmt: Log message format string.
        datefmt: Date/time format.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # capture everything; handlers decide level

    # Console handler (colored)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, level.upper(), logging.INFO))
    console.setFormatter(ColoredFormatter(fmt, datefmt=datefmt))
    root.addHandler(console)

    # File handler (optional)
    if log_file:
        fpath = Path(log_file)
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(fpath), encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        root.addHandler(fh)

    # Suppress noisy third-party loggers
    logging.getLogger("lark").setLevel(logging.WARNING)
    logging.getLogger("sklearn").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Convenience: return a named logger for a module.

    Usage inside any module:

        from core.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("loaded %d traces", n)
    """
    return logging.getLogger(name)
