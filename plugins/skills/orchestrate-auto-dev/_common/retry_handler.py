"""Retry logic with exponential backoff.

Provides configurable retry mechanism for failed operations.
"""

import time
import functools
from typing import Callable, Optional, Any, Type, Tuple, List
from dataclasses import dataclass
from enum import Enum

from .logger import Logger

logger = Logger("retry_handler")


class BackoffStrategy(str, Enum):
    """Backoff strategies for retry delays."""
    CONSTANT = "constant"      # Same delay each time
    LINEAR = "linear"          # Linearly increasing delay
    EXPONENTIAL = "exponential"  # Exponentially increasing delay


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    backoff_multiplier: float = 2.0
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    on_retry: Optional[Callable[[int, Exception], None]] = None


class RetryHandler:
    """
    Handle retry logic with configurable backoff.

    Features:
    - Multiple backoff strategies
    - Configurable retry conditions
    - Retry statistics
    - Callback on retry
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize retry handler.

        Args:
            config: Retry configuration (uses defaults if None)
        """
        self.config = config or RetryConfig()
        self.retry_stats: List[dict] = []

    def retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None
        attempt = 0

        logger.debug(f"Starting retry handler for {func.__name__} (max {self.config.max_attempts} attempts)")

        while attempt < self.config.max_attempts:
            attempt += 1

            try:
                result = func(*args, **kwargs)

                # Success - record stats
                if attempt > 1:
                    logger.info(f"Function {func.__name__} succeeded after {attempt} attempts")
                    self.retry_stats.append({
                        'function': func.__name__,
                        'attempts': attempt,
                        'success': True,
                    })
                else:
                    logger.debug(f"Function {func.__name__} succeeded on first attempt")

                return result

            except self.config.retryable_exceptions as e:
                last_exception = e

                # Last attempt - don't retry
                if attempt >= self.config.max_attempts:
                    logger.error(f"Function {func.__name__} failed after {attempt} attempts: {str(e)[:100]}")
                    self.retry_stats.append({
                        'function': func.__name__,
                        'attempts': attempt,
                        'success': False,
                        'error': str(e),
                    })
                    break

                # Log retry attempt
                logger.warning(
                    f"Function {func.__name__} failed "
                    f"(attempt {attempt}/{self.config.max_attempts}): {str(e)[:100]}"
                )

                # Call retry callback if configured
                if self.config.on_retry:
                    try:
                        self.config.on_retry(attempt, e)
                    except Exception:
                        pass  # Don't let callback errors affect retry

                # Calculate delay
                delay = self._calculate_delay(attempt)
                logger.info(f"Retrying {func.__name__} in {delay:.1f}s (attempt {attempt + 1}/{self.config.max_attempts})")

                # Wait before retry
                time.sleep(delay)

        # All retries exhausted - raise last exception
        if last_exception:
            raise last_exception

    def retry_async(self, func: Callable, *args, **kwargs):
        """
        Async version of retry (placeholder for future implementation).

        Note: Requires async/await support
        """
        raise NotImplementedError("Async retry not yet implemented")

    def should_retry(self, exception: Exception) -> bool:
        """
        Check if exception is retryable.

        Args:
            exception: Exception to check

        Returns:
            True if should retry, False otherwise
        """
        return isinstance(exception, self.config.retryable_exceptions)

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay before next retry.

        Args:
            attempt: Current attempt number (1-indexed)

        Returns:
            Delay in seconds
        """
        if self.config.backoff_strategy == BackoffStrategy.CONSTANT:
            delay = self.config.base_delay_seconds

        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.config.base_delay_seconds * attempt

        elif self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.config.base_delay_seconds * (self.config.backoff_multiplier ** (attempt - 1))

        else:
            delay = self.config.base_delay_seconds

        # Cap at max delay
        capped_delay = min(delay, self.config.max_delay_seconds)
        logger.debug(f"Calculated delay: {capped_delay:.1f}s (strategy: {self.config.backoff_strategy.value}, attempt: {attempt})")
        return capped_delay

    def get_stats(self) -> dict:
        """
        Get retry statistics.

        Returns:
            Dictionary with retry stats
        """
        if not self.retry_stats:
            logger.debug("No retry stats available")
            return {
                'total_retries': 0,
                'successful_retries': 0,
                'failed_retries': 0,
            }

        total = len(self.retry_stats)
        successful = sum(1 for s in self.retry_stats if s['success'])
        failed = total - successful

        logger.debug(f"Retry stats: {total} total, {successful} successful, {failed} failed")

        return {
            'total_retries': total,
            'successful_retries': successful,
            'failed_retries': failed,
            'details': self.retry_stats,
        }

    def reset_stats(self) -> None:
        """Clear retry statistics."""
        stats_count = len(self.retry_stats)
        self.retry_stats = []
        logger.debug(f"Reset retry statistics (cleared {stats_count} entries)")


# Decorator for adding retry to functions
def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator to add retry logic to a function.

    Args:
        max_attempts: Maximum retry attempts
        base_delay: Base delay between retries
        backoff_strategy: Backoff strategy to use
        retryable_exceptions: Exceptions that trigger retry

    Example:
        @with_retry(max_attempts=3, base_delay=2.0)
        def flaky_function():
            # May fail sometimes
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay_seconds=base_delay,
                backoff_strategy=backoff_strategy,
                retryable_exceptions=retryable_exceptions,
            )
            handler = RetryHandler(config)
            return handler.retry(func, *args, **kwargs)
        return wrapper
    return decorator


# Convenience function for quick retry
def retry_on_failure(
    func: Callable,
    max_attempts: int = 3,
    delay: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Any:
    """
    Quick retry function without creating handler.

    Args:
        func: Function to execute
        max_attempts: Maximum attempts
        delay: Delay between retries
        exceptions: Exceptions to catch

    Returns:
        Result from func
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay_seconds=delay,
        retryable_exceptions=exceptions,
    )
    handler = RetryHandler(config)
    return handler.retry(func)
