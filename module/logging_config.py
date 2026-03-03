import logging
import logging.handlers
import sys
from enum import Enum


class LogLevel(str, Enum):
    """
    Possible log levels the module can be configured with.
    """

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


log_level_mapping = {
    LogLevel.DEBUG: logging.DEBUG,
    LogLevel.INFO: logging.INFO,
    LogLevel.WARNING: logging.WARNING,
    LogLevel.ERROR: logging.ERROR,
    LogLevel.CRITICAL: logging.CRITICAL,
}

# Logging formatter
FORMATTER = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")


def configure_initial_logging(
    name: str = "",
) -> None:
    """
    Configures the console handler and its formatting.

    :param name: The name of the root logger to configure.
    """
    logger = logging.getLogger(name)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(FORMATTER)
    logger.addHandler(console_handler)


def configure_logging(
    log_level: LogLevel,
    log_file_path: str,
    name: str = "",
) -> None:
    """
    Performs remaining configuration for logging by adding a file handler and setting the log level.

    :param log_level: Logging level of the module.
    :param log_file_path: Path to the log file to write to.
    :param name: The name of the root logger to configure.
    """
    logger = logging.getLogger(name)
    mapped_log_level: int = log_level_mapping[log_level]
    logger.setLevel(mapped_log_level)

    # Create and configure the file handler.
    # the handler rotates the log file every 10 MB and keeps 5 backups.
    # eg, execution_logs.txt, execution_logs.txt.1, …, execution_logs.txt.5
    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path,
        maxBytes=10_000_000,
        backupCount=5,
    )
    file_handler.setLevel(mapped_log_level)
    file_handler.setFormatter(FORMATTER)
    logger.addHandler(file_handler)
