"""Tests for resource-link resolution in eero.api.links.

Tests cover:
- resolve_link: link present, link absent, envelope vs data-object input,
  version prefix preserved from the link, no mutation of the parent object
- self_url: envelope vs data-object input, absent url
- resource_url: bare ID, host-relative path, absolute API-host URL, foreign
  host rejected, non-https scheme rejected, userinfo/suffix host tricks
  rejected
- join_api_path: basic joining, validation of empty input
- Parent envelopes for network / eero / guest network / profile / device
  shapes, matching the fields the API returns for each
- Version-per-family constants in eero.const derive correctly
- The transport accepts and credentials an absolute URL produced by the
  resolver (mocked at the aiohttp session boundary; no live requests)
"""

import copy
from typing import Any, Dict

import pytest

from eero.api.base import BaseAPI
from eero.api.links import (
    join_api_path,
    resolve_link,
    resource_url,
    self_url,
    sub_resource_url,
)
from eero.const import (
    API_ENDPOINT,
    API_HOST,
    API_VERSION_DEFAULT,
    API_VERSION_DEVICE_WRITES,
    API_VERSION_MULTISTATICIP,
    API_VERSION_SECONDARY_WAN,
    DEVICE_UPDATE_ENDPOINT,
    api_endpoint,
)
from eero.exceptions import EeroValidationException

from .conftest import api_success_response, create_mock_response

# ========================== Fixture Envelopes ==========================


@pytest.fixture
def network_data() -> Dict[str, Any]:
    """A network ``data`` object shaped like the API response."""
    return {
        "url": "/2.2/networks/network-id-placeholder",
        "name": "Placeholder Network",
        "resources": {
            "settings": "/2.2/networks/network-id-placeholder/settings",
            "devices": "/2.2/networks/network-id-placeholder/devices",
            "eeros": "/2.2/networks/network-id-placeholder/eeros",
            "profiles": "/2.2/networks/network-id-placeholder/profiles",
            "guestnetwork": "/2.2/networks/network-id-placeholder/guestnetwork",
            "reboot": "/2.2/networks/network-id-placeholder/reboot",
            "forwards": "/2.3/networks/network-id-placeholder/forwards",
            "support": "/2.3/networks/network-id-placeholder/support",
            "routing": "/2.3/networks/network-id-placeholder/routing",
        },
    }


@pytest.fixture
def network_envelope(network_data: Dict[str, Any]) -> Dict[str, Any]:
    """A full network response envelope wrapping ``network_data``."""
    return api_success_response(network_data)


@pytest.fixture
def eero_data() -> Dict[str, Any]:
    """An eero ``data`` object shaped like the API response."""
    return {
        "url": "/2.2/eeros/eero-id-placeholder",
        "resources": {
            "connections": "/2.2/eeros/eero-id-placeholder/connections",
            "led_action": "/2.2/eeros/eero-id-placeholder/led",
            "reboot": "/2.2/eeros/eero-id-placeholder/reboot",
        },
    }


@pytest.fixture
def guest_network_data() -> Dict[str, Any]:
    """A guest-network ``data`` object shaped like the API response."""
    return {
        "resources": {
            "password": "/2.2/networks/network-id-placeholder/guestnetwork/password",
        },
    }


@pytest.fixture
def profile_data() -> Dict[str, Any]:
    """A profile ``data`` object shaped like the API response."""
    return {
        "url": "/2.2/networks/network-id-placeholder/profiles/profile-id-placeholder",
        "resources": {
            "schedules": (
                "/2.2/networks/network-id-placeholder/profiles/" "profile-id-placeholder/schedules"
            ),
        },
    }


@pytest.fixture
def device_data() -> Dict[str, Any]:
    """A device ``data`` object shaped like the API response (no resources)."""
    return {
        "url": "/2.2/networks/network-id-placeholder/devices/deviceidplaceholder",
    }


# ========================== resolve_link Tests ==========================


class TestResolveLink:
    """Tests for resolve_link with various parent shapes."""

    def test_link_present_returns_absolute_url(self, network_data):
        """A present link resolves to an absolute URL on the API host."""
        assert resolve_link(network_data, "eeros") == (
            f"{API_HOST}/2.2/networks/network-id-placeholder/eeros"
        )

    def test_link_absent_returns_none(self, network_data):
        """A link name not present in resources returns None."""
        assert resolve_link(network_data, "nonexistent") is None

    def test_no_resources_object_returns_none(self, device_data):
        """A parent with no resources object returns None for any link."""
        assert resolve_link(device_data, "anything") is None

    def test_accepts_full_envelope(self, network_envelope):
        """A full {"meta":..., "data":...} envelope is auto-unwrapped."""
        assert resolve_link(network_envelope, "devices") == (
            f"{API_HOST}/2.2/networks/network-id-placeholder/devices"
        )

    def test_accepts_data_object_directly(self, network_data):
        """An already-unwrapped data object works identically to an envelope."""
        assert resolve_link(network_data, "devices") == (
            f"{API_HOST}/2.2/networks/network-id-placeholder/devices"
        )

    @pytest.mark.parametrize(
        "link_name,expected_suffix",
        [
            ("settings", "/2.2/networks/network-id-placeholder/settings"),
            ("devices", "/2.2/networks/network-id-placeholder/devices"),
            ("eeros", "/2.2/networks/network-id-placeholder/eeros"),
            ("profiles", "/2.2/networks/network-id-placeholder/profiles"),
            ("guestnetwork", "/2.2/networks/network-id-placeholder/guestnetwork"),
            ("reboot", "/2.2/networks/network-id-placeholder/reboot"),
        ],
    )
    def test_network_links_default_version(self, network_data, link_name, expected_suffix):
        """Network links on the default version resolve with that prefix intact."""
        assert resolve_link(network_data, link_name) == f"{API_HOST}{expected_suffix}"

    @pytest.mark.parametrize(
        "link_name",
        ["forwards", "support", "routing"],
    )
    def test_version_prefix_preserved_for_23_families(self, network_data, link_name):
        """Links served under 2.3 keep that prefix rather than being rewritten."""
        resolved = resolve_link(network_data, link_name)
        assert resolved is not None
        assert resolved.startswith(f"{API_HOST}/2.3/")

    def test_eero_links(self, eero_data):
        """Eero resource links resolve, including the led_action path."""
        assert resolve_link(eero_data, "led_action") == (
            f"{API_HOST}/2.2/eeros/eero-id-placeholder/led"
        )
        assert resolve_link(eero_data, "reboot") == (
            f"{API_HOST}/2.2/eeros/eero-id-placeholder/reboot"
        )

    def test_guest_network_password_link(self, guest_network_data):
        """Guest-network password link resolves."""
        assert resolve_link(guest_network_data, "password") == (
            f"{API_HOST}/2.2/networks/network-id-placeholder/guestnetwork/password"
        )

    def test_profile_schedules_link(self, profile_data):
        """Profile schedules link resolves."""
        assert resolve_link(profile_data, "schedules") == (
            f"{API_HOST}/2.2/networks/network-id-placeholder/profiles/"
            f"profile-id-placeholder/schedules"
        )

    def test_does_not_mutate_parent(self, network_envelope):
        """resolve_link never mutates or copies-with-changes the parent."""
        before = copy.deepcopy(network_envelope)
        resolve_link(network_envelope, "eeros")
        resolve_link(network_envelope, "nonexistent")
        assert network_envelope == before


# ========================== self_url Tests ==========================


class TestSelfUrl:
    """Tests for self_url with various parent shapes."""

    def test_self_url_from_data_object(self, network_data):
        """self_url resolves the parent's own url field."""
        assert self_url(network_data) == f"{API_HOST}/2.2/networks/network-id-placeholder"

    def test_self_url_from_envelope(self, network_envelope):
        """self_url auto-unwraps a full envelope."""
        assert self_url(network_envelope) == f"{API_HOST}/2.2/networks/network-id-placeholder"

    def test_self_url_eero(self, eero_data):
        """self_url resolves an eero's own url."""
        assert self_url(eero_data) == f"{API_HOST}/2.2/eeros/eero-id-placeholder"

    def test_self_url_profile(self, profile_data):
        """self_url resolves a profile's own url."""
        assert self_url(profile_data) == (
            f"{API_HOST}/2.2/networks/network-id-placeholder/profiles/profile-id-placeholder"
        )

    def test_self_url_device(self, device_data):
        """self_url resolves a device's own url."""
        assert self_url(device_data) == (
            f"{API_HOST}/2.2/networks/network-id-placeholder/devices/deviceidplaceholder"
        )

    def test_self_url_absent_returns_none(self, guest_network_data):
        """A parent with no url field returns None."""
        assert self_url(guest_network_data) is None

    def test_does_not_mutate_parent(self, network_envelope):
        """self_url never mutates or copies-with-changes the parent."""
        before = copy.deepcopy(network_envelope)
        self_url(network_envelope)
        assert network_envelope == before


# ========================== join_api_path Tests ==========================


class TestJoinApiPath:
    """Tests for join_api_path."""

    def test_joins_leading_slash_path(self):
        """A leading-slash path joins cleanly onto the API host."""
        assert join_api_path("/2.2/networks/network-id-placeholder") == (
            f"{API_HOST}/2.2/networks/network-id-placeholder"
        )

    def test_joins_bare_path(self):
        """A path without a leading slash also joins cleanly."""
        assert join_api_path("2.2/networks/network-id-placeholder") == (
            f"{API_HOST}/2.2/networks/network-id-placeholder"
        )

    def test_preserves_23_version_prefix(self):
        """A 2.3-prefixed path keeps that prefix, not rewritten to default."""
        assert join_api_path("/2.3/networks/network-id-placeholder/forwards") == (
            f"{API_HOST}/2.3/networks/network-id-placeholder/forwards"
        )

    def test_empty_path_raises(self):
        """An empty path raises EeroValidationException."""
        with pytest.raises(EeroValidationException):
            join_api_path("")

    def test_non_string_raises(self):
        """A non-string path raises EeroValidationException."""
        with pytest.raises(EeroValidationException):
            join_api_path(None)  # type: ignore[arg-type]


# ========================== resource_url Tests ==========================


class TestResourceUrl:
    """Tests for resource_url's ID-or-URL polymorphism."""

    def test_bare_id_uses_template_and_default_version(self):
        """A bare ID is substituted into the template at the default version."""
        assert resource_url("network-id-placeholder", "networks/{id}") == (
            f"{API_ENDPOINT}/networks/network-id-placeholder"
        )

    def test_bare_id_uses_explicit_version(self):
        """A bare ID with an explicit version resolves under that version."""
        assert resource_url(
            "device-id-placeholder",
            "networks/network-id-placeholder/devices/{id}",
            version=API_VERSION_DEVICE_WRITES,
        ) == (
            f"{DEVICE_UPDATE_ENDPOINT}/networks/network-id-placeholder/devices/device-id-placeholder"
        )

    def test_host_relative_path_joins_onto_api_host(self):
        """A host-relative path (as returned by the API) is joined as-is."""
        assert (
            resource_url("/2.2/networks/network-id-placeholder", "networks/{id}")
            == f"{API_HOST}/2.2/networks/network-id-placeholder"
        )

    def test_host_relative_path_preserves_23_prefix(self):
        """A 2.3-prefixed path is preserved, not rewritten to the template's version."""
        assert (
            resource_url("/2.3/networks/network-id-placeholder/forwards", "networks/{id}")
            == f"{API_HOST}/2.3/networks/network-id-placeholder/forwards"
        )

    def test_absolute_api_host_url_is_accepted(self):
        """An absolute URL already on the API host passes through unchanged."""
        url = f"{API_HOST}/2.2/networks/network-id-placeholder"
        assert resource_url(url, "networks/{id}") == url

    def test_foreign_host_rejected(self):
        """An absolute URL on a different host is rejected."""
        with pytest.raises(EeroValidationException):
            resource_url(
                "https://evil.example/2.2/networks/network-id-placeholder", "networks/{id}"
            )

    def test_http_scheme_rejected(self):
        """A plain-http downgrade of the API host is rejected."""
        with pytest.raises(EeroValidationException):
            resource_url(
                "http://api-user.e2ro.com/2.2/networks/network-id-placeholder",
                "networks/{id}",
            )

    def test_userinfo_trick_rejected(self):
        """A userinfo prefix that disguises a foreign host is rejected."""
        with pytest.raises(EeroValidationException):
            resource_url(
                "https://api-user.e2ro.com@evil.example/2.2/networks/network-id-placeholder",
                "networks/{id}",
            )

    def test_suffix_trick_rejected(self):
        """A hostname-suffix trick that disguises a foreign host is rejected."""
        with pytest.raises(EeroValidationException):
            resource_url(
                "https://api-user.e2ro.com.evil.example/2.2/networks/network-id-placeholder",
                "networks/{id}",
            )

    def test_empty_id_or_url_raises(self):
        """An empty id_or_url raises EeroValidationException."""
        with pytest.raises(EeroValidationException):
            resource_url("", "networks/{id}")

    def test_non_string_id_or_url_raises(self):
        """A non-string id_or_url raises EeroValidationException."""
        with pytest.raises(EeroValidationException):
            resource_url(None, "networks/{id}")  # type: ignore[arg-type]


# ========================== Constants Tests ==========================


class TestVersionConstants:
    """Tests that version-per-family constants in eero.const derive correctly."""

    def test_api_endpoint_helper(self):
        """api_endpoint joins the API host and a version segment."""
        assert api_endpoint("2.2") == f"{API_HOST}/2.2"
        assert api_endpoint("2.3") == f"{API_HOST}/2.3"

    def test_api_endpoint_matches_default(self):
        """API_ENDPOINT is derived from api_endpoint(API_VERSION_DEFAULT)."""
        assert API_ENDPOINT == api_endpoint(API_VERSION_DEFAULT)
        assert API_VERSION_DEFAULT == "2.2"

    def test_device_update_endpoint_matches_device_writes_version(self):
        """DEVICE_UPDATE_ENDPOINT is derived from API_VERSION_DEVICE_WRITES."""
        assert DEVICE_UPDATE_ENDPOINT == api_endpoint(API_VERSION_DEVICE_WRITES)
        assert API_VERSION_DEVICE_WRITES == "2.3"

    def test_multistaticip_and_secondary_wan_versions(self):
        """The 2.3-only families share the same version constant value."""
        assert API_VERSION_MULTISTATICIP == "2.3"
        assert API_VERSION_SECONDARY_WAN == "2.3"


# ========================== Sub-resource Resolution Tests ==========================


class TestResourceUrlSuffix:
    """A template suffix after the id names a sub-resource of the parent."""

    @pytest.mark.parametrize(
        ("id_or_url", "expected"),
        [
            (
                "network-id-placeholder",
                f"{API_ENDPOINT}/networks/network-id-placeholder/settings",
            ),
            (
                "/2.3/networks/network-id-placeholder",
                f"{API_HOST}/2.3/networks/network-id-placeholder/settings",
            ),
            (
                f"{API_HOST}/2.2/networks/network-id-placeholder/",
                f"{API_HOST}/2.2/networks/network-id-placeholder/settings",
            ),
        ],
        ids=["bare-id", "path-keeps-its-version", "absolute-url-trailing-slash"],
    )
    def test_suffix_is_appended_to_parent(self, id_or_url: str, expected: str) -> None:
        """The suffix is applied whether the parent is an id, a path or a URL."""
        assert resource_url(id_or_url, "networks/{id}/settings") == expected

    @pytest.mark.parametrize("template", ["networks", "networks/{id}/{id}"])
    def test_template_must_contain_one_placeholder(self, template: str) -> None:
        """Templates without exactly one placeholder are rejected."""
        with pytest.raises(EeroValidationException):
            resource_url("network-id-placeholder", template)


class TestSubResourceUrl:
    """The parent's published link wins; the template is the fallback."""

    def test_link_from_parent_is_preferred(self, network_data: Dict[str, Any]) -> None:
        """A link present on the parent is used, keeping its own version prefix."""
        url = sub_resource_url(
            "network-id-placeholder",
            "networks/{id}/forwards",
            link="forwards",
            parent=network_data,
        )

        assert url == f"{API_HOST}/2.3/networks/network-id-placeholder/forwards"

    @pytest.mark.parametrize("parent", [None, {"url": "/2.2/networks/x", "resources": {}}])
    def test_template_fallback_without_link(self, parent: Any) -> None:
        """Without a usable link the template on the default version is used."""
        url = sub_resource_url(
            "network-id-placeholder", "networks/{id}/forwards", link="forwards", parent=parent
        )

        assert url == f"{API_ENDPOINT}/networks/network-id-placeholder/forwards"

    def test_parent_is_not_mutated(self, network_data: Dict[str, Any]) -> None:
        """Resolution reads the parent and leaves it byte-identical."""
        before = copy.deepcopy(network_data)

        sub_resource_url(
            "network-id-placeholder", "networks/{id}/eeros", link="eeros", parent=network_data
        )

        assert network_data == before


# ========================== Transport Integration Test ==========================


class TestResolvedLinkGoesThroughTransport:
    """An absolute URL produced by the resolver is accepted by the transport.

    No live requests are made -- the aiohttp session is mocked at the
    request boundary.
    """

    @pytest.mark.asyncio
    async def test_credential_attached_for_resolved_link(self, mock_session, network_data):
        """A resolver-produced absolute URL on the API host gets the credential."""
        resolved = resolve_link(network_data, "eeros")
        assert resolved is not None

        mock_session.request.return_value = create_mock_response(200, api_success_response([]))

        # BaseAPI is exercised directly (rather than AuthenticatedAPI) since
        # this test targets only the transport's URL/credential handling,
        # not the auth-layer wiring covered by AuthenticatedAPI's own tests.
        api = BaseAPI(session=mock_session, base_url=API_ENDPOINT)

        await api.get(resolved, auth_token="token-placeholder")

        _, call_kwargs = mock_session.request.call_args
        assert mock_session.request.call_args[0][1] == resolved
        assert call_kwargs["headers"]["X-User-Token"] == "token-placeholder"
