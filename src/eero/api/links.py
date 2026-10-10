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
from typing import Any, Mapping, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

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

# One identifier-bearing path segment: it starts with an alphanumeric, so a
# literal ``.`` or ``..`` segment can never match, and it holds no separators,
# query or fragment delimiters, or percent-escapes.
_SEGMENT = r"[A-Za-z0-9][A-Za-z0-9._:-]*"

# A bare identifier is exactly one such segment. Anything else must arrive as
# a path or absolute URL, where the host and scheme are validated. ``\Z``
# rather than ``$``, which would also accept a trailing newline.
_IDENTIFIER_RE = re.compile(rf"^{_SEGMENT}\Z")

# Whitespace and control characters. Parsers and HTTP clients silently strip
# or normalise some of these (tab, carriage return and newline among them), so
# a value carrying one can reach the wire as a different path than the one
# that was validated.
_CONTROL_CHARS_RE = re.compile(r"[\s\x00-\x1f\x7f-\x9f]")

# A percent-encoded dot (``%2e``), which a server may decode into a dot
# segment after the path has been validated.
_ENCODED_DOT_RE = re.compile(r"%2e", re.IGNORECASE)

# A path segment that moves up or stays in place instead of naming a resource.
_DOT_SEGMENTS = frozenset({".", ".."})


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


def validate_identifier(value: str) -> str:
    """Validate a bare resource identifier before it is placed in a path.

    Public alias of :func:`_validate_identifier`, for callers outside this
    module (e.g. ``eero.api.data_usage``) that need to validate a bare id as
    a single path segment without routing it through :func:`resource_url`'s
    discarded-URL indirection.

    Args:
        value: The caller-supplied identifier.

    Returns:
        ``value`` unchanged, once validated.

    Raises:
        EeroValidationException: As :func:`_validate_identifier`.
    """
    return _validate_identifier(value)


def _require_plain_path(value: str, field: str) -> str:
    """Reject a path or URL that could address a different resource than it names.

    This is the one rule for the shape of any path or URL the SDK is about to
    place on a request line, whether an API published it or a caller supplied
    it: it must be a plain path, with no query, fragment, dot segment or
    control character that a parser or the server could resolve differently.

    Args:
        value: The host-relative path or absolute URL to check.
        field: The parameter name to report in the validation error.

    Returns:
        ``value`` unchanged, once checked.

    Raises:
        EeroValidationException: If ``value`` contains whitespace or a control
            character, a query (``?``) or fragment (``#``) delimiter, a
            ``.`` or ``..`` path segment, or a percent-encoded dot.

    Dots inside a segment (``a..b``, ``v1.2``) are allowed; only a whole ``.``
    or ``..`` segment is rejected. A bare identifier is stricter and also
    rejects ``..`` anywhere in it (see :func:`_validate_identifier`).
    """
    if _CONTROL_CHARS_RE.search(value):
        raise EeroValidationException(field, "must not contain whitespace or control characters")
    if "?" in value or "#" in value:
        raise EeroValidationException(field, "must not carry a query or fragment")
    if _ENCODED_DOT_RE.search(value) or not _DOT_SEGMENTS.isdisjoint(value.split("/")):
        raise EeroValidationException(field, "must not contain dot segments")
    return value


def _validate_link_path(link: str, field: str = "link") -> str:
    """Validate a host-relative path before joining it onto the API host.

    Args:
        link: The path, as the API returned it in an envelope or as a caller
            supplied it.
        field: The parameter name to report in the validation error. Defaults
            to ``"link"`` for values read from an envelope; callers validating
            their own argument pass its name.

    Returns:
        ``link`` unchanged, once validated.

    Raises:
        EeroValidationException: If the value carries a scheme or an
            authority (``//``), which an API-published path never does, or
            fails :func:`_require_plain_path`. The path is deliberately not
            confined to a resource family: a published link may name any
            resource, on whatever version the API serves it.
    """
    if not isinstance(link, str) or not link or "://" in link or link.startswith("//"):
        raise EeroValidationException(field, "must be a host-relative API path")
    return _require_plain_path(link, field)


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
            resolve to a ``hostname`` that does not equal the API host. Also
            raised if the URL fails :func:`_require_plain_path`.
    """
    _require_plain_path(url, "url")
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


def require_family_path(url: str, family: str, suffix: str = "", *, field: str) -> Tuple[str, ...]:
    """Require a URL's path to name exactly one resource of an expected family.

    The path must be ``/<version>/<family><suffix>`` where every ``{id}`` in
    ``family`` stands for a single path segment, and nothing else: no other
    resource family, no extra or missing components, no query or fragment, no
    dot segment, no percent-escape and no whitespace or control character.
    The host is not examined; callers validate it first.

    Args:
        url: The absolute URL, or host-relative path, to check.
        family: The expected path after the version segment, with a ``{id}``
            placeholder for each identifier, e.g. ``"eeros/{id}"`` or
            ``"networks/{id}/profiles/{id}"``.
        suffix: The literal path that must follow the last identifier, e.g.
            ``"/schedules"``. Empty when the identifier is the final segment.
        field: The parameter name to report in the validation error.

    Returns:
        The identifiers the path carries, in the order of the ``{id}``
        placeholders.

    Raises:
        EeroValidationException: If the path does not have exactly that shape.
    """
    _require_plain_path(url, field)
    body = f"({_SEGMENT})".join(re.escape(part) for part in family.split(_ID_PLACEHOLDER))
    pattern = rf"/[0-9]+\.[0-9]+/{body}{re.escape(suffix)}/?"
    match = re.fullmatch(pattern, urlsplit(url).path)
    if match is None:
        raise EeroValidationException(field, f"must be a path under {family} on the API host")
    return match.groups()


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
            does not contain exactly one ``{id}`` placeholder, or a path or
            URL fails :func:`_require_plain_path` or, when ``template`` names
            a resource family, does not identify exactly one resource of it.

    When ``template`` continues after the placeholder (for example
    ``"networks/{id}/settings"``), that suffix names a sub-resource of the
    identified resource. A bare identifier is substituted into the whole
    template; a path or absolute URL is taken to identify the parent
    resource itself, so the suffix is appended to it.

    The text before the placeholder names the resource family (``networks``
    for ``"networks/{id}/settings"``, ``entitlements/networks`` for
    ``"entitlements/networks/{id}/features"``). A caller-supplied path or
    absolute URL must be exactly ``/<version>/<family>/<id>``, so an
    identifier of another family cannot be redirected to this template's
    endpoint. The version segment is the caller's own and is preserved. A
    template with nothing before the placeholder names no family, and its
    path or URL is checked only for host and shape.
    """
    if not isinstance(id_or_url, str) or not id_or_url:
        raise EeroValidationException("id_or_url", "must be a non-empty string")
    if template.count(_ID_PLACEHOLDER) != 1:
        raise EeroValidationException("template", "must contain exactly one {id} placeholder")

    prefix, suffix = template.split(_ID_PLACEHOLDER, 1)
    family = prefix.strip("/")

    supplied: Optional[str] = None
    if id_or_url.lower().startswith(("http://", "https://")):
        supplied = _validate_absolute_url(id_or_url)
    elif id_or_url.startswith("/"):
        supplied = join_api_path(_validate_link_path(id_or_url, "id_or_url"))

    if supplied is not None:
        if family:
            require_family_path(supplied, f"{family}/{_ID_PLACEHOLDER}", field="id_or_url")
        return supplied.rstrip("/") + suffix

    path = template.format(id=_validate_identifier(id_or_url))
    return f"{api_endpoint(version).rstrip('/')}/{path.lstrip('/')}"


#: Matches the API-version segment of a URL path, e.g. the ``2.3`` in
#: ``/2.3/networks/123/support``.
_VERSION_SEGMENT_RE = re.compile(r"[0-9]+\.[0-9]+")


def rewrite_version(url: str, version: str) -> str:
    """Rewrite the API-version segment of an already-resolved absolute URL.

    Used where a domain method must pin a specific API version regardless
    of what version segment a parent envelope's published link named,
    because the response shape differs by version -- see
    ``eero.api.support.SupportAPI.get_support``, whose ``support`` link is
    served on 2.3 under a current ``User-Agent`` but returns a different
    shape there than on 2.2 (issue #135). ``eero.api.forwards.ForwardsAPI.
    get_forwards`` and ``eero.api.routing.RoutingAPI.get_routing`` pin to
    2.2 the same way, for safety, even though their known shape is
    unchanged across versions.

    The URL is parsed, not pattern-matched as a string, and only the first
    path segment is replaced. The scheme is therefore compared
    case-insensitively, as URL parsers do, and a control character inside
    the path (which an HTTP client may strip on the wire) cannot hide the
    version segment from the rewrite.

    Args:
        url: An absolute URL already resolved onto the API host, carrying a
            leading version segment (e.g. ``.../2.3/networks/...``).
        version: The version segment to substitute, e.g. ``"2.2"``.

    Returns:
        ``url`` with its version segment replaced by ``version``, or ``url``
        unchanged if it is not an ``http(s)`` URL with a host or carries no
        leading version segment.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return url
    segments = parts.path.split("/", 2)
    if len(segments) != 3 or segments[0] or not _VERSION_SEGMENT_RE.fullmatch(segments[1]):
        return url
    segments[1] = version
    return urlunsplit(parts._replace(path="/".join(segments)))


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
    "require_family_path",
    "resolve_link",
    "resource_url",
    "rewrite_version",
    "self_url",
    "sub_resource_url",
    "validate_identifier",
]
