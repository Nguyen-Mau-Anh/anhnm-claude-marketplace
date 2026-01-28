"""Structured logging for orchestrators.

Provides timestamped, level-based logging with stage tracking.
"""

import sys
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Optional, TextIO


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class Logger:
    """
    Structured logger for orchestrators.

    Features:
    - Timestamped log entries
    - Log levels (DEBUG, INFO, WARN, ERROR)
    - Stage-based logging
    - Console and optional file output
    - Automatic flush for real-time visibility
    - Story-specific log file creation
    """

    def __init__(
        self,
        name: str,
        level: LogLevel = LogLevel.INFO,
        log_file: Optional[Path] = None,
    ):
        """
        Initialize logger.

        Args:
            name: Logger name (e.g., "orchestrate-dev")
            level: Minimum log level to display
            log_file: Optional file path for log output
        """
        self.name = name
        self.level = level
        self.log_file = log_file
        self._file_handle: Optional[TextIO] = None
        self._current_stage: Optional[str] = None

        # Open log file if specified
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self._file_handle = open(self.log_file, 'a')

    @classmethod
    def for_story(
        cls,
        story_id: str,
        project_root: Path,
        level: LogLevel = LogLevel.INFO,
    ) -> "Logger":
        """
        Create a logger for a specific story.

        Args:
            story_id: Story identifier (e.g., "1-2-feature", "PROJ-123")
            project_root: Project root directory
            level: Log level (default: INFO)

        Returns:
            Logger instance with story-specific log file

        Example:
            logger = Logger.for_story("1-2-auth", Path.cwd())
            # Creates: .orchestrate-temp/logs/stories/1-2-auth.log
        """
        log_dir = project_root / ".orchestrate-temp/logs/stories"
        log_file = log_dir / f"{story_id}.log"

        logger = cls(name=story_id, level=level, log_file=log_file)
        logger.info(f"Story log initialized: {story_id}")
        logger.separator()
        return logger

    @classmethod
    def for_stage(
        cls,
        stage_name: str,
        story_id: str,
        project_root: Path,
        level: LogLevel = LogLevel.INFO,
    ) -> "Logger":
        """
        Create a logger for a specific stage within a story.

        Args:
            stage_name: Stage name (e.g., "planning", "implementation")
            story_id: Story identifier
            project_root: Project root directory
            level: Log level (default: INFO)

        Returns:
            Logger instance with stage-specific log file

        Example:
            logger = Logger.for_stage("planning", "1-2-auth", Path.cwd())
            # Creates: .orchestrate-temp/logs/stories/1-2-auth/planning.log
        """
        log_dir = project_root / f".orchestrate-temp/logs/stories/{story_id}"
        log_file = log_dir / f"{stage_name}.log"

        logger = cls(name=f"{story_id}:{stage_name}", level=level, log_file=log_file)
        logger.info(f"Stage log initialized: {stage_name} for {story_id}")
        logger.separator()
        return logger

    @classmethod
    def for_workflow(
        cls,
        workflow_name: str,
        project_root: Path,
        level: LogLevel = LogLevel.INFO,
    ) -> "Logger":
        """
        Create a logger for a workflow execution.

        Args:
            workflow_name: Workflow name (e.g., "orchestrate-dev", "test-runner")
            project_root: Project root directory
            level: Log level (default: INFO)

        Returns:
            Logger instance with workflow-specific log file

        Example:
            logger = Logger.for_workflow("orchestrate-dev", Path.cwd())
            # Creates: .orchestrate-temp/logs/workflows/orchestrate-dev.log
        """
        log_dir = project_root / ".orchestrate-temp/logs/workflows"
        log_file = log_dir / f"{workflow_name}.log"

        logger = cls(name=workflow_name, level=level, log_file=log_file)
        logger.info(f"Workflow log initialized: {workflow_name}")
        logger.separator()
        return logger

    def __del__(self):
        """Cleanup file handle on deletion."""
        if self._file_handle:
            try:
                self._file_handle.close()
            except:
                pass

    def _should_log(self, level: LogLevel) -> bool:
        """Check if message at level should be logged."""
        levels = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARN, LogLevel.ERROR]
        return levels.index(level) >= levels.index(self.level)

    def _format_message(self, level: LogLevel, message: str) -> str:
        """Format log message with timestamp and context."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        stage_prefix = f"[{self._current_stage}] " if self._current_stage else ""
        return f"[{timestamp}] [{self.name}] {stage_prefix}[{level.value}] {message}"

    def _write(self, formatted_message: str) -> None:
        """Write message to console and file."""
        # Console output
        print(formatted_message, flush=True)

        # File output
        if self._file_handle:
            self._file_handle.write(formatted_message + "\n")
            self._file_handle.flush()

    def debug(self, message: str) -> None:
        """Log debug message."""
        if self._should_log(LogLevel.DEBUG):
            self._write(self._format_message(LogLevel.DEBUG, message))

    def info(self, message: str) -> None:
        """Log info message."""
        if self._should_log(LogLevel.INFO):
            self._write(self._format_message(LogLevel.INFO, message))

    def warn(self, message: str) -> None:
        """Log warning message."""
        if self._should_log(LogLevel.WARN):
            self._write(self._format_message(LogLevel.WARN, message))

    def error(self, message: str) -> None:
        """Log error message."""
        if self._should_log(LogLevel.ERROR):
            self._write(self._format_message(LogLevel.ERROR, message))

    def stage_start(self, stage_name: str) -> None:
        """Mark the start of a pipeline stage."""
        self._current_stage = stage_name
        self.info(f"=== Stage: {stage_name} - START ===")

    def stage_end(self, stage_name: str, success: bool, duration_seconds: Optional[float] = None) -> None:
        """Mark the end of a pipeline stage."""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        duration_str = f" ({duration_seconds:.1f}s)" if duration_seconds else ""
        self.info(f"=== Stage: {stage_name} - {status}{duration_str} ===")
        self._current_stage = None

    def set_level(self, level: LogLevel) -> None:
        """Change log level at runtime."""
        self.level = level
        self.debug(f"Log level set to {level.value}")

    def separator(self, char: str = "=", length: int = 60) -> None:
        """Print a visual separator."""
        print(char * length, flush=True)
        if self._file_handle:
            self._file_handle.write(char * length + "\n")
            self._file_handle.flush()

    def write_to_file_only(self, content: str) -> None:
        """
        Write content directly to log file without console output or timestamp.

        Useful for logging large agent outputs that should be in the file but not the console.

        Args:
            content: Content to write to file only
        """
        if self._file_handle:
            self._file_handle.write(content + "\n")
            self._file_handle.flush()


# Convenience function for quick logging
def log(message: str, level: LogLevel = LogLevel.INFO) -> None:
    """Quick log function without creating logger instance."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] [{level.value}] {message}"
    print(formatted, flush=True)
