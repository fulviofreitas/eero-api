"""Tests for DhcpAPI module.

Tests cover:
- set_dhcp: mode validation, only-given-keys for custom/custom_v2, unknown
  field rejection, parent-link preference, the settings-class reboot warning
- set_connection_mode: enum validation, the settings-class reboot warning
- set_nat_port_randomization: JSON body, the settings-class reboot warning
- set_pppoe: JSON body with nested username/password, password never logged
- Not-authenticated errors on every method
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.dhcp import DhcpAPI
from eero.exceptions import EeroAuthenticationException, EeroValidationException

from .conftest import create_mock_response


@pytest.fixture
def dhcp_api(mock_session):
    """Create a DhcpAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return DhcpAPI(auth_api)


class TestDhcpAPIInit:
    """Tests for DhcpAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = DhcpAPI(auth_api)

        assert api._auth_api is auth_api


class TestDhcpAPISetDhcp:
    """Tests for set_dhcp method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mode", ["automatic", "manual"])
    async def test_set_dhcp_mode_only(self, dhcp_api, mock_session, caplog, mode):
        """Test set_dhcp sends only the mode field, and warns about the mesh reboot risk."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await dhcp_api.set_dhcp("network_123", mode=mode)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/settings")
        assert call_args.kwargs["json"] == {"dhcp": {"mode": mode}}
        assert any(
            "set DHCP configuration for network" in message and "reboot" in message
            for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_set_dhcp_custom_only_given_keys(self, dhcp_api, mock_session):
        """Test set_dhcp forwards only the supplied custom lease-range keys."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await dhcp_api.set_dhcp("network_123", custom={"start_ip": "192.0.2.10"})

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"dhcp": {"custom": {"start_ip": "192.0.2.10"}}}

    @pytest.mark.asyncio
    async def test_set_dhcp_custom_v2_only_given_keys(self, dhcp_api, mock_session):
        """Test set_dhcp forwards only the supplied custom_v2 keys."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await dhcp_api.set_dhcp("network_123", custom_v2={"supernet": "10.0.0.0/8"})

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"dhcp": {"custom_v2": {"supernet": "10.0.0.0/8"}}}

    @pytest.mark.asyncio
    async def test_set_dhcp_rejects_invalid_mode(self, dhcp_api):
        """Test set_dhcp rejects a mode outside automatic/manual."""
        with pytest.raises(EeroValidationException):
            await dhcp_api.set_dhcp("network_123", mode="AUTOMATIC")

    @pytest.mark.asyncio
    async def test_set_dhcp_rejects_unknown_custom_field(self, dhcp_api):
        """Test set_dhcp rejects an undeclared custom lease-range field."""
        with pytest.raises(EeroValidationException):
            await dhcp_api.set_dhcp("network_123", custom={"bogus_field": "x"})

    @pytest.mark.asyncio
    async def test_set_dhcp_rejects_unknown_custom_v2_field(self, dhcp_api):
        """Test set_dhcp rejects an undeclared custom_v2 field."""
        with pytest.raises(EeroValidationException):
            await dhcp_api.set_dhcp("network_123", custom_v2={"bogus_field": "x"})

    @pytest.mark.asyncio
    async def test_set_dhcp_rejects_no_fields(self, dhcp_api):
        """Test set_dhcp rejects a call with no fields supplied."""
        with pytest.raises(EeroValidationException):
            await dhcp_api.set_dhcp("network_123")

    @pytest.mark.asyncio
    async def test_set_dhcp_prefers_parent_link(self, dhcp_api, mock_session):
        """Test set_dhcp uses the network's published settings link over the template."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        parent = {"resources": {"settings": "/2.3/networks/network_123/settings"}}

        await dhcp_api.set_dhcp("network_123", mode="automatic", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/settings")

    @pytest.mark.asyncio
    async def test_set_dhcp_not_authenticated(self, dhcp_api):
        """Test set_dhcp raises when not authenticated."""
        dhcp_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await dhcp_api.set_dhcp("network_123", mode="automatic")


class TestDhcpAPISetConnectionMode:
    """Tests for set_connection_mode method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mode", ["BRIDGE", "NAT"])
    async def test_set_connection_mode_sends_json(self, dhcp_api, mock_session, caplog, mode):
        """Test set_connection_mode PUTs the connection mode and warns about reboot risk."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await dhcp_api.set_connection_mode("network_123", mode)

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.kwargs["json"] == {"connection": {"mode": mode}}
        assert any(
            "set connection mode for network" in message and "reboot" in message
            for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_set_connection_mode_rejects_invalid_mode(self, dhcp_api):
        """Test set_connection_mode rejects a value outside BRIDGE/NAT."""
        with pytest.raises(EeroValidationException):
            await dhcp_api.set_connection_mode("network_123", "bridge")

    @pytest.mark.asyncio
    async def test_set_connection_mode_not_authenticated(self, dhcp_api):
        """Test set_connection_mode raises when not authenticated."""
        dhcp_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await dhcp_api.set_connection_mode("network_123", "NAT")


class TestDhcpAPISetNatPortRandomization:
    """Tests for set_nat_port_randomization method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("enabled", [True, False])
    async def test_set_nat_port_randomization_sends_json(
        self, dhcp_api, mock_session, caplog, enabled
    ):
        """Test set_nat_port_randomization PUTs the boolean field and warns about reboot risk."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await dhcp_api.set_nat_port_randomization("network_123", enabled)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"nat_port_randomization": enabled}
        assert any(
            "set NAT port randomization for network" in message and "reboot" in message
            for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_set_nat_port_randomization_not_authenticated(self, dhcp_api):
        """Test set_nat_port_randomization raises when not authenticated."""
        dhcp_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await dhcp_api.set_nat_port_randomization("network_123", True)


class TestDhcpAPISetPppoe:
    """Tests for set_pppoe method."""

    @pytest.mark.asyncio
    async def test_set_pppoe_sends_nested_json(self, dhcp_api, mock_session, caplog):
        """Test set_pppoe POSTs nested username/password JSON and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {"pppoe_credentials": "encrypted-blob"}}
        )

        with caplog.at_level(logging.WARNING):
            result = await dhcp_api.set_pppoe(
                "eero-serial-placeholder", username="isp-user", password="isp-secret"
            )

        assert result["data"]["pppoe_credentials"] == "encrypted-blob"
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith("/2.2/eeros/eero-serial-placeholder/pppoe")
        assert call_args.kwargs["json"] == {
            "pppoe": {"username": "isp-user", "password": "isp-secret"}
        }
        assert any("encrypt PPPoE credentials for eero" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_pppoe_never_logs_password(self, dhcp_api, mock_session, caplog):
        """Test set_pppoe never logs the plaintext password value."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.DEBUG):
            await dhcp_api.set_pppoe(
                "eero-serial-placeholder", username="isp-user", password="super-secret-value"
            )

        assert not any("super-secret-value" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_pppoe_not_authenticated(self, dhcp_api):
        """Test set_pppoe raises when not authenticated."""
        dhcp_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await dhcp_api.set_pppoe("eero-serial-placeholder", username="u", password="p")
