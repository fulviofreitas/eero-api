"""Tests for SecurityAPI module.

Tests cover security settings like WPA3, band steering, UPnP, IPv6, MLO
mode, fast transition, Passpoint, and proxied nodes.
"""

import copy
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.security import SecurityAPI
from eero.exceptions import EeroAuthenticationException, EeroValidationException

from .conftest import api_success_response, create_mock_response


class TestSecurityAPILinkWiring:
    """Tests for URL resolution on the settings write path."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_wpa3_uses_default_template(self, security_api, mock_session):
        """Test set_wpa3 builds the settings URL from the template with no parent."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await security_api.set_wpa3("network_123", True)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.2/networks/network_123/settings")
        assert call_args.kwargs["json"] == {"wpa3": True}

    @pytest.mark.asyncio
    async def test_set_wpa3_prefers_parent_link(self, security_api, mock_session):
        """Test set_wpa3 uses the network's published settings link over the template."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        parent = {"resources": {"settings": "/2.3/networks/network_123/settings"}}
        parent_copy = copy.deepcopy(parent)

        await security_api.set_wpa3("network_123", True, parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/settings")
        assert parent == parent_copy


class TestSecurityAPIInit:
    """Tests for SecurityAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = SecurityAPI(auth_api)
        assert api._auth_api is auth_api


class TestSecurityAPIGetSettings:
    """Tests for get_security_settings method."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_security_settings_returns_raw_response(self, security_api, mock_session):
        """Test getting security settings returns raw response."""
        network_data = {
            "wpa3": True,
            "band_steering": True,
            "upnp": False,
        }
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await security_api.get_security_settings("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_security_settings_not_authenticated(self, security_api):
        """Test get_security_settings raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await security_api.get_security_settings("network_123")


class TestSecurityAPISetWPA3:
    """Tests for set_wpa3 method."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_wpa3_returns_raw_response(self, security_api, mock_session):
        """Test setting WPA3 returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_wpa3("network_123", True)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"wpa3": True}

    @pytest.mark.asyncio
    async def test_set_wpa3_targets_settings_endpoint(self, security_api, mock_session):
        """Test set_wpa3 sends request to /settings endpoint."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        await security_api.set_wpa3("network_123", True)

        call_args = mock_session.request.call_args
        url = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "networks/network_123/settings" in url

    @pytest.mark.asyncio
    async def test_set_wpa3_not_authenticated(self, security_api):
        """Test set_wpa3 raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.set_wpa3("network_123", True)


class TestSecurityAPISetBandSteering:
    """Tests for set_band_steering method."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_band_steering_returns_raw_response(self, security_api, mock_session):
        """Test setting band steering returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_band_steering("network_123", True)

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_set_band_steering_targets_settings_endpoint(self, security_api, mock_session):
        """Test set_band_steering sends request to /settings endpoint."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        await security_api.set_band_steering("network_123", True)

        call_args = mock_session.request.call_args
        url = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "networks/network_123/settings" in url


class TestSecurityAPISetUPnP:
    """Tests for set_upnp method."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_upnp_returns_raw_response(self, security_api, mock_session):
        """Test setting UPnP returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_upnp("network_123", True)

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_set_upnp_targets_settings_endpoint(self, security_api, mock_session):
        """Test set_upnp sends request to /settings endpoint."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        await security_api.set_upnp("network_123", True)

        call_args = mock_session.request.call_args
        url = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "networks/network_123/settings" in url


class TestSecurityAPISetIPv6:
    """Tests for set_ipv6 method."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_ipv6_returns_raw_response(self, security_api, mock_session):
        """Test setting IPv6 returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_ipv6("network_123", True)

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_set_ipv6_targets_settings_endpoint(self, security_api, mock_session):
        """Test set_ipv6 sends request to /settings endpoint."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        await security_api.set_ipv6("network_123", True)

        call_args = mock_session.request.call_args
        url = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "networks/network_123/settings" in url

    @pytest.mark.asyncio
    async def test_set_ipv6_not_authenticated(self, security_api):
        """Test set_ipv6 raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.set_ipv6("network_123", True)


class TestSecurityAPIConfigure:
    """Tests for configure_security method."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_configure_security_returns_raw_response(self, security_api, mock_session):
        """Test configure_security returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await security_api.configure_security("network_123", wpa3=True, upnp=False)

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_configure_security_targets_settings_endpoint(self, security_api, mock_session):
        """Test configure_security sends request to /settings endpoint."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        await security_api.configure_security("network_123", wpa3=True, upnp=False)

        call_args = mock_session.request.call_args
        url = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "networks/network_123/settings" in url

    @pytest.mark.asyncio
    async def test_configure_security_not_authenticated(self, security_api):
        """Test configure_security raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.configure_security("network_123", wpa3=True)


@pytest.fixture
def security_api(mock_session):
    """Create a SecurityAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return SecurityAPI(auth_api)


class TestSecurityAPISetMloMode:
    """Tests for set_mlo_mode method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mode", ["disabled", "single", "multi"])
    async def test_set_mlo_mode_sends_json(self, security_api, mock_session, caplog, mode):
        """Test set_mlo_mode PUTs the mode and warns about reboot risk."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await security_api.set_mlo_mode("network_123", mode)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/mlo_mode")
        assert call_args.kwargs["json"] == {"mlo_mode": mode}
        assert any(
            "set MLO mode for network" in message and "reboot" in message
            for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_set_mlo_mode_prefers_parent_link(self, security_api, mock_session):
        """Test set_mlo_mode uses the published link over the template."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        parent = {"resources": {"mlo_mode": "/2.3/networks/network_123/mlo_mode"}}

        await security_api.set_mlo_mode("network_123", "single", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/mlo_mode")

    @pytest.mark.asyncio
    async def test_set_mlo_mode_rejects_invalid_mode(self, security_api):
        """Test set_mlo_mode rejects an undeclared mode value."""
        with pytest.raises(EeroValidationException):
            await security_api.set_mlo_mode("network_123", "DISABLED")

    @pytest.mark.asyncio
    async def test_set_mlo_mode_not_authenticated(self, security_api):
        """Test set_mlo_mode raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.set_mlo_mode("network_123", "single")


class TestSecurityAPIFastTransition:
    """Tests for get_fast_transition and set_fast_transition methods."""

    @pytest.mark.asyncio
    async def test_get_fast_transition_returns_raw_response(self, security_api, mock_session):
        """Test get_fast_transition GETs the fast_transition sub-resource."""
        expected = {"fast_transition": True}
        mock_session.request.return_value = create_mock_response(
            200, api_success_response(expected)
        )

        result = await security_api.get_fast_transition("network_123")

        assert result["data"] == expected
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/fast_transition")

    @pytest.mark.asyncio
    async def test_get_fast_transition_not_authenticated(self, security_api):
        """Test get_fast_transition raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.get_fast_transition("network_123")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("enabled", [True, False])
    async def test_set_fast_transition_sends_json(
        self, security_api, mock_session, caplog, enabled
    ):
        """Test set_fast_transition PUTs the boolean field and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await security_api.set_fast_transition("network_123", enabled)

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/fast_transition")
        assert call_args.kwargs["json"] == {"fast_transition": enabled}
        assert any("set fast transition for network" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_fast_transition_not_authenticated(self, security_api):
        """Test set_fast_transition raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.set_fast_transition("network_123", True)


class TestSecurityAPISetPasspointEnabled:
    """Tests for set_passpoint_enabled method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("enabled", [True, False])
    async def test_set_passpoint_enabled_sends_json(
        self, security_api, mock_session, caplog, enabled
    ):
        """Test set_passpoint_enabled PUTs the boolean field and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await security_api.set_passpoint_enabled("network_123", enabled)

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/passpoint/enabled")
        assert call_args.kwargs["json"] == {"enabled": enabled}
        assert any("set Passpoint enabled for network" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_passpoint_enabled_not_authenticated(self, security_api):
        """Test set_passpoint_enabled raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.set_passpoint_enabled("network_123", True)


class TestSecurityAPISetProxiedNodes:
    """Tests for set_proxied_nodes method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("enabled", [True, False])
    async def test_set_proxied_nodes_sends_json(self, security_api, mock_session, caplog, enabled):
        """Test set_proxied_nodes PUTs the boolean field and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await security_api.set_proxied_nodes("network_123", enabled)

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/proxied_nodes")
        assert call_args.kwargs["json"] == {"enabled": enabled}
        assert any("set proxied nodes for network" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_proxied_nodes_not_authenticated(self, security_api):
        """Test set_proxied_nodes raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.set_proxied_nodes("network_123", True)


# ========================== Settings-write reboot warning ==========================


class TestSettingsWriteRebootWarning:
    """Tests for the uncharacterised-write warning on the settings-class writes.

    These writes PUT the network's ``settings`` sub-resource -- the same
    endpoint the DNS module's confirmed-reboot write targets -- so each must
    warn, once per call, that it may reboot every eero on the mesh.
    """

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "call",
        [
            lambda api: api.set_wpa3("network_123", True),
            lambda api: api.set_band_steering("network_123", True),
            lambda api: api.set_upnp("network_123", True),
            lambda api: api.set_ipv6("network_123", True),
            lambda api: api.configure_security("network_123", wpa3=True),
        ],
    )
    async def test_settings_write_warns_once_about_reboot(
        self, security_api, mock_session, caplog, call
    ):
        """Test each settings-class write logs exactly one reboot warning."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING, logger="eero.api.security"):
            await call(security_api)

        reboot_warnings = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and "reboot" in r.getMessage().lower()
        ]
        assert len(reboot_warnings) == 1
