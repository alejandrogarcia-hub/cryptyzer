"""Logger configuration module for application-wide logging.

This module provides a centralized logging configuration with JSON formatting,
file rotation, and optional console output for development environments. It
ensures consistent logging across the application with proper file management
and formatting.

Classes:
    LogManager: Manages application-wide logging configuration and setup.
"""

import logging
import logging.handlers
import os

from pythonjsonlogger import jsonlogger


class LogManager:
    """Manages application logging configuration and setup.

    This class handles the configuration of logging with JSON formatting,
    file rotation, and optional console output for development environments.
    It provides a unified logging interface across the application.

    Attributes:
        logger (logging.Logger): Configured logger instance.
        log_dir (str): Directory path for log files.
        formatter (jsonlogger.JsonFormatter): JSON formatter for log messages.

    Note:
        Log files are automatically rotated based on size with backup retention.
    """

    logger: logging.Logger
    log_dir: str
    formatter: jsonlogger.JsonFormatter

    def __init__(
        self,
        app_name: str,
        log_dir: str,
        level: int = logging.INFO,
        max_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        development: bool = False,
    ) -> None:
        """Initialize the log manager with specified configuration.

        Sets up logging with proper directory structure, file rotation,
        and formatting configuration.

        Args:
            app_name: Name of the application for logger identification.
            log_dir: Directory path where log files will be stored.
            level: Logging level (default: logging.INFO).
            max_size: Maximum size of log file before rotation in bytes (default: 10MB).
            backup_count: Number of backup files to keep (default: 5).
            development: Enable console logging for development (default: False).

        Raises:
            AssertionError: If log_dir is not provided.
            OSError: If unable to create log directory with proper permissions.

        Examples:
            >>> logger = LogManager(
            ...     app_name="MyApp",
            ...     log_dir="/var/log/myapp",
            ...     level=logging.DEBUG,
            ...     development=True
            ... )
        """
        assert log_dir, "log_dir is required"

        # Expand user path if necessary
        self.log_dir = os.path.expanduser(log_dir)

        # Create directory with proper permissions (read/write for user)
        try:
            os.makedirs(self.log_dir, mode=0o755, exist_ok=True)
        except OSError as e:
            raise OSError(f"Failed to create log directory: {e}")

        self.logger: logging.Logger = logging.getLogger(app_name)
        self.logger.setLevel(level)
        self.formatter: jsonlogger.JsonFormatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(filename)s %(name)s %(funcName)s %(lineno)s %(message)s"
        )

        # Set up handlers
        self._setup_file_handler(app_name, max_size, backup_count)
        if development:
            self._setup_console_handler()

    def _setup_file_handler(
        self, app_name: str, max_size: int, backup_count: int
    ) -> None:
        """Configure rotating file handler for log files.

        Sets up a rotating file handler that automatically rotates log files
        when they reach the specified size limit.

        Args:
            app_name: Application name used in log file naming.
            max_size: Maximum size of each log file in bytes.
            backup_count: Number of backup files to maintain.

        Raises:
            OSError: If unable to create or write to log file.

        Note:
            Log files are named {app_name}.log with numbered backups.
        """
        log_file = os.path.join(self.log_dir, f"{app_name}.log")
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_size, backupCount=backup_count
        )
        handler.setFormatter(self.formatter)
        self.logger.addHandler(handler)

    def _setup_console_handler(self) -> None:
        """Configure console handler for development logging.

        Adds a console handler to output logs to stdout when in development mode.
        Uses the same JSON formatter as the file handler for consistency.

        Note:
            Console output is particularly useful during development and debugging.
        """
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self.formatter)
        self.logger.addHandler(console_handler)
