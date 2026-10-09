"""Secure logging utilities for Eero API.

This module provides a SecureLogger that automatically redacts sensitive
data from log messages based on field names and patterns.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from functools import lru_cache
from typing import Any, Dict, FrozenSet, MutableMapping, Optional, Pattern, Tuple

# Default sensitive field name patterns (case-insensitive). Includes both
# credential-shaped fields (token/password/secret/...) and identifier-shaped
# fields (login/email/phone/...) that could otherwise leak a user-submitted
# identifier (e.g. the value passed to AuthAPI.login) into a log record via
# an echoed API response or a caller-provided extra/args dict.
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
        "login",
        "email",
        "phone",
        "sms",
        "serial",
        "mac",
        "mac_address",
        "ssid",
    }
)

# The subset of sensitive patterns considered credential-shaped rather than
# merely identifier-shaped. A key matching one of these must never have any
# of its value's leading characters logged -- only its length (see
# _redact_value / _redact_dict). Identifier-shaped fields (email, phone,
# ...) still show a short prefix for debugging usability.
_ZERO_VISIBILITY_PATTERNS: FrozenSet[str] = frozenset(
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

# Containers nested deeper than this are replaced wholesale by
# ``_UNTRAVERSABLE_PLACEHOLDER`` rather than walked, so a pathological or
# hostile structure can neither exhaust the interpreter stack nor smuggle a
# value past the redactor by sitting below the point where it stops looking.
_MAX_REDACTION_DEPTH = 16

# Substituted for a container that is part of a reference cycle or that sits
# below ``_MAX_REDACTION_DEPTH``. Fixed text: it never depends on the content
# it replaces.
_UNTRAVERSABLE_PLACEHOLDER = "[REDACTED:cyclic-or-too-deep]"


@lru_cache(maxsize=32)
def _get_sensitive_regex(patterns: FrozenSet[str]) -> Pattern[str]:
    """Get a compiled regex for a specific set of sensitive field patterns.

    Cached per distinct ``patterns`` argument (via ``lru_cache``) rather than
    behind a single module-global slot, so a logger built with a narrow or
    custom pattern set can never leak into -- or be leaked into by -- the
    cached regex for a different pattern set (e.g. ``DEFAULT_SENSITIVE_
    PATTERNS``) built before or after it.

    Args:
        patterns: Set of sensitive field name patterns

    Returns:
        Compiled regex pattern
    """
    pattern = "|".join(re.escape(p) for p in patterns)
    return re.compile(pattern, re.IGNORECASE)


def _is_sensitive_key(key: object, patterns: FrozenSet[str] = DEFAULT_SENSITIVE_PATTERNS) -> bool:
    """Check if a key name indicates sensitive data.

    Args:
        key: The key/field name to check. Matched via ``str(key)``, so a
            non-string mapping key (an ``int``, a tuple, ...) is checked by
            its text form instead of raising.
        patterns: Set of sensitive patterns to match against

    Returns:
        True if the key appears to be sensitive
    """
    key_lower = str(key).lower()
    regex = _get_sensitive_regex(patterns)
    return bool(regex.search(key_lower))


def _is_zero_visibility_key(key: object) -> bool:
    """Check if a key name is credential-shaped and must never show a value prefix.

    Args:
        key: The key/field name to check (matched via ``str(key)``)

    Returns:
        True if the key matches one of ``_ZERO_VISIBILITY_PATTERNS``
    """
    regex = _get_sensitive_regex(_ZERO_VISIBILITY_PATTERNS)
    return bool(regex.search(str(key).lower()))


def _redact_value(value: Any, visible_chars: int = 4) -> str:
    """Redact a sensitive value for safe logging.

    Args:
        value: The value to redact
        visible_chars: Number of characters to show. A value of 0 (or a
            string no longer than this many characters) shows the length
            only, never any of the value's own characters.

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
    if visible_chars <= 0 or length <= visible_chars:
        return f"[REDACTED:{length}chars]"

    return f"{str_value[:visible_chars]}...[REDACTED:{length}chars]"


def _redact(
    value: Any,
    patterns: FrozenSet[str],
    visible_chars: int,
    depth: int = 0,
    ancestors: FrozenSet[int] = frozenset(),
) -> Any:
    """Recursively build a redacted copy of ``value``.

    Mappings, lists and tuples are walked; every other value is returned
    as-is. The argument is never mutated: each container is rebuilt, a
    mapping as a plain ``dict`` (keys preserved as-is) and a list or tuple as
    the same kind of sequence.

    Args:
        value: The value to redact
        patterns: Set of sensitive field patterns
        visible_chars: Number of characters to show for redacted values
        depth: Nesting level of ``value`` (0 for the top-level argument)
        ancestors: ``id()`` of every container on the path from the top-level
            argument down to ``value``; membership means a reference cycle

    Returns:
        A new structure with sensitive values redacted, or
        ``_UNTRAVERSABLE_PLACEHOLDER`` for a container that is cyclic or
        nested deeper than ``_MAX_REDACTION_DEPTH``
    """
    if not isinstance(value, (Mapping, list, tuple)):
        return value
    if depth >= _MAX_REDACTION_DEPTH or id(value) in ancestors:
        return _UNTRAVERSABLE_PLACEHOLDER

    path = ancestors | {id(value)}
    if isinstance(value, Mapping):
        result: Dict[Any, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(key, patterns):
                # Credential-shaped keys (token/password/secret/...) never
                # show any leading characters, regardless of the caller's
                # visible_chars -- only identifier-shaped keys (email/phone/...)
                # get the normal partial-prefix redaction.
                key_visible_chars = 0 if _is_zero_visibility_key(key) else visible_chars
                result[key] = _redact_value(item, key_visible_chars)
            else:
                result[key] = _redact(item, patterns, visible_chars, depth + 1, path)
        return result

    items = [_redact(item, patterns, visible_chars, depth + 1, path) for item in value]
    return tuple(items) if isinstance(value, tuple) else items


def redact_sensitive(
    value: Any,
    patterns: FrozenSet[str] = DEFAULT_SENSITIVE_PATTERNS,
    visible_chars: int = 4,
) -> Any:
    """Redact sensitive data from any value for safe logging.

    This function can handle:
    - Mappings (recursively redacts sensitive keys; the result is a ``dict``)
    - Lists and tuples (each element is redacted; the container type is kept)
    - Any nesting of the above, to a depth of 16 levels. A container that is
      part of a reference cycle, or nested deeper, is replaced by a fixed
      placeholder rather than raising.
    - Strings and other types (returned as-is, use for values you know are safe)

    The argument is never mutated; redacted structures are always new objects.

    Args:
        value: The value to potentially redact
        patterns: Set of sensitive field name patterns
        visible_chars: Number of visible characters for redacted values

    Returns:
        Value with sensitive data redacted
    """
    return _redact(value, patterns, visible_chars)


class SecureLoggerAdapter(logging.LoggerAdapter):  # type: ignore[type-arg]
    """Logger adapter that automatically redacts sensitive data.

    This adapter wraps a standard Python logger and automatically
    detects and redacts sensitive field names in log arguments.

    Example:
        logger = get_secure_logger(__name__)
        logger.debug("User data: %s", {"user_token": "abc123", "name": "John"})
        # Logs: "User data: {'user_token': '[REDACTED:6chars]', 'name': 'John'}"
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
        """Process a log call: redact the message object and the ``extra`` dict.

        The adapter's own ``extra`` context and the call's ``extra`` are
        merged (the call's keys win) and the result is redacted, so both end
        up on the record attributes in redacted form.

        Args:
            msg: The log message (normally a format string)
            kwargs: Keyword arguments for the log call

        Returns:
            Tuple of (message, kwargs) with sensitive data redacted
        """
        extra = {**(self.extra or {}), **(kwargs.get("extra") or {})}
        if extra:
            kwargs["extra"] = _redact(extra, self._sensitive_patterns, self._visible_chars)
        return redact_sensitive(msg, self._sensitive_patterns, self._visible_chars), kwargs

    def log(self, level: int, msg: Any, *args: Any, **kwargs: Any) -> None:
        """Log ``msg`` at ``level`` after redacting its arguments and ``extra``.

        Every other logging method of the adapter (``debug``, ``info``,
        ``warning``, ``error``, ``critical``, ``exception``) funnels through
        here, so they all share this one redaction path. The level check runs
        first: a disabled level costs nothing and cannot raise, whatever the
        arguments are.

        Args:
            level: Log level
            msg: Log message format string
            *args: Positional arguments for string formatting
            **kwargs: Keyword arguments for the underlying logger
        """
        if not self.isEnabledFor(level):
            return
        redacted_msg, redacted_kwargs = self.process(msg, kwargs)
        redacted_args = tuple(
            redact_sensitive(arg, self._sensitive_patterns, self._visible_chars) for arg in args
        )
        self.logger.log(level, redacted_msg, *redacted_args, **redacted_kwargs)


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
        # Output: Response: {'user_token': '[REDACTED:9chars]', 'status': 'ok'}
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

        No cache invalidation is needed here: ``_get_sensitive_regex`` is
        keyed by the pattern set itself, so the returned (new) frozenset
        simply gets its own independently-cached regex on first use.
    """
    return DEFAULT_SENSITIVE_PATTERNS | {pattern.lower()}
