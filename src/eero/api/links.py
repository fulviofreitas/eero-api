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

import re
from typing import Any, Mapping, Optional
from urllib.parse import urlsplit

from ..const import API_HOST, API_VERSION_DEFAULT, api_endpoint
from ..exceptions import EeroValidationException
from .base import id_from_url

# The hostname of the configured API host, used to validate absolute URLs.
# Derived once from API_HOST rather than hardcoded a second time.
_API_HOST_NAME = urlsplit(API_HOST).hostname or ""

# The scheme required for any absolute URL accepted by this module.
_API_SCHEME = urlsplit(API_HOST).scheme or "https"

#: A response envelope or its ``data`` object, as any read-only mapping.
#: The helpers below only ever look values up; they never mutate, copy or
#: transform the envelope, so a ``dict``, a ``MappingProxyType`` or any other
#: ``Mapping`` implementation is accepted alike.
Envelope = Mapping[str, Any]

# The single placeholder every URL template carries for the resource id.
_ID_PLACEHOLDER = "{id}"

# A bare identifier is exactly one path segment: no separators, no query or
# fragment delimiters, no percent-escapes and no traversal. Anything else must
# arrive as a path or absolute URL, where the host and scheme are validated.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


def _validate_identifier(value: str) -> str:
    """Validate a bare resource identifier before it is placed in a path.

    Args:
        value: The caller-supplied identifier.

    Returns:
        ``value`` unchanged, once validated.

    Raises:
        EeroValidationException: If the value is empty, contains a path or
            query delimiter, a percent-escape, whitespace, or a ``..``
            sequence, any of which could retarget the request within the API
            host.
    """
    if not isinstance(value, str) or not _IDENTIFIER_RE.match(value) or ".." in value:
        raise EeroValidationException("id", "must be a single path segment identifier")
    return value


def _validate_link_path(link: str) -> str:
    """Validate a link value read from an envelope before joining it.

    Args:
        link: The link value as the API returned it.

    Returns:
        ``link`` unchanged, once validated.

    Raises:
        EeroValidationException: If the value carries a scheme or an
            authority (``//``), which an API-published path never does.
    """
    if not isinstance(link, str) or not link or "://" in link or link.startswith("//"):
        raise EeroValidationException("link", "must be a host-relative API path")
    return link


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
    if isinstance(parent, Mapping) and "meta" in parent and isinstance(parent.get("data"), Mapping):
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
    resources = data.get("resources") if isinstance(data, Mapping) else None
    if not isinstance(resources, Mapping):
        return None
    link = resources.get(name)
    if not isinstance(link, str) or not link:
        return None
    return join_api_path(_validate_link_path(link))


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
    url = data.get("url") if isinstance(data, Mapping) else None
    if not isinstance(url, str) or not url:
        return None
    return join_api_path(_validate_link_path(url))


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
            uses a scheme other than the API host's scheme, or ``template``
            does not contain exactly one ``{id}`` placeholder.

    When ``template`` continues after the placeholder (for example
    ``"networks/{id}/settings"``), that suffix names a sub-resource of the
    identified resource. A bare identifier is substituted into the whole
    template; a path or absolute URL is taken to identify the parent
    resource itself, so the suffix is appended to it.
    """
    if not isinstance(id_or_url, str) or not id_or_url:
        raise EeroValidationException("id_or_url", "must be a non-empty string")
    if template.count(_ID_PLACEHOLDER) != 1:
        raise EeroValidationException("template", "must contain exactly one {id} placeholder")

    suffix = template.split(_ID_PLACEHOLDER, 1)[1]

    if id_or_url.lower().startswith(("http://", "https://")):
        return _validate_absolute_url(id_or_url).rstrip("/") + suffix

    if id_or_url.startswith("/"):
        return join_api_path(_validate_link_path(id_or_url)).rstrip("/") + suffix

    path = template.format(id=_validate_identifier(id_or_url))
    return f"{api_endpoint(version).rstrip('/')}/{path.lstrip('/')}"


def child_url(base_url: str, child_id: str) -> str:
    """Append a validated child identifier to an already-resolved URL.

    Used where a collection URL is known (for example a resolved link) and a
    single member is addressed by id, so the member id never reaches the
    request line without validation.

    Args:
        base_url: The absolute, already-validated collection URL.
        child_id: A bare identifier for the member.

    Returns:
        The member URL.

    Raises:
        EeroValidationException: If ``child_id`` is not a single path
            segment identifier (see :func:`resource_url`).
    """
    return f"{base_url.rstrip('/')}/{_validate_identifier(child_id)}"


def sub_resource_url(
    id_or_url: str,
    template: str,
    *,
    link: str,
    parent: Optional[Envelope] = None,
    version: str = API_VERSION_DEFAULT,
) -> str:
    """Resolve a sub-resource URL, preferring the parent's own link.

    Domain methods call this once per request: when the caller supplies the
    parent envelope (for example a cached network), the link the API
    published for the sub-resource is used, including whatever version
    prefix the API put on it; otherwise the URL is built from
    ``id_or_url`` and ``template`` exactly as :func:`resource_url` does.

    Args:
        id_or_url: The parent's bare identifier, path, or absolute URL.
        template: A format string with one ``{id}`` placeholder followed by
            the sub-resource suffix, e.g. ``"networks/{id}/settings"``.
        link: The name of the link in the parent's ``resources`` object,
            e.g. ``"settings"``.
        parent: The parent envelope (full or ``data``), if the caller has
            one. Read only; never mutated.
        version: The API version for the template fallback.

    Returns:
        The absolute URL of the sub-resource.

    Raises:
        EeroValidationException: As :func:`resource_url`.
    """
    if parent is not None:
        resolved = resolve_link(parent, link)
        if resolved is not None:
            return resolved
    return resource_url(id_or_url, template, version=version)


__all__ = [
    "Envelope",
    "child_url",
    "id_from_url",
    "join_api_path",
    "resolve_link",
    "resource_url",
    "self_url",
    "sub_resource_url",
]
