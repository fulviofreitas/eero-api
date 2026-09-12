"""Tests for DnsAPI module.

Tests cover:
- Getting DNS settings (raw response)
- Setting DNS caching via the nested `dns.caching` field
- Custom DNS servers per address family, and mixed-family input
- Per-family and whole-network clearing (mode -> automatic)
- DNS mode switching and mode validation
- IP-literal and address-family validation, and the per-family cap

Wire format under test (live-verified 2026-09-12, API 2.2 — see issue #123):

    IPv4:  {"dns":  {"mode": ..., "custom": {"ips": [...]}}}
    IPv6:  {"ipv6": {"name_servers": {"mode": ..., "custom": [...]}}}

The shapes are asymmetric on purpose; the helpers below are the single place
that knowledge lives, so a confirmed upstream change means editing one function.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.dns import (
    DNS_MODE_AUTOMATIC,
    DNS_MODE_CUSTOM,
    MAX_DNS_SERVERS_PER_FAMILY,
    DnsAPI,
)
from eero.exceptions import EeroAuthenticationException, EeroValidationException

from .conftest import api_success_response, create_mock_response

# ========================== Payload shape helpers ==========================


def ipv4_payload(ips, mode=DNS_MODE_CUSTOM):
    """The verified IPv4 custom-DNS payload fragment."""
    fragment = {"mode": mode}
    if ips is not None:
        fragment["custom"] = {"ips": ips}
    return {"dns": fragment}


def ipv6_payload(ips, mode=DNS_MODE_CUSTOM):
    """The verified IPv6 custom-DNS payload fragment.

    Note the asymmetry with `ipv4_payload`: the list sits directly under
    `custom`, not nested under an `ips` key.
    """
    fragment = {"mode": mode}
    if ips is not None:
        fragment["custom"] = ips
    return {"ipv6": {"name_servers": fragment}}


def sent_payload(mock_session):
    """The JSON body of the most recent request."""
    return mock_session.request.call_args.kwargs["json"]


def sent_url(mock_session):
    """The URL of the most recent request."""
    return mock_session.request.call_args[0][1]


@pytest.fixture
def dns_api(mock_session):
    """Create a DnsAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return DnsAPI(auth_api)


@pytest.fixture
def unauthenticated_dns_api(mock_session):
    """Create a DnsAPI whose auth token lookup returns nothing."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value=None)
    return DnsAPI(auth_api)


# ========================== Init ==========================


class TestDnsAPIInit:
    """Tests for DnsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = DnsAPI(auth_api)

        assert api._auth_api is auth_api


# ========================== Reads ==========================


class TestDnsAPIGetSettings:
    """Tests for get_dns_settings method."""

    @pytest.mark.asyncio
    async def test_returns_raw_response(self, dns_api, mock_session):
        """Test the full network payload is returned unmodified."""
        network_data = {
            "dns": {
                "mode": DNS_MODE_CUSTOM,
                "custom": {"ips": ["1.1.1.1", "1.0.0.1"]},
                "parent": {"ips": ["192.168.1.254"]},
                "caching": False,
            },
            "ipv6": {
                "name_servers": {
                    "mode": DNS_MODE_CUSTOM,
                    "custom": ["2606:4700:4700:0:0:0:0:1111"],
                }
            },
        }
        mock_session.request.return_value = create_mock_response(
            json_data=api_success_response(network_data)
        )

        result = await dns_api.get_dns_settings("net123")

        assert result["data"] == network_data
        assert result["data"]["dns"]["custom"]["ips"] == ["1.1.1.1", "1.0.0.1"]
        assert result["data"]["ipv6"]["name_servers"]["mode"] == DNS_MODE_CUSTOM

    @pytest.mark.asyncio
    async def test_not_authenticated(self, unauthenticated_dns_api, mock_session):
        """Test unauthenticated reads raise without touching the network."""
        with pytest.raises(EeroAuthenticationException):
            await unauthenticated_dns_api.get_dns_settings("net123")

        mock_session.request.assert_not_called()


# ========================== DNS caching ==========================


class TestDnsCaching:
    """Tests for set_dns_caching."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("enabled", [True, False])
    async def test_sends_nested_caching_field(self, dns_api, mock_session, enabled):
        """Test caching is written to dns.caching, not the dead dns_caching field."""
        await dns_api.set_dns_caching("net123", enabled)

        assert sent_payload(mock_session) == {"dns": {"caching": enabled}}

    @pytest.mark.asyncio
    async def test_does_not_send_legacy_field(self, dns_api, mock_session):
        """Regression: `dns_caching` is silently ignored by the API (issue #123)."""
        await dns_api.set_dns_caching("net123", True)

        assert "dns_caching" not in sent_payload(mock_session)

    @pytest.mark.asyncio
    async def test_targets_settings_endpoint(self, dns_api, mock_session):
        """Test the write goes to the settings sub-resource."""
        await dns_api.set_dns_caching("net123", True)

        assert "networks/net123/settings" in sent_url(mock_session)

    @pytest.mark.asyncio
    async def test_not_authenticated(self, unauthenticated_dns_api, mock_session):
        """Test unauthenticated writes raise without touching the network."""
        with pytest.raises(EeroAuthenticationException):
            await unauthenticated_dns_api.set_dns_caching("net123", True)

        mock_session.request.assert_not_called()


# ========================== Custom DNS — mixed input ==========================


class TestSetCustomDns:
    """Tests for set_custom_dns with mixed-family input."""

    @pytest.mark.asyncio
    async def test_ipv4_only(self, dns_api, mock_session):
        """Test an IPv4-only list writes only the dns object."""
        await dns_api.set_custom_dns("net123", ["1.1.1.1", "1.0.0.1"])

        payload = sent_payload(mock_session)
        assert payload == ipv4_payload(["1.1.1.1", "1.0.0.1"])
        assert "ipv6" not in payload

    @pytest.mark.asyncio
    async def test_ipv6_only(self, dns_api, mock_session):
        """Test an IPv6-only list writes only the ipv6 object."""
        await dns_api.set_custom_dns("net123", ["2606:4700:4700::1111"])

        payload = sent_payload(mock_session)
        assert payload == ipv6_payload(["2606:4700:4700::1111"])
        assert "dns" not in payload

    @pytest.mark.asyncio
    async def test_dual_stack_sets_both_families(self, dns_api, mock_session):
        """Test a mixed list configures all four slots in one write."""
        await dns_api.set_custom_dns(
            "net123",
            [
                "1.1.1.1",
                "1.0.0.1",
                "2606:4700:4700::1111",
                "2606:4700:4700::1001",
            ],
        )

        payload = sent_payload(mock_session)
        assert payload["dns"]["custom"]["ips"] == ["1.1.1.1", "1.0.0.1"]
        assert payload["ipv6"]["name_servers"]["custom"] == [
            "2606:4700:4700::1111",
            "2606:4700:4700::1001",
        ]
        assert payload["dns"]["mode"] == DNS_MODE_CUSTOM
        assert payload["ipv6"]["name_servers"]["mode"] == DNS_MODE_CUSTOM

    @pytest.mark.asyncio
    async def test_does_not_send_legacy_field(self, dns_api, mock_session):
        """Regression: `custom_dns` is silently ignored by the API (issue #123)."""
        await dns_api.set_custom_dns("net123", ["1.1.1.1"])

        assert "custom_dns" not in sent_payload(mock_session)

    @pytest.mark.asyncio
    async def test_over_limit_raises_and_does_not_write(self, dns_api, mock_session):
        """Test exceeding the per-family cap raises instead of truncating.

        This replaces the former `test_set_custom_dns_limits_to_two`, which
        asserted silent truncation as correct behaviour.
        """
        servers = ["1.1.1.1", "1.0.0.1", "8.8.8.8"]

        with pytest.raises(EeroValidationException) as exc_info:
            await dns_api.set_custom_dns("net123", servers)

        assert str(MAX_DNS_SERVERS_PER_FAMILY) in str(exc_info.value)
        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_per_family_cap_is_not_a_total_cap(self, dns_api, mock_session):
        """Test 2 IPv4 + 2 IPv6 is accepted even though that is four servers."""
        await dns_api.set_custom_dns(
            "net123",
            ["1.1.1.1", "1.0.0.1", "2606:4700:4700::1111", "2606:4700:4700::1001"],
        )

        mock_session.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_list_raises(self, dns_api, mock_session):
        """Test an empty list is rejected rather than silently clearing DNS."""
        with pytest.raises(EeroValidationException) as exc_info:
            await dns_api.set_custom_dns("net123", [])

        assert "clear_custom_dns" in str(exc_info.value)
        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_authenticated(self, unauthenticated_dns_api, mock_session):
        """Test unauthenticated writes raise without touching the network."""
        with pytest.raises(EeroAuthenticationException):
            await unauthenticated_dns_api.set_custom_dns("net123", ["1.1.1.1"])

        mock_session.request.assert_not_called()


# ========================== Per-family set ==========================


class TestSetCustomDnsPerFamily:
    """Tests for set_custom_dns_ipv4 / set_custom_dns_ipv6."""

    @pytest.mark.asyncio
    async def test_ipv4_leaves_ipv6_untouched(self, dns_api, mock_session):
        """Test the IPv4 write carries no ipv6 key at all."""
        await dns_api.set_custom_dns_ipv4("net123", ["8.8.8.8", "8.8.4.4"])

        payload = sent_payload(mock_session)
        assert payload == ipv4_payload(["8.8.8.8", "8.8.4.4"])
        assert "ipv6" not in payload

    @pytest.mark.asyncio
    async def test_ipv6_leaves_ipv4_untouched(self, dns_api, mock_session):
        """Test the IPv6 write carries no dns key at all."""
        await dns_api.set_custom_dns_ipv6("net123", ["2606:4700:4700::1111"])

        payload = sent_payload(mock_session)
        assert payload == ipv6_payload(["2606:4700:4700::1111"])
        assert "dns" not in payload

    @pytest.mark.asyncio
    async def test_ipv4_rejects_ipv6_literal(self, dns_api, mock_session):
        """Test family mismatch is reported distinctly from malformed input."""
        with pytest.raises(EeroValidationException) as exc_info:
            await dns_api.set_custom_dns_ipv4("net123", ["2606:4700:4700::1111"])

        assert "IPv6" in str(exc_info.value)
        assert "expected IPv4" in str(exc_info.value)
        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_ipv6_rejects_ipv4_literal(self, dns_api, mock_session):
        """Test family mismatch in the other direction."""
        with pytest.raises(EeroValidationException) as exc_info:
            await dns_api.set_custom_dns_ipv6("net123", ["1.1.1.1"])

        assert "expected IPv6" in str(exc_info.value)
        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_ipv6_compressed_form_is_preserved(self, dns_api, mock_session):
        """Test we send the compressed literal; the API expands it on storage."""
        await dns_api.set_custom_dns_ipv6("net123", ["2606:4700:4700:0:0:0:0:1111"])

        sent = sent_payload(mock_session)["ipv6"]["name_servers"]["custom"]
        assert sent == ["2606:4700:4700::1111"]

    @pytest.mark.asyncio
    async def test_empty_list_raises(self, dns_api, mock_session):
        """Test an empty per-family list points the caller at clear_custom_dns."""
        with pytest.raises(EeroValidationException) as exc_info:
            await dns_api.set_custom_dns_ipv4("net123", [])

        assert "clear_custom_dns" in str(exc_info.value)
        mock_session.request.assert_not_called()


# ========================== Clearing ==========================


class TestClearCustomDns:
    """Tests for clear_custom_dns."""

    @pytest.mark.asyncio
    async def test_clears_both_families_by_default(self, dns_api, mock_session):
        """Test the default switches both selectors to automatic."""
        await dns_api.clear_custom_dns("net123")

        payload = sent_payload(mock_session)
        assert payload["dns"]["mode"] == DNS_MODE_AUTOMATIC
        assert payload["ipv6"]["name_servers"]["mode"] == DNS_MODE_AUTOMATIC

    @pytest.mark.asyncio
    async def test_is_non_destructive(self, dns_api, mock_session):
        """Test clearing does not send an empty server list.

        The API retains stored servers when mode is automatic, mirroring the
        app's "ISP DNS (Default)" option. Sending an empty list would discard
        the user's configuration.
        """
        await dns_api.clear_custom_dns("net123")

        payload = sent_payload(mock_session)
        assert "custom" not in payload["dns"]
        assert "custom" not in payload["ipv6"]["name_servers"]

    @pytest.mark.asyncio
    async def test_clear_ipv4_only(self, dns_api, mock_session):
        """Test clearing IPv4 leaves the IPv6 selector alone."""
        await dns_api.clear_custom_dns("net123", family="ipv4")

        payload = sent_payload(mock_session)
        assert payload == ipv4_payload(None, mode=DNS_MODE_AUTOMATIC)
        assert "ipv6" not in payload

    @pytest.mark.asyncio
    async def test_clear_ipv6_only(self, dns_api, mock_session):
        """Test clearing IPv6 leaves the IPv4 selector alone."""
        await dns_api.clear_custom_dns("net123", family="ipv6")

        payload = sent_payload(mock_session)
        assert payload == ipv6_payload(None, mode=DNS_MODE_AUTOMATIC)
        assert "dns" not in payload

    @pytest.mark.asyncio
    async def test_invalid_family_raises(self, dns_api, mock_session):
        """Test an unknown family is rejected before any write."""
        with pytest.raises(EeroValidationException):
            await dns_api.clear_custom_dns("net123", family="ipv5")

        mock_session.request.assert_not_called()


# ========================== DNS mode ==========================


class TestSetDnsMode:
    """Tests for set_dns_mode."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("preset", ["cloudflare", "google", "opendns", "quad9"])
    async def test_provider_names_are_not_modes(self, dns_api, mock_session, preset):
        """Test provider names are rejected rather than resolved by the SDK.

        The API serves its own provider catalogue at dns.default_test_servers.
        Hardcoding a copy here would duplicate server-owned data and go stale —
        an earlier draft did exactly that and already omitted Quad9, which the
        API offers. Consumers read the catalogue and pass the addresses.
        """
        with pytest.raises(EeroValidationException) as exc_info:
            await dns_api.set_dns_mode("net123", preset)

        assert "default_test_servers" in str(exc_info.value)
        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mode", ["auto", "automatic", "AUTO"])
    async def test_auto_switches_mode_without_discarding_servers(self, dns_api, mock_session, mode):
        """Test "auto" is a mode change, not a server-list wipe.

        The previous implementation sent an empty custom_dns list, conflating
        "use automatic DNS" with "delete the user's servers".
        """
        await dns_api.set_dns_mode("net123", mode)

        payload = sent_payload(mock_session)
        assert payload["dns"]["mode"] == DNS_MODE_AUTOMATIC
        assert "custom" not in payload["dns"]

    @pytest.mark.asyncio
    async def test_custom_mode_with_servers(self, dns_api, mock_session):
        """Test custom mode forwards the supplied servers."""
        await dns_api.set_dns_mode("net123", "custom", ["9.9.9.9"])

        assert sent_payload(mock_session) == ipv4_payload(["9.9.9.9"])

    @pytest.mark.asyncio
    async def test_custom_mode_without_servers_reenables_stored(self, dns_api, mock_session):
        """Test omitting servers re-enables what the network already stores.

        Live-verified: a mode-only write to "custom" restores the retained
        servers, so requiring the caller to resupply them would be busywork.
        """
        await dns_api.set_dns_mode("net123", "custom")

        payload = sent_payload(mock_session)
        assert payload["dns"] == {"mode": DNS_MODE_CUSTOM}
        assert payload["ipv6"]["name_servers"] == {"mode": DNS_MODE_CUSTOM}

    @pytest.mark.asyncio
    async def test_reenable_sends_no_server_list(self, dns_api, mock_session):
        """Test the re-enable carries no `custom` key.

        Sending an empty list would erase the stored servers — the opposite of
        the intent.
        """
        await dns_api.set_dns_mode("net123", "custom")

        payload = sent_payload(mock_session)
        assert "custom" not in payload["dns"]
        assert "custom" not in payload["ipv6"]["name_servers"]

    @pytest.mark.asyncio
    async def test_clear_then_reenable_round_trip(self, dns_api, mock_session):
        """Test clear and re-enable are exact inverses at the payload level."""
        await dns_api.clear_custom_dns("net123")
        cleared = sent_payload(mock_session)

        await dns_api.set_dns_mode("net123", "custom")
        restored = sent_payload(mock_session)

        assert cleared["dns"]["mode"] == DNS_MODE_AUTOMATIC
        assert restored["dns"]["mode"] == DNS_MODE_CUSTOM
        assert cleared.keys() == restored.keys()

    @pytest.mark.asyncio
    async def test_invalid_mode_raises(self, dns_api, mock_session):
        """Test an unknown mode raises rather than fabricating a 400 response.

        The previous implementation returned a locally-built
        {"meta": {"code": 400}} envelope that never came from the API.
        """
        with pytest.raises(EeroValidationException) as exc_info:
            await dns_api.set_dns_mode("net123", "not-a-mode")

        assert exc_info.value.field == "mode"
        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_targets_settings_endpoint(self, dns_api, mock_session):
        """Test the write goes to the settings sub-resource."""
        await dns_api.set_dns_mode("net123", "custom", ["9.9.9.9"])

        assert "networks/net123/settings" in sent_url(mock_session)


# ========================== Validation ==========================


class TestServerValidation:
    """Tests for IP-literal validation."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad",
        [
            "dns.google",
            "8.8.8.8:53",
            "[2606:4700:4700::1111]:53",
            "999.999.999.999",
            "",
            "   ",
            "1.1.1",
        ],
    )
    async def test_rejects_invalid_literals(self, dns_api, mock_session, bad):
        """Test malformed input is rejected locally, before any request."""
        with pytest.raises(EeroValidationException):
            await dns_api.set_custom_dns("net123", [bad])

        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_non_string_entries(self, dns_api, mock_session):
        """Test a None entry raises a clear validation error, not AttributeError."""
        with pytest.raises(EeroValidationException):
            await dns_api.set_custom_dns("net123", [None])

        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_non_list(self, dns_api, mock_session):
        """Test a bare string is rejected rather than iterated character by character."""
        with pytest.raises(EeroValidationException):
            await dns_api.set_custom_dns("net123", "1.1.1.1")

        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_strips_surrounding_whitespace(self, dns_api, mock_session):
        """Test padded input is normalised rather than rejected."""
        await dns_api.set_custom_dns("net123", ["  1.1.1.1  "])

        assert sent_payload(mock_session)["dns"]["custom"]["ips"] == ["1.1.1.1"]

    @pytest.mark.asyncio
    async def test_rejects_ipv6_zone_identifier(self, dns_api, mock_session):
        """Test a zone-scoped address is rejected; zones are meaningless to a cloud API."""
        with pytest.raises(EeroValidationException):
            await dns_api.set_custom_dns("net123", ["fe80::1%eth0"])

        mock_session.request.assert_not_called()


# ========================== IPv6 upstream toggle ==========================


class TestSetIpv6Dns:
    """Tests for set_ipv6_dns (the ipv6_upstream toggle)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("enabled", [True, False])
    async def test_writes_ipv6_upstream(self, dns_api, mock_session, enabled):
        """Test this writes the connectivity toggle, not DNS servers."""
        await dns_api.set_ipv6_dns("net123", enabled)

        assert sent_payload(mock_session) == {"ipv6_upstream": enabled}

    @pytest.mark.asyncio
    async def test_does_not_touch_name_servers(self, dns_api, mock_session):
        """Test it leaves IPv6 DNS configuration alone.

        IPv6 custom DNS works independently of ipv6_upstream — verified with
        name_servers.mode == "custom" while ipv6_upstream was False.
        """
        await dns_api.set_ipv6_dns("net123", True)

        assert "ipv6" not in sent_payload(mock_session)
