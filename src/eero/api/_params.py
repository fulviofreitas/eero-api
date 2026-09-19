"""Shared query-parameter validation and identifier resolution helpers.

Small, dependency-free helpers shared by more than one domain module in
this SDK, so that validation rules and identifier-resolution rules have
exactly one implementation each rather than one copy per module.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..const import API_VERSION_DEFAULT
from ..exceptions import EeroValidationException
from ._writes import as_envelope
from .links import resource_url, self_url

#: Valid values for a `cadence` query/body parameter, shared by every family
#: that buckets a time series into "daily" or "hourly" points (data usage,
#: insights, data-usage report settings).
CADENCE_VALUES = ("daily", "hourly")


def validate_cadence(value: str) -> str:
    """Validate a `cadence` value against the API's two accepted buckets.

    Args:
        value: Candidate cadence value. Callers for whom cadence is
            optional must not call this with ``None``; omit the parameter
            entirely instead.

    Returns:
        ``value`` unchanged, once validated.

    Raises:
        EeroValidationException: If ``value`` is not ``"daily"`` or
            ``"hourly"``.
    """
    if value not in CADENCE_VALUES:
        raise EeroValidationException(
            "cadence",
            f"must be one of {CADENCE_VALUES}, got {value!r}",
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


__all__ = ["CADENCE_VALUES", "validate_cadence", "resolve_network_url"]
