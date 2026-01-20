"""Secure logging utilities for Eero API.

This module provides a SecureLogger that automatically redacts sensitive
data from log messages based on field names and patterns.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any, Dict, FrozenSet, List, MutableMapping, Optional, Pattern, Tuple

# Default sensitive field name patterns (case-insensitive)
DEFAULT_SENSITIVE_PATTERNS: FrozenSet[str] = frozenset(
    {
        "token",
        "password",
        "passwd",
        "secret",
        "key",
        "credential",
        "session_id",
        "session",
        "cookie",
        "auth",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "user_token",
        "bearer",
        "authorization",
        "private",
    }
)

# Compiled regex for detecting sensitive field names
_SENSITIVE_REGEX: Optional[Pattern[str]] = None


def _get_sensitive_regex(patterns: FrozenSet[str]) -> Pattern[str]:
    """Get compiled regex for sensitive field detection.

    Args:
        patterns: Set of sensitive field name patterns

    Returns:
        Compiled regex pattern
    """
    global _SENSITIVE_REGEX
    if _SENSITIVE_REGEX is None:
        pattern = "|".join(re.escape(p) for p in patterns)
        _SENSITIVE_REGEX = re.compile(pattern, re.IGNORECASE)
    return _SENSITIVE_REGEX


def _is_sensitive_key(key: str, patterns: FrozenSet[str] = DEFAULT_SENSITIVE_PATTERNS) -> bool:
    """Check if a key name indicates sensitive data.

    Args:
        key: The key/field name to check
        patterns: Set of sensitive patterns to match against

    Returns:
        True if the key appears to be sensitive
    """
    key_lower = key.lower()
    regex = _get_sensitive_regex(patterns)
    return bool(regex.search(key_lower))


def _redact_value(value: Any, visible_chars: int = 4) -> str:
    """Redact a sensitive value for safe logging.

    Args:
        value: The value to redact
        visible_chars: Number of characters to show (default 4)

    Returns:
        Redacted string representation
    """
    if value is None:
        return "[NONE]"
    if isinstance(value, bool):
        return "[REDACTED:bool]"
    if isinstance(value, (int, float)):
        return "[REDACTED:number]"

    str_value = str(value)
    if not str_value:
        return "[EMPTY]"

    length = len(str_value)
    if length <= visible_chars:
        return f"[REDACTED:{length}chars]"

    return f"{str_value[:visible_chars]}...[REDACTED:{length}chars]"


def _redact_dict(
    data: Dict[str, Any],
    patterns: FrozenSet[str] = DEFAULT_SENSITIVE_PATTERNS,
    visible_chars: int = 4,
) -> Dict[str, Any]:
    """Recursively redact sensitive values in a dictionary.

    Args:
        data: Dictionary to redact
        patterns: Set of sensitive field patterns
        visible_chars: Number of characters to show for redacted values

    Returns:
        New dictionary with sensitive values redacted
    """
    result: Dict[str, Any] = {}
    for key, value in data.items():
        if _is_sensitive_key(key, patterns):
            result[key] = _redact_value(value, visible_chars)
        elif isinstance(value, dict):
            result[key] = _redact_dict(value, patterns, visible_chars)
        elif isinstance(value, list):
            redacted_list: List[Any] = []
            for item in value:
                if isinstance(item, dict):
                    redacted_list.append(_redact_dict(item, patterns, visible_chars))
                else:
                    redacted_list.append(item)
            result[key] = redacted_list
        else:
            result[key] = value
    return result


def redact_sensitive(
    value: Any,
    patterns: FrozenSet[str] = DEFAULT_SENSITIVE_PATTERNS,
    visible_chars: int = 4,
) -> Any:
    """Redact sensitive data from any value for safe logging.

    This function can handle:
    - Dictionaries (recursively redacts sensitive keys)
    - Strings (returns as-is, use for values you know are safe)
    - Other types (returns as-is)

    Args:
        value: The value to potentially redact
        patterns: Set of sensitive field name patterns
        visible_chars: Number of visible characters for redacted values

    Returns:
        Value with sensitive data redacted
    """
    if isinstance(value, dict):
        return _redact_dict(value, patterns, visible_chars)
    return value


class SecureLoggerAdapter(logging.LoggerAdapter):  # type: ignore[type-arg]
    """Logger adapter that automatically redacts sensitive data.

    This adapter wraps a standard Python logger and automatically
    detects and redacts sensitive field names in log arguments.

    Example:
        logger = get_secure_logger(__name__)
        logger.debug("User data: %s", {"user_token": "abc123", "name": "John"})
        # Logs: "User data: {'user_token': 'abc1...[REDACTED:6chars]', 'name': 'John'}"
    """

    def __init__(
        self,
        logger: logging.Logger,
        extra: Optional[Dict[str, Any]] = None,
        sensitive_patterns: FrozenSet[str] = DEFAULT_SENSITIVE_PATTERNS,
        visible_chars: int = 4,
    ) -> None:
        """Initialize the secure logger adapter.

        Args:
            logger: The underlying logger to wrap
            extra: Extra context to include in all log messages
            sensitive_patterns: Patterns that indicate sensitive field names
            visible_chars: Number of characters to show in redacted values
        """
        super().__init__(logger, extra or {})
        self._sensitive_patterns = sensitive_patterns
        self._visible_chars = visible_chars

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> Tuple[Any, MutableMapping[str, Any]]:
        """Process log message and redact sensitive data in arguments.

        Args:
            msg: The log message format string
            kwargs: Keyword arguments for the log call

        Returns:
            Tuple of (message, kwargs) with sensitive data redacted
        """
        # Redact any sensitive data in extra dict
        if "extra" in kwargs and isinstance(kwargs["extra"], dict):
            kwargs["extra"] = _redact_dict(
                kwargs["extra"],
                self._sensitive_patterns,
                self._visible_chars,
            )

        return super().process(msg, kwargs)

    def _log_with_redaction(
        self,
        level: int,
        msg: str,
        args: Tuple[Any, ...],
        **kwargs: Any,
    ) -> None:
        """Internal method to log with automatic redaction of args.

        Args:
            level: Log level
            msg: Log message format string
            args: Positional arguments for string formatting
            **kwargs: Additional keyword arguments
        """
        # Redact sensitive data in positional arguments
        redacted_args = tuple(
            redact_sensitive(arg, self._sensitive_patterns, self._visible_chars) for arg in args
        )

        # Use the underlying logger's log method
        if self.isEnabledFor(level):
            self.logger.log(level, msg, *redacted_args, **kwargs)

    def debug(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        """Log debug message with automatic redaction."""
        self._log_with_redaction(logging.DEBUG, str(msg), args, **kwargs)

    def info(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        """Log info message with automatic redaction."""
        self._log_with_redaction(logging.INFO, str(msg), args, **kwargs)

    def warning(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        """Log warning message with automatic redaction."""
        self._log_with_redaction(logging.WARNING, str(msg), args, **kwargs)

    def error(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        """Log error message with automatic redaction."""
        self._log_with_redaction(logging.ERROR, str(msg), args, **kwargs)

    def critical(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        """Log critical message with automatic redaction."""
        self._log_with_redaction(logging.CRITICAL, str(msg), args, **kwargs)

    def exception(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        """Log exception with automatic redaction."""
        kwargs["exc_info"] = kwargs.get("exc_info", True)
        self._log_with_redaction(logging.ERROR, str(msg), args, **kwargs)


@lru_cache(maxsize=128)
def get_secure_logger(
    name: str,
    sensitive_patterns: Optional[FrozenSet[str]] = None,
    visible_chars: int = 4,
) -> SecureLoggerAdapter:
    """Get a secure logger that automatically redacts sensitive data.

    This is a drop-in replacement for logging.getLogger() that returns
    a logger with automatic sensitive data redaction.

    Args:
        name: Logger name (typically __name__)
        sensitive_patterns: Optional custom set of sensitive field patterns
        visible_chars: Number of characters to show in redacted values

    Returns:
        SecureLoggerAdapter instance

    Example:
        from eero.logging import get_secure_logger

        _LOGGER = get_secure_logger(__name__)

        # Sensitive fields are automatically redacted
        _LOGGER.debug("Response: %s", {"user_token": "secret123", "status": "ok"})
        # Output: Response: {'user_token': 'secr...[REDACTED:9chars]', 'status': 'ok'}
    """
    patterns = sensitive_patterns or DEFAULT_SENSITIVE_PATTERNS
    logger = logging.getLogger(name)
    return SecureLoggerAdapter(logger, sensitive_patterns=patterns, visible_chars=visible_chars)


def add_sensitive_pattern(pattern: str) -> FrozenSet[str]:
    """Add a custom sensitive pattern to the default set.

    Args:
        pattern: The pattern to add (case-insensitive matching)

    Returns:
        New frozen set with the pattern added

    Note:
        This returns a new set; use it when creating loggers:

        patterns = add_sensitive_pattern("my_secret_field")
        logger = get_secure_logger(__name__, sensitive_patterns=patterns)
    """
    global _SENSITIVE_REGEX
    _SENSITIVE_REGEX = None  # Clear cache to rebuild with new pattern
    return DEFAULT_SENSITIVE_PATTERNS | {pattern.lower()}
