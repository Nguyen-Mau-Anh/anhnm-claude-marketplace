"""Health monitoring for spawned processes.

Monitors process health, detects timeouts, tracks resource usage,
and detects hung processes.
"""

import time
import psutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from .logger import Logger

logger = Logger("health_checker")


class HealthStatus(Enum):
    """Health status of a process."""
    HEALTHY = "healthy"
    TIMEOUT = "timeout"
    HUNG = "hung"
    HIGH_MEMORY = "high_memory"
    HIGH_CPU = "high_cpu"
    NOT_FOUND = "not_found"
    TERMINATED = "terminated"


@dataclass
class HealthReport:
    """Health check report for a process."""
    pid: int
    status: HealthStatus
    cpu_percent: float
    memory_mb: float
    runtime_seconds: float
    last_activity_seconds: float
    message: str


class HealthChecker:
    """
    Monitor health of spawned processes.

    Features:
    - Activity timeout detection (no output for X seconds)
    - CPU-based activity detection (process is working)
    - Memory usage tracking
    - Hung process detection
    """

    def __init__(
        self,
        activity_timeout: int = 1200,  # 20 minutes
        use_cpu_detection: bool = True,
        memory_limit_mb: int = 4096,  # 4GB
        cpu_threshold: float = 1.0,  # 1% CPU = active
    ):
        """
        Initialize health checker.

        Args:
            activity_timeout: Seconds without activity before timeout
            use_cpu_detection: If True, don't timeout if CPU is active
            memory_limit_mb: Memory limit in MB
            cpu_threshold: Minimum CPU% to consider process active
        """
        self.activity_timeout = activity_timeout
        self.use_cpu_detection = use_cpu_detection
        self.memory_limit_mb = memory_limit_mb
        self.cpu_threshold = cpu_threshold

        # Track last activity time per process
        self._last_activity: Dict[int, float] = {}
        self._start_time: Dict[int, float] = {}

    def register_process(self, pid: int) -> None:
        """
        Register a process for monitoring.

        Args:
            pid: Process ID to monitor
        """
        now = time.time()
        self._last_activity[pid] = now
        self._start_time[pid] = now
        logger.debug(f"Registered process {pid} for health monitoring")

    def record_activity(self, pid: int) -> None:
        """
        Record activity (output) from a process.

        Args:
            pid: Process ID
        """
        self._last_activity[pid] = time.time()
        logger.debug(f"Recorded activity for process {pid}")

    def check_health(self, pid: int) -> HealthReport:
        """
        Check health of a process.

        Args:
            pid: Process ID to check

        Returns:
            HealthReport with status and metrics
        """
        try:
            process = psutil.Process(pid)

            # Get process metrics
            cpu_percent = process.cpu_percent(interval=0.1)
            memory_mb = process.memory_info().rss / (1024 * 1024)

            # Calculate runtime
            start_time = self._start_time.get(pid, time.time())
            runtime_seconds = time.time() - start_time

            # Calculate time since last activity
            last_activity = self._last_activity.get(pid, start_time)
            last_activity_seconds = time.time() - last_activity

            # Check if process is terminated
            if not process.is_running():
                logger.warning(f"Process {pid} has terminated")
                return HealthReport(
                    pid=pid,
                    status=HealthStatus.TERMINATED,
                    cpu_percent=0,
                    memory_mb=memory_mb,
                    runtime_seconds=runtime_seconds,
                    last_activity_seconds=last_activity_seconds,
                    message="Process has terminated"
                )

            # Check memory usage
            if memory_mb > self.memory_limit_mb:
                logger.warning(f"Process {pid} high memory: {memory_mb:.0f}MB exceeds limit {self.memory_limit_mb}MB")
                return HealthReport(
                    pid=pid,
                    status=HealthStatus.HIGH_MEMORY,
                    cpu_percent=cpu_percent,
                    memory_mb=memory_mb,
                    runtime_seconds=runtime_seconds,
                    last_activity_seconds=last_activity_seconds,
                    message=f"Memory usage {memory_mb:.0f}MB exceeds limit {self.memory_limit_mb}MB"
                )

            # Check for timeout
            if last_activity_seconds > self.activity_timeout:
                # If using CPU detection, check if process is active
                if self.use_cpu_detection and cpu_percent >= self.cpu_threshold:
                    # Process is using CPU, so it's working (thinking/computing)
                    logger.debug(
                        f"Process {pid} healthy (CPU active): {cpu_percent:.1f}% CPU, "
                        f"no output for {last_activity_seconds:.0f}s"
                    )
                    return HealthReport(
                        pid=pid,
                        status=HealthStatus.HEALTHY,
                        cpu_percent=cpu_percent,
                        memory_mb=memory_mb,
                        runtime_seconds=runtime_seconds,
                        last_activity_seconds=last_activity_seconds,
                        message=f"Active (CPU: {cpu_percent:.1f}%, thinking/computing)"
                    )
                else:
                    # No CPU activity and no output = hung
                    logger.warning(f"Process {pid} hung: no activity for {last_activity_seconds:.0f}s (timeout: {self.activity_timeout}s)")
                    return HealthReport(
                        pid=pid,
                        status=HealthStatus.HUNG,
                        cpu_percent=cpu_percent,
                        memory_mb=memory_mb,
                        runtime_seconds=runtime_seconds,
                        last_activity_seconds=last_activity_seconds,
                        message=f"No activity for {last_activity_seconds:.0f}s (timeout: {self.activity_timeout}s)"
                    )

            # Process is healthy
            logger.debug(f"Process {pid} healthy: CPU {cpu_percent:.1f}%, Memory {memory_mb:.0f}MB, Runtime {runtime_seconds:.0f}s")
            return HealthReport(
                pid=pid,
                status=HealthStatus.HEALTHY,
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                runtime_seconds=runtime_seconds,
                last_activity_seconds=last_activity_seconds,
                message="Process is healthy"
            )

        except psutil.NoSuchProcess:
            logger.warning(f"Process {pid} not found")
            return HealthReport(
                pid=pid,
                status=HealthStatus.NOT_FOUND,
                cpu_percent=0,
                memory_mb=0,
                runtime_seconds=0,
                last_activity_seconds=0,
                message="Process not found"
            )
        except Exception as e:
            logger.error(f"Error checking health for process {pid}: {e}")
            return HealthReport(
                pid=pid,
                status=HealthStatus.NOT_FOUND,
                cpu_percent=0,
                memory_mb=0,
                runtime_seconds=0,
                last_activity_seconds=0,
                message=f"Error checking health: {e}"
            )

    def should_kill(self, pid: int) -> tuple[bool, str]:
        """
        Determine if a process should be killed.

        Args:
            pid: Process ID

        Returns:
            Tuple of (should_kill: bool, reason: str)
        """
        report = self.check_health(pid)

        if report.status == HealthStatus.HUNG:
            reason = f"Process hung (no activity for {report.last_activity_seconds:.0f}s)"
            logger.info(f"Process {pid} should be killed: {reason}")
            return True, reason

        if report.status == HealthStatus.HIGH_MEMORY:
            reason = f"Memory limit exceeded ({report.memory_mb:.0f}MB)"
            logger.info(f"Process {pid} should be killed: {reason}")
            return True, reason

        if report.status == HealthStatus.TERMINATED:
            logger.debug(f"Process {pid} already terminated")
            return False, "Process already terminated"

        if report.status == HealthStatus.NOT_FOUND:
            logger.debug(f"Process {pid} not found")
            return False, "Process not found"

        logger.debug(f"Process {pid} is healthy")
        return False, "Process is healthy"

    def get_resource_stats(self, pid: int) -> Optional[Dict[str, Any]]:
        """
        Get resource usage statistics for a process.

        Args:
            pid: Process ID

        Returns:
            Dict with CPU, memory, and other stats or None if not found
        """
        try:
            process = psutil.Process(pid)

            # Get detailed stats
            cpu_percent = process.cpu_percent(interval=0.1)
            memory_info = process.memory_info()
            io_counters = process.io_counters() if hasattr(process, 'io_counters') else None

            stats = {
                'pid': pid,
                'cpu_percent': cpu_percent,
                'memory_rss_mb': memory_info.rss / (1024 * 1024),
                'memory_vms_mb': memory_info.vms / (1024 * 1024),
                'num_threads': process.num_threads(),
                'status': process.status(),
                'create_time': process.create_time(),
            }

            if io_counters:
                stats['io_read_mb'] = io_counters.read_bytes / (1024 * 1024)
                stats['io_write_mb'] = io_counters.write_bytes / (1024 * 1024)

            logger.debug(f"Resource stats for process {pid}: CPU {cpu_percent:.1f}%, Memory {stats['memory_rss_mb']:.1f}MB")
            return stats

        except psutil.NoSuchProcess:
            logger.warning(f"Cannot get stats: process {pid} not found")
            return None
        except Exception as e:
            logger.error(f"Error getting resource stats for process {pid}: {e}")
            return None

    def cleanup(self, pid: int) -> None:
        """
        Clean up tracking data for a process.

        Args:
            pid: Process ID
        """
        self._last_activity.pop(pid, None)
        self._start_time.pop(pid, None)
        logger.debug(f"Cleaned up tracking data for process {pid}")


def detect_critical_errors(output: str, patterns: List[str]) -> Optional[str]:
    """
    Detect critical error patterns in process output.

    Args:
        output: Process output to check
        patterns: List of error patterns to look for

    Returns:
        Matched error pattern or None
    """
    output_lower = output.lower()

    for pattern in patterns:
        if pattern.lower() in output_lower:
            return pattern

    return None


def is_process_active(pid: int, cpu_threshold: float = 1.0) -> bool:
    """
    Check if a process is actively working (using CPU).

    Args:
        pid: Process ID
        cpu_threshold: Minimum CPU% to consider active

    Returns:
        True if process is using CPU above threshold
    """
    try:
        process = psutil.Process(pid)
        cpu_percent = process.cpu_percent(interval=0.1)
        return cpu_percent >= cpu_threshold
    except (psutil.NoSuchProcess, Exception):
        return False
