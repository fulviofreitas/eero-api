"""Closed catalogue of the API's error codes and their SDK exception mapping.

The API reports failures as ``{"meta": {"code": <http status>, "error":
<string>, ...}}``. ``meta.error`` is drawn from a closed set of dot-separated
strings (matched case-insensitively by the SDK); some error responses omit
``meta.error`` entirely, or carry a free-text sentence instead of one of
these strings. This module is the single source of truth for that catalogue
and for grouping each string by the SDK exception class it should raise.

The transport (``eero.api.base``) is the only caller of
:func:`exception_for_error` — it is the single place classification happens.
Nothing here ever raises; it only builds and returns exception instances.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, FrozenSet, Optional

from .exceptions import (
    EeroAccessDeniedException,
    EeroAPIException,
    EeroAuthenticationException,
    EeroClientBlockedException,
    EeroException,
    EeroFeatureUnavailableException,
    EeroNotFoundException,
    EeroPremiumRequiredException,
    EeroRateLimitException,
    EeroValidationException,
)


class ErrorGroup(str, Enum):
    """A group of catalogue error strings that share an SDK exception class."""

    SESSION = "session"
    SESSION_REFRESH = "session_refresh"
    VERIFICATION = "verification"
    ACCESS_DENIED = "access_denied"
    NOT_FOUND = "not_found"
    RATE_LIMIT = "rate_limit"
    VALIDATION = "validation"
    PREMIUM = "premium"
    FEATURE_UNAVAILABLE = "feature_unavailable"
    CLIENT_BLOCKED = "client_blocked"
    DOMAIN = "domain"


# Session errors (401): terminal, credential-clearing.
SESSION_ERRORS: FrozenSet[str] = frozenset(
    {
        "error.session.expired",
        "error.session.invalid",
        "error.session.revoked",
    }
)

# Session-refresh signal (401): not terminal, triggers the transparent
# refresh-and-replay in the transport. Never clears credentials.
SESSION_REFRESH_ERRORS: FrozenSet[str] = frozenset({"error.session.refresh"})

# Verification / login-state errors (401): the token has been issued but the
# account is mid-verification or otherwise blocked from completing login.
# Never clears credentials.
VERIFICATION_ERRORS: FrozenSet[str] = frozenset(
    {
        "error.verification.required",
        "error.verification.invalid",
        "error.verification.expired",
        "error.verification.failure",
        "error.verification.blocked",
        "error.login.unknown",
        "error.login.blocked",
        "error.too.many.resends",
        "error.email.unverified",
    }
)

# Access denied (403): authenticated, but not permitted. Not an auth error.
ACCESS_DENIED_ERRORS: FrozenSet[str] = frozenset({"error.access.denied"})

# Not found (404). A 404 with no meta.error at all, or with a free-text
# sentence instead of one of these strings, also maps to EeroNotFoundException
# -- see exception_for_error.
NOT_FOUND_ERRORS: FrozenSet[str] = frozenset(
    {
        "error.network.not.found",
        "error.eero.no_serial_found",
        "error.software_keys.not_found",
    }
)

# Rate limiting. Reported either via HTTP 429 or this string on another status.
RATE_LIMIT_ERRORS: FrozenSet[str] = frozenset({"error.rate.limit"})

# Client-side-shaped validation errors returned by the server (HTTP 400).
VALIDATION_ERRORS: FrozenSet[str] = frozenset(
    {
        "error.form.errors",
        "error.form.email.unavailable",
        "error.form.phone.unavailable",
        "error.form.email.malformed",
        "error.form.phone.malformed",
        "error.invites.format.faulty",
        "error.invalid.user.role",
        "error.reservation.ip.invalid",
        "error.network.multistaticipv2.wan_ip_not_in_range",
    }
)

# Premium/subscription gating. Maps to EeroPremiumRequiredException regardless
# of HTTP status.
PREMIUM_ERRORS: FrozenSet[str] = frozenset(
    {
        "error.premium.user_not_subscribed",
        "error.partner.unavailable",
    }
)

# Feature unavailable on this device/network. Maps to
# EeroFeatureUnavailableException regardless of HTTP status.
FEATURE_UNAVAILABLE_ERRORS: FrozenSet[str] = frozenset(
    {
        "error.eero.offline",
        "error.network.unavailable",
        "error.eero.not.capable",
        "error.eero.deactivated",
        "error.eero.owned_by_organization",
        "error.eero.wifibackup.as.gateway",
        "error.eero.already.owned",
        "error.eero.needs.reset",
    }
)

# Client version rejected by the API. Maps to EeroClientBlockedException
# regardless of HTTP status.
CLIENT_BLOCKED_ERRORS: FrozenSet[str] = frozenset({"error.app.version.blocked"})

# Domain-specific errors that stay EeroAPIException; the sub-code is exposed
# via error_code for callers that want to branch on it.
DOMAIN_ERRORS: FrozenSet[str] = frozenset(
    {
        "error.reservation.failed",
        "error.assignment.ip.unavailable",
        "error.assignment.port.unavailable",
        "error.forward.failed",
        "error.backup.access.point.ssid.already.exists",
        "error.backup.access.point.ssid.conflict",
        "error.max.number.of.backup.access.points.reached",
        "error.invite.status.accepted",
        "error.invite.status.rejected",
        "error.invite.status.revoked",
        "error.invite.status.expired",
        "error.max.admins.reached",
        "error.public_static_ip.reservation.error",
        "error.network.transfer.recipient.unverified_phone",
        "error.network.transfer.recipient.unverified_email",
        "error.network.transfer.recipient.mismatched_phone",
        "error.network.transfer.recipient.mismatched_email",
        "error.network.transfer.recipient.ambiguous",
        "error.user.amazon_login.exists",
        "error.user.amazon_login.email.unavailable",
        "error.software_keys.already_used",
        "error.stripe.card.incorrect_number",
        "error.stripe.card.expired",
        "error.stripe.card.incorrect_cvc",
        "error.stripe.card.incorrect_zip",
        "error.stripe.card.declined",
        "error.stripe.card.processing_error",
        "error.stripe.coupon.inappropriate",
        "error.stripe.coupon.invalid",
        "error.stripe.coupon.missing",
        "encryptme.error.email.exists",
        "encryptme.error.email.invalid",
        "encryptme.error.creation.failed",
    }
)

# Every group, keyed by its enum member. Used to build the reverse lookup and
# to validate the catalogue's internal consistency (no duplicate strings,
# every group non-empty).
_GROUP_MEMBERS: Dict[ErrorGroup, FrozenSet[str]] = {
    ErrorGroup.SESSION: SESSION_ERRORS,
    ErrorGroup.SESSION_REFRESH: SESSION_REFRESH_ERRORS,
    ErrorGroup.VERIFICATION: VERIFICATION_ERRORS,
    ErrorGroup.ACCESS_DENIED: ACCESS_DENIED_ERRORS,
    ErrorGroup.NOT_FOUND: NOT_FOUND_ERRORS,
    ErrorGroup.RATE_LIMIT: RATE_LIMIT_ERRORS,
    ErrorGroup.VALIDATION: VALIDATION_ERRORS,
    ErrorGroup.PREMIUM: PREMIUM_ERRORS,
    ErrorGroup.FEATURE_UNAVAILABLE: FEATURE_UNAVAILABLE_ERRORS,
    ErrorGroup.CLIENT_BLOCKED: CLIENT_BLOCKED_ERRORS,
    ErrorGroup.DOMAIN: DOMAIN_ERRORS,
}

# Reverse lookup, built once at import time. Every catalogue string is
# lowercase and stable; membership is validated by tests/test_errors.py.
_STRING_TO_GROUP: Dict[str, ErrorGroup] = {
    error_string: group for group, members in _GROUP_MEMBERS.items() for error_string in members
}

# The groups that select their SDK exception class regardless of the HTTP
# status code that carried them.
_STATUS_INDEPENDENT_GROUPS: FrozenSet[ErrorGroup] = frozenset(
    {
        ErrorGroup.PREMIUM,
        ErrorGroup.FEATURE_UNAVAILABLE,
        ErrorGroup.CLIENT_BLOCKED,
        ErrorGroup.RATE_LIMIT,
    }
)


def classify_error_code(error_code: Optional[str]) -> Optional[ErrorGroup]:
    """Return the catalogue group for an API error code.

    Matching is case-insensitive and trims surrounding whitespace, matching
    how the transport extracts ``meta.error``.

    Args:
        error_code: The value of ``envelope["meta"]["error"]``, or ``None``.

    Returns:
        The :class:`ErrorGroup` the string belongs to, or ``None`` when
        ``error_code`` is ``None``, empty, or not present in the catalogue
        (for example a free-text sentence, or an error string the SDK does
        not yet recognise).
    """
    if not error_code:
        return None
    normalized = error_code.strip().lower()
    return _STRING_TO_GROUP.get(normalized)


def message_for_error_code(error_code: Optional[str]) -> str:
    """Build a leak-safe exception message for a ``meta.error`` value.

    When ``error_code`` classifies into a known catalogue group, the message
    is the catalogue string itself (normalized: trimmed and lowercased).
    Otherwise -- ``error_code`` is ``None``, empty, or an unrecognised /
    free-text value -- the message is the fixed label below. Neither branch
    ever embeds any other part of the response body (no ``data``, no raw
    body text, no request URL): those stay out of exception messages and are
    only ever available via the ``envelope`` attribute or a debug log line.

    Args:
        error_code: The value of ``envelope["meta"]["error"]``, or ``None``.

    Returns:
        The message text to use for the raised exception.
    """
    if classify_error_code(error_code) is not None:
        # classify_error_code returning non-None guarantees error_code is a
        # non-empty string (see its own None/empty short-circuit above).
        return error_code.strip().lower()  # type: ignore[union-attr]
    return "unrecognised error string"


def exception_for_error(
    status_code: int,
    *,
    envelope: Optional[Dict[str, Any]],
    error_code: Optional[str],
) -> EeroException:
    """Choose and build the SDK exception for a non-2xx, non-3xx API response.

    Classification never rejects or alters ``envelope`` -- it is only ever
    attached to the returned exception, verbatim. The exception message is
    always built by :func:`message_for_error_code`, never from the raw
    response body or the request URL. Precedence:

    1. HTTP 401 always -> :class:`EeroAuthenticationException`, regardless
       of ``meta.error``. This is checked first, before the
       status-independent groups below, so this function stays safe as the
       single classification point even for a 401 carrying one of their
       strings (which should not happen per the catalogue, but must never
       silently downgrade an authentication failure to something else).
    2. Otherwise, a ``meta.error`` string in one of the status-independent
       groups (premium/feature-unavailable/client-blocked/rate-limit)
       always wins, regardless of the HTTP status code.
    3. Otherwise the HTTP status code selects the class: 403 (with
       ``error.access.denied``) -> :class:`EeroAccessDeniedException`, 404 ->
       :class:`EeroNotFoundException` (regardless of whether ``meta.error``
       is present, recognised, or free text), 400 (with a recognised
       validation string) -> :class:`EeroValidationException`.
    4. Anything else -- including every recognised "domain" string, an
       unrecognised string, and a 403/400 that doesn't match the groups
       above -- is :class:`EeroAPIException`.

    An unrecognised or free-text ``meta.error`` never changes the class
    chosen by the HTTP status and never raises on its own; it is only
    carried through as ``error_code`` on whatever exception is returned.

    Args:
        status_code: The HTTP status code of the response.
        envelope: The raw, unmodified parsed response envelope, or ``None``.
        error_code: The value of ``envelope["meta"]["error"]``, or ``None``.

    Returns:
        An unraised :class:`EeroException` instance carrying ``envelope`` and
        ``error_code``. The caller is responsible for raising it.
    """
    message = message_for_error_code(error_code)
    group = classify_error_code(error_code)

    if status_code == 401:
        return EeroAuthenticationException(message, envelope=envelope, error_code=error_code)

    if group in _STATUS_INDEPENDENT_GROUPS:
        if group is ErrorGroup.PREMIUM:
            return EeroPremiumRequiredException.from_response(
                message, status_code=status_code, envelope=envelope, error_code=error_code
            )
        if group is ErrorGroup.FEATURE_UNAVAILABLE:
            return EeroFeatureUnavailableException.from_response(
                message, status_code=status_code, envelope=envelope, error_code=error_code
            )
        if group is ErrorGroup.CLIENT_BLOCKED:
            return EeroClientBlockedException(
                status_code, message, envelope=envelope, error_code=error_code
            )
        # ErrorGroup.RATE_LIMIT
        return EeroRateLimitException(message, envelope=envelope, error_code=error_code)

    if status_code == 403:
        if group is ErrorGroup.ACCESS_DENIED:
            return EeroAccessDeniedException(
                status_code, message, envelope=envelope, error_code=error_code
            )
        return EeroAPIException(status_code, message, envelope=envelope, error_code=error_code)

    if status_code == 404:
        return EeroNotFoundException.from_response(
            message, status_code=status_code, envelope=envelope, error_code=error_code
        )

    if status_code == 429:
        return EeroRateLimitException(message, envelope=envelope, error_code=error_code)

    if status_code == 400 and group is ErrorGroup.VALIDATION:
        return EeroValidationException.from_response(
            message, envelope=envelope, error_code=error_code
        )

    return EeroAPIException(status_code, message, envelope=envelope, error_code=error_code)
