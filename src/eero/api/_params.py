"""Shared query-parameter validation and identifier resolution helpers.

Small, dependency-free helpers shared by more than one domain module in
this SDK, so that validation rules and identifier-resolution rules have
exactly one implementation each rather than one copy per module.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from ..const import API_VERSION_DEFAULT
from ..exceptions import EeroValidationException
from ._writes import as_envelope
from .links import resolve_link, resource_url, self_url

#: Valid values for a `cadence` query/body parameter, shared by every family
#: that buckets a time series into "daily" or "hourly" points (data usage,
#: insights, data-usage report settings). This is the default accepted set;
#: pass `allowed=` to `validate_cadence` for the one endpoint family
#: (network-level insights) that accepts a third bucket size.
CADENCE_VALUES = ("daily", "hourly")


def validate_cadence(value: str, *, allowed: Sequence[str] = CADENCE_VALUES) -> str:
    """Validate a `cadence` value against its endpoint's accepted buckets.

    Args:
        value: Candidate cadence value. Callers for whom cadence is
            optional must not call this with ``None``; omit the parameter
            entirely instead.
        allowed: The accepted values for the calling endpoint. Defaults to
            :data:`CADENCE_VALUES` (``"daily"``/``"hourly"``), the set the
            API accepts on every insights and data-usage read. An endpoint
            that is later found to accept other buckets passes its own
            sequence here so the rule stays in one place.

    Returns:
        ``value`` unchanged, once validated.

    Raises:
        EeroValidationException: If ``value`` is not one of ``allowed``.
    """
    if value not in allowed:
        raise EeroValidationException(
            "cadence",
            f"must be one of {tuple(allowed)}, got {value!r}",
        )
    return value


def resolve_network_url(
    network: str,
    parent: Optional[Mapping[str, Any]] = None,
    *,
    version: str = API_VERSION_DEFAULT,
) -> str:
    """Resolve a network identifier to its absolute base URL.

    The network's own URL (``self_url(parent)``) is preferred whenever the
    caller supplies the cached network envelope; otherwise the URL is built
    from ``network`` -- a bare ID, a host-relative path, or an absolute
    API-host URL -- exactly as :func:`eero.api.links.resource_url` does.

    This is the shared "identifier + optional parent" resolution rule for
    modules whose endpoints are conventional sub-paths of a network (e.g.
    ``networks/{id}/data_usage/...``) rather than paths the API publishes
    as a named hypermedia link, so a plain :func:`eero.api.links.
    sub_resource_url` call (which resolves a single named link verbatim)
    does not apply.

    Args:
        network: The network's bare ID, path, or absolute URL.
        parent: The cached network envelope (full or ``data``), if the
            caller has one. Read only; never mutated.
        version: The API version for the template fallback.

    Returns:
        The absolute URL of the network resource itself, with no trailing
        slash, suitable for a caller to append a literal suffix to.

    Raises:
        EeroValidationException: As :func:`eero.api.links.resource_url`.
    """
    envelope = as_envelope(parent)
    if envelope is not None:
        resolved = self_url(envelope)
        if resolved is not None:
            return resolved
    return resource_url(network, "networks/{id}", version=version)


def resolve_nested_url(
    network: str,
    child: str,
    *,
    prefix: str,
    suffix: str = "",
    link: Optional[str] = None,
    parent: Optional[Mapping[str, Any]] = None,
    version: str = API_VERSION_DEFAULT,
) -> str:
    """Resolve a two-level nested resource URL without double-formatting either id.

    Several endpoint families nest a child resource under a network (for
    example ``networks/{network}/profiles/{profile}/schedules`` or
    ``networks/{network}/insights/devices/{mac}``). Building that path by
    splicing ``network`` into an f-string and handing the combined text to
    :func:`eero.api.links.resource_url` as its ``template`` argument is
    unsafe: ``resource_url`` calls `str.format` a second time to substitute
    ``child``, and if ``network`` happens to contain a stray ``{`` or ``}``
    character, that second `.format()` call raises a bare `KeyError`
    instead of a clean, caller-facing validation error.

    This helper avoids the double-formatting entirely: ``network`` is
    resolved to an absolute URL by :func:`resolve_network_url` (a single,
    self-contained substitution), and ``child`` is either resolved through
    `resource_url`'s own URL/path branch (when it is itself a path or
    absolute URL) or validated and appended as a literal path segment
    (when it is a bare id) -- in neither case does a caller-supplied value
    ever become part of a template string handed to a later `.format()`
    call.

    Args:
        network: The network's bare ID, path, or absolute URL.
        child: The nested resource's bare id, path, or absolute URL.
        prefix: The literal path segment between the network and the
            child id, e.g. ``"profiles"`` or ``"insights/devices"``. No
            leading or trailing slash.
        suffix: A literal path segment appended after the child id, e.g.
            ``"/schedules"`` or ``"/devices"``. Empty when the child id is
            the final path segment.
        link: The name of the link in the parent's ``resources`` object
            that, when present, is preferred over the network/child
            template entirely (e.g. ``"schedules"``). Omit when no such
            named link exists for this endpoint.
        parent: The cached parent envelope (full or ``data``), if the
            caller has one. Read only; never mutated.
        version: The API version for the template fallback.

    Returns:
        The absolute URL of the nested resource.

    Raises:
        EeroValidationException: If ``child`` is not a non-empty string,
            or is an absolute URL that is not on the configured API host,
            or uses a scheme other than the API host's scheme. As
            :func:`resolve_network_url` for an invalid ``network``.
    """
    envelope = as_envelope(parent)
    if envelope is not None and link is not None:
        resolved = resolve_link(envelope, link)
        if resolved is not None:
            return resolved

    if isinstance(child, str) and child.startswith(("http://", "https://", "/")):
        return resource_url(child, "{id}" + suffix, version=version)
    if not isinstance(child, str) or not child:
        raise EeroValidationException("child", "must be a non-empty string")

    network_url = resolve_network_url(network, version=version)
    return f"{network_url}/{prefix}/{child}{suffix}"


__all__ = [
    "CADENCE_VALUES",
    "validate_cadence",
    "resolve_network_url",
    "resolve_nested_url",
]
