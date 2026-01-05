"""Logging configuration for the orchestrator.

Configures root logger with console and file handlers so all modules
can use standard logging.getLogger(__name__) and benefit from file logging.
"""

import logging
from pathlib import Path

_SETUP_DONE = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with console and file handlers.
    
    This should be called once at application startup. All modules can then
    use standard logging.getLogger(__name__) and will automatically get
    both console and file logging.
    
    Args:
        level: Logging level (default: INFO)
    """
    global _SETUP_DONE
    if _SETUP_DONE:
        return
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove any existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler - simpler format for readability
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(
        "[%(asctime)s][%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler - more detailed format with full timestamps
    try:
        base = Path(__file__).resolve().parents[1]
        log_dir = base / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(
            log_dir / "orchestrator.log",
            encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    except Exception:
        # If file logging fails, continue with console only
        pass
    
    _SETUP_DONE = True

