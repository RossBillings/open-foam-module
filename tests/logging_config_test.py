"""Tests for module/logging_config.py"""

import logging
from pathlib import Path

from module.logging_config import (
    LogLevel,
    configure_initial_logging,
    configure_logging,
    log_level_mapping,
)


def test_log_level_enum_values():
    """Test that LogLevel enum has correct values."""
    assert LogLevel.CRITICAL == "critical"
    assert LogLevel.ERROR == "error"
    assert LogLevel.WARNING == "warning"
    assert LogLevel.INFO == "info"
    assert LogLevel.DEBUG == "debug"


def test_log_level_mapping():
    """Test that log_level_mapping maps correctly."""
    assert log_level_mapping[LogLevel.DEBUG] == logging.DEBUG
    assert log_level_mapping[LogLevel.INFO] == logging.INFO
    assert log_level_mapping[LogLevel.WARNING] == logging.WARNING
    assert log_level_mapping[LogLevel.ERROR] == logging.ERROR
    assert log_level_mapping[LogLevel.CRITICAL] == logging.CRITICAL


def test_configure_initial_logging():
    """Test configure_initial_logging sets up console handler."""
    logger_name = "test_logger"
    logger = logging.getLogger(logger_name)

    # Clear any existing handlers
    logger.handlers.clear()

    configure_initial_logging(logger_name)

    # Check that handler was added
    assert len(logger.handlers) > 0
    # Check that handler is a StreamHandler
    assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)


def test_configure_initial_logging_default_name():
    """Test configure_initial_logging with default name."""
    root_logger = logging.getLogger()

    # Clear any existing handlers
    root_logger.handlers.clear()

    configure_initial_logging()

    # Check that handler was added
    assert len(root_logger.handlers) > 0


def test_configure_logging_with_info_level(tmp_path: Path):
    """Test configure_logging with INFO level."""
    logger_name = "test_logger"
    logger = logging.getLogger(logger_name)

    # Clear any existing handlers
    logger.handlers.clear()

    log_file_path = tmp_path / "test.log"

    configure_logging(LogLevel.INFO, str(log_file_path), logger_name)

    # Check that logger level was set
    assert logger.level == logging.INFO

    # Check that file handler was added
    file_handlers = [
        h
        for h in logger.handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    assert len(file_handlers) > 0

    # Check that log file can be written to
    logger.info("Test message")
    assert log_file_path.exists()


def test_configure_logging_with_debug_level(tmp_path: Path):
    """Test configure_logging with DEBUG level."""
    logger_name = "test_logger_debug"
    logger = logging.getLogger(logger_name)

    # Clear any existing handlers
    logger.handlers.clear()

    log_file_path = tmp_path / "debug.log"

    configure_logging(LogLevel.DEBUG, str(log_file_path), logger_name)

    assert logger.level == logging.DEBUG


def test_configure_logging_with_warning_level(tmp_path: Path):
    """Test configure_logging with WARNING level."""
    logger_name = "test_logger_warning"
    logger = logging.getLogger(logger_name)

    # Clear any existing handlers
    logger.handlers.clear()

    log_file_path = tmp_path / "warning.log"

    configure_logging(LogLevel.WARNING, str(log_file_path), logger_name)

    assert logger.level == logging.WARNING


def test_configure_logging_with_error_level(tmp_path: Path):
    """Test configure_logging with ERROR level."""
    logger_name = "test_logger_error"
    logger = logging.getLogger(logger_name)

    # Clear any existing handlers
    logger.handlers.clear()

    log_file_path = tmp_path / "error.log"

    configure_logging(LogLevel.ERROR, str(log_file_path), logger_name)

    assert logger.level == logging.ERROR


def test_configure_logging_with_critical_level(tmp_path: Path):
    """Test configure_logging with CRITICAL level."""
    logger_name = "test_logger_critical"
    logger = logging.getLogger(logger_name)

    # Clear any existing handlers
    logger.handlers.clear()

    log_file_path = tmp_path / "critical.log"

    configure_logging(LogLevel.CRITICAL, str(log_file_path), logger_name)

    assert logger.level == logging.CRITICAL


def test_configure_logging_default_name(tmp_path: Path):
    """Test configure_logging with default name."""
    root_logger = logging.getLogger()

    # Clear any existing handlers
    root_logger.handlers.clear()

    log_file_path = tmp_path / "root.log"

    configure_logging(LogLevel.INFO, str(log_file_path))

    assert root_logger.level == logging.INFO


def test_configure_logging_rotating_file_handler(tmp_path: Path):
    """Test that configure_logging creates RotatingFileHandler with correct settings."""
    logger_name = "test_rotating"
    logger = logging.getLogger(logger_name)

    # Clear any existing handlers
    logger.handlers.clear()

    log_file_path = tmp_path / "rotating.log"

    configure_logging(LogLevel.INFO, str(log_file_path), logger_name)

    # Find RotatingFileHandler
    file_handlers = [
        h
        for h in logger.handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    assert len(file_handlers) == 1

    handler = file_handlers[0]
    assert handler.maxBytes == 10_000_000
    assert handler.backupCount == 5
    assert handler.level == logging.INFO
