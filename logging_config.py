"""
Enhanced logging configuration for KotobaTranscriber
Provides detailed logging with rotation and error tracking
"""

import logging
import logging.handlers
import sys
import os
from pathlib import Path


def setup_logging(log_name="app", log_dir="logs", level=logging.DEBUG):
    """
    Set up comprehensive logging with file and console handlers

    Args:
        log_name: Name of the log file (without .log extension)
        log_dir: Directory for log files
        level: Logging level (default: DEBUG for maximum detail)

    Returns:
        Logger instance
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove any existing handlers
    logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # File handler with rotation (10MB per file, keep 5 backups)
    log_file = log_path / f"{log_name}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)

    # Error file handler (only errors and critical)
    error_log_file = log_path / f"{log_name}_errors.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    logger.addHandler(error_handler)

    # Console handler (INFO and above to avoid spam)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)

    # Log startup info
    logger.info("=" * 80)
    logger.info(f"Logging initialized: {log_name}")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Error log: {error_log_file}")
    logger.info(f"Log level: {logging.getLevelName(level)}")
    logger.info("=" * 80)

    return logger


def log_exception(logger, exc_type, exc_value, exc_traceback):
    """
    Exception handler to log uncaught exceptions

    Args:
        logger: Logger instance
        exc_type: Exception type
        exc_value: Exception value
        exc_traceback: Exception traceback
    """
    if issubclass(exc_type, KeyboardInterrupt):
        # Don't log keyboard interrupts
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )


def setup_exception_logging(logger):
    """
    Set up global exception handler to catch all uncaught exceptions

    Args:
        logger: Logger instance
    """
    sys.excepthook = lambda exc_type, exc_value, exc_traceback: \
        log_exception(logger, exc_type, exc_value, exc_traceback)
