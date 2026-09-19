"""Resource-link resolution for Eero API response envelopes.

The API returns hypermedia-style links inside response envelopes: a
resource's own ``url`` and, for several resource types, a ``resources``
object whose values are host-relative paths to related resources (for
example a network's ``eeros``, ``devices``, or ``guestnetwork`` links). This
module is the single place in the SDK that turns those links into absolute
URLs.

This unit performs no I/O and never mutates, copies-with-changes, or
otherwise transforms the envelopes it reads -- it only reads fields and
returns strings. The v2.0 raw-response contract (every API method returns
the API's response body unmodified) is preserved by construction: nothing
here is wired into a response path, and nothing here constructs a new
envelope.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from ..const import API_HOST, API_VERSION_DEFAULT, api_endpoint
from ..exceptions import EeroValidationException
from .base import id_from_url

# The hostname of the configured API host, used to validate absolute URLs.
# Derived once from API_HOST rather than hardcoded a second time.
_API_HOST_NAME = urlsplit(API_HOST).hostname or ""

# The scheme required for any absolute URL accepted by this module.
_API_SCHEME = urlsplit(API_HOST).scheme or "https"

Envelope = Dict[str, Any]


def _as_data(parent: Envelope) -> Envelope:
    """Return the ``data`` object of a parent, without mutating it.

    Args:
        parent: Either a full response envelope (``{"meta": ..., "data":
            ...}``) or an already-unwrapped ``data`` object.

    Returns:
        The ``data`` object: ``parent["data"]`` when ``parent`` looks like a
        full envelope (a dict with both ``meta`` and ``data`` keys, where
        ``data`` is itself a dict), otherwise ``parent`` unchanged. This is a
        read-only lookup; the returned object is the same object (or a
        sub-object of it) as was passed in, never a copy.
    """
    if isinstance(parent, dict) and "meta" in parent and isinstance(parent.get("data"), dict):
        return parent["data"]
    return parent


def join_api_path(path: str) -> str:
    """Resolve a host-relative API path to an absolute URL on the API host.

    Args:
        path: A host-relative path as returned by the API, e.g.
            ``"/2.2/networks/network-id-placeholder/eeros"``. Any version
            prefix already present in ``path`` is preserved unchanged.

    Returns:
        The absolute URL formed by joining ``path`` onto :data:`API_HOST`.

    Raises:
        EeroValidationException: If ``path`` is not a non-empty string.
    """
    if not isinstance(path, str) or not path:
        raise EeroValidationException("path", "must be a non-empty string")
    return f"{API_HOST.rstrip('/')}/{path.lstrip('/')}"


def _validate_absolute_url(url: str) -> str:
    """Validate that an absolute URL is on the configured API host.

    Args:
        url: The absolute URL to validate.

    Returns:
        ``url`` unchanged, once validated.

    Raises:
        EeroValidationException: If the URL's scheme is not the API host's
            scheme, or its hostname does not exactly match the API host
            (case-insensitively). This rejects userinfo tricks (e.g.
            ``https://api-user.e2ro.com@evil.example/...``, where the real
            host is ``evil.example``) and suffix tricks (e.g.
            ``https://api-user.e2ro.com.evil.example/...``) because both
            resolve to a ``hostname`` that does not equal the API host.
    """
    parsed = urlsplit(url)
    hostname = parsed.hostname
    host_matches = hostname is not None and hostname.lower() == _API_HOST_NAME.lower()
    scheme_matches = parsed.scheme.lower() == _API_SCHEME.lower()
    if not (host_matches and scheme_matches):
        raise EeroValidationException(
            "url",
            f"must be an absolute {_API_SCHEME} URL on {_API_HOST_NAME}",
        )
    return url


def resolve_link(parent: Envelope, name: str) -> Optional[str]:
    """Resolve a named resource link from a parent envelope to an absolute URL.

    Reads ``parent["resources"][name]`` (or ``parent["data"]["resources"]
    [name]`` when ``parent`` is a full envelope) and joins it onto the API
    host. The parent object is read only -- never mutated, copied-with-
    changes, or otherwise transformed.

    Args:
        parent: Either a full response envelope or its unwrapped ``data``
            object. Detected automatically; the caller does not need to
            unwrap the envelope first.
        name: The link name to resolve, e.g. ``"eeros"``, ``"devices"``,
            ``"guestnetwork"``, ``"reboot"``.

    Returns:
        The absolute URL for the named link, or ``None`` when the parent has
        no ``resources`` object, or no link of that name.
    """
    data = _as_data(parent)
    resources = data.get("resources") if isinstance(data, dict) else None
    if not isinstance(resources, dict):
        return None
    link = resources.get(name)
    if not isinstance(link, str) or not link:
        return None
    return join_api_path(link)


def self_url(parent: Envelope) -> Optional[str]:
    """Resolve a parent envelope's own ``url`` link to an absolute URL.

    Args:
        parent: Either a full response envelope or its unwrapped ``data``
            object.

    Returns:
        The absolute URL for the parent's own resource, or ``None`` when no
        ``url`` field is present.
    """
    data = _as_data(parent)
    url = data.get("url") if isinstance(data, dict) else None
    if not isinstance(url, str) or not url:
        return None
    return join_api_path(url)


def resource_url(
    id_or_url: str,
    template: str,
    *,
    version: str = API_VERSION_DEFAULT,
) -> str:
    """Resolve a bare ID or an API-returned path/URL to an absolute URL.

    This is the single helper for the id-or-url polymorphism domain modules
    encounter throughout the API: a caller-supplied identifier and a link
    value read back from a previous response are both valid inputs to many
    operations, and each must be turned into the same absolute URL.

    Args:
        id_or_url: Either a bare identifier (e.g. ``"network-id-
            placeholder"``), a host-relative path as returned by the API
            (e.g. ``"/2.2/networks/network-id-placeholder"``), or an
            absolute URL on the API host.
        template: A format string with a single ``{id}`` placeholder, used
            to build the URL when ``id_or_url`` is a bare identifier, e.g.
            ``"networks/{id}"``. Interpreted as relative to ``version``.
        version: The API version to substitute into ``template`` when
            ``id_or_url`` is a bare identifier. Defaults to
            :data:`eero.const.API_VERSION_DEFAULT`.

    Returns:
        The absolute URL.

    Raises:
        EeroValidationException: If ``id_or_url`` is not a non-empty string,
            or is an absolute URL that is not on the configured API host, or
            uses a scheme other than the API host's scheme.
    """
    if not isinstance(id_or_url, str) or not id_or_url:
        raise EeroValidationException("id_or_url", "must be a non-empty string")

    if id_or_url.startswith(("http://", "https://")):
        return _validate_absolute_url(id_or_url)

    if id_or_url.startswith("/"):
        return join_api_path(id_or_url)

    path = template.format(id=id_or_url)
    return f"{api_endpoint(version).rstrip('/')}/{path.lstrip('/')}"


__all__ = [
    "Envelope",
    "id_from_url",
    "join_api_path",
    "resolve_link",
    "resource_url",
    "self_url",
]
