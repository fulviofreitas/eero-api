"""Tests for SubnetsAPI module.

Tests cover:
- get_config: verified read, parent-link preference
- set_config: JSON body forwarded unchanged
- delete_subnet: DELETE by subnet type
- set_content_filters: JSON body forwarded unchanged
- get_content_filters: verified read
- The uncharacterised-write warning on every unverified write
- Not-authenticated errors on every method
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.subnets import SubnetsAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def subnets_api(mock_session):
    """Create a SubnetsAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return SubnetsAPI(auth_api)


class TestSubnetsAPIInit:
    """Tests for SubnetsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = SubnetsAPI(auth_api)

        assert api._auth_api is auth_api


class TestSubnetsAPIGetConfig:
    """Tests for get_config method."""

    @pytest.mark.asyncio
    async def test_get_config_returns_raw_response(self, subnets_api, mock_session):
        """Test get_config GETs the subnets_config sub-resource."""
        expected = {"subnet_type": "main"}
        mock_session.request.return_value = create_mock_response(
            200, api_success_response(expected)
        )

        result = await subnets_api.get_config("network_123")

        assert result["data"] == expected
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/subnets_config")

    @pytest.mark.asyncio
    async def test_get_config_prefers_parent_link(self, subnets_api, mock_session):
        """Test get_config uses the published link over the template."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        parent = {"resources": {"subnets_config": "/2.3/networks/network_123/subnets_config"}}

        await subnets_api.get_config("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/subnets_config")

    @pytest.mark.asyncio
    async def test_get_config_not_authenticated(self, subnets_api):
        """Test get_config raises when not authenticated."""
        subnets_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await subnets_api.get_config("network_123")


class TestSubnetsAPISetConfig:
    """Tests for set_config method."""

    @pytest.mark.asyncio
    async def test_set_config_forwards_body_unchanged(self, subnets_api, mock_session, caplog):
        """Test set_config PUTs the caller's mapping unchanged and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        config = {"subnet_type": "guest", "enabled": True, "wan_access": False}

        with caplog.at_level(logging.WARNING):
            await subnets_api.set_config("network_123", config)

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/subnets_config")
        assert call_args.kwargs["json"] == config
        assert any("set subnet configuration for network" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_config_never_logs_password(self, subnets_api, mock_session, caplog):
        """Test set_config never logs a plaintext password value present in config."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.DEBUG):
            await subnets_api.set_config(
                "network_123", {"subnet_type": "guest", "password": "super-secret-value"}
            )

        assert not any("super-secret-value" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_config_not_authenticated(self, subnets_api):
        """Test set_config raises when not authenticated."""
        subnets_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await subnets_api.set_config("network_123", {})


class TestSubnetsAPIDeleteSubnet:
    """Tests for delete_subnet method."""

    @pytest.mark.asyncio
    async def test_delete_subnet_sends_delete(self, subnets_api, mock_session, caplog):
        """Test delete_subnet DELETEs the subnet type sub-resource and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await subnets_api.delete_subnet("network_123", "guest")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "DELETE"
        assert call_args.args[1].endswith("/2.2/networks/network_123/subnets_config/guest")
        assert any("delete subnet guest for network" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_delete_subnet_not_authenticated(self, subnets_api):
        """Test delete_subnet raises when not authenticated."""
        subnets_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await subnets_api.delete_subnet("network_123", "guest")


class TestSubnetsAPISetContentFilters:
    """Tests for set_content_filters method."""

    @pytest.mark.asyncio
    async def test_set_content_filters_forwards_body_unchanged(
        self, subnets_api, mock_session, caplog
    ):
        """Test set_content_filters PUTs the caller's mapping unchanged and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        filters = {"content_filters": ["adult"], "subnets": ["subnet_001"]}

        with caplog.at_level(logging.WARNING):
            await subnets_api.set_content_filters("network_123", filters)

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith(
            "/2.2/networks/network_123/subnets_config/dns_policies/content_filters"
        )
        assert call_args.kwargs["json"] == filters
        assert any(
            "set subnet content filters for network" in message for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_set_content_filters_not_authenticated(self, subnets_api):
        """Test set_content_filters raises when not authenticated."""
        subnets_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await subnets_api.set_content_filters("network_123", {})


class TestSubnetsAPIGetContentFilters:
    """Tests for get_content_filters method."""

    @pytest.mark.asyncio
    async def test_get_content_filters_returns_raw_response(self, subnets_api, mock_session):
        """Test get_content_filters GETs the per-subnet content-filters sub-resource."""
        expected = {"dns_policies_enabled": True}
        mock_session.request.return_value = create_mock_response(
            200, api_success_response(expected)
        )

        result = await subnets_api.get_content_filters("network_123", "subnet_001")

        assert result["data"] == expected
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith(
            "/2.2/networks/network_123/subnets_config/subnet_001/dns_policies/content_filters"
        )

    @pytest.mark.asyncio
    async def test_get_content_filters_not_authenticated(self, subnets_api):
        """Test get_content_filters raises when not authenticated."""
        subnets_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await subnets_api.get_content_filters("network_123", "subnet_001")
