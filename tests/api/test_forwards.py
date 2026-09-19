"""Tests for ForwardsAPI module."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.forwards import ForwardsAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestForwardsAPIInit:
    """Tests for ForwardsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = ForwardsAPI(auth_api)
        assert api._auth_api is auth_api


class TestForwardsAPIGetForwards:
    """Tests for get_forwards method."""

    @pytest.fixture
    def forwards_api(self, mock_session):
        """Create a ForwardsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ForwardsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_forwards_returns_raw_response(self, forwards_api, mock_session):
        """Test get_forwards returns raw response."""
        forwards_data = [{"port": 80, "protocol": "tcp", "device_id": "device123"}]
        mock_response = create_mock_response(200, api_success_response(forwards_data))
        mock_session.request.return_value = mock_response

        result = await forwards_api.get_forwards("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_forwards_not_authenticated(self, forwards_api):
        """Test get_forwards raises when not authenticated."""
        forwards_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await forwards_api.get_forwards("network_123")


class TestForwardsAPICreateForward:
    """Tests for create_forward method."""

    @pytest.fixture
    def forwards_api(self, mock_session):
        """Create a ForwardsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ForwardsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_create_forward_returns_raw_response(self, forwards_api, mock_session):
        """Test create_forward returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        forward_data = {"port": 80, "protocol": "tcp"}
        result = await forwards_api.create_forward("network_123", forward_data)

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_create_forward_warns_uncharacterised_write(
        self, forwards_api, mock_session, caplog
    ):
        """Test create_forward logs the uncharacterised-write warning once."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING, logger="eero.api.forwards"):
            await forwards_api.create_forward("network_123", {"port": 80})

        assert any("create forward for network network_123" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_create_forward_not_authenticated(self, forwards_api):
        """Test create_forward raises when not authenticated."""
        forwards_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await forwards_api.create_forward("network_123", {})


class TestForwardsAPIDeleteForward:
    """Tests for delete_forward method."""

    @pytest.fixture
    def forwards_api(self, mock_session):
        """Create a ForwardsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ForwardsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_delete_forward_returns_raw_response(self, forwards_api, mock_session):
        """Test delete_forward returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await forwards_api.delete_forward("network_123", "forward_id")

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_delete_forward_warns_uncharacterised_write(
        self, forwards_api, mock_session, caplog
    ):
        """Test delete_forward logs the uncharacterised-write warning once."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING, logger="eero.api.forwards"):
            await forwards_api.delete_forward("network_123", "forward_id")

        assert any("delete forward for network network_123" in m for m in caplog.messages)


class TestForwardsAPIUpdateForward:
    """Tests for update_forward method."""

    @pytest.fixture
    def forwards_api(self, mock_session):
        """Create a ForwardsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ForwardsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_update_forward_from_path_string(self, forwards_api, mock_session):
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        await forwards_api.update_forward(
            "/2.2/networks/network_123/forwards/f_1", {"enabled": False}
        )

        method, url = mock_session.request.call_args.args[:2]
        assert method == "PUT"
        assert url == "https://api-user.e2ro.com/2.2/networks/network_123/forwards/f_1"
        assert mock_session.request.call_args.kwargs["json"] == {"enabled": False}

    @pytest.mark.asyncio
    async def test_update_forward_from_envelope(self, forwards_api, mock_session):
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response
        envelope = {"url": "/2.3/networks/network_123/forwards/f_1"}

        await forwards_api.update_forward(envelope, {"enabled": True})

        _, url = mock_session.request.call_args.args[:2]
        assert url == "https://api-user.e2ro.com/2.3/networks/network_123/forwards/f_1"

    @pytest.mark.asyncio
    async def test_update_forward_from_bare_id_requires_network(self, forwards_api, mock_session):
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        await forwards_api.update_forward("f_1", {"enabled": True}, network="network_123")

        _, url = mock_session.request.call_args.args[:2]
        assert url == "https://api-user.e2ro.com/2.2/networks/network_123/forwards/f_1"

    @pytest.mark.asyncio
    async def test_update_forward_warns_uncharacterised_write(
        self, forwards_api, mock_session, caplog
    ):
        """Test update_forward logs the uncharacterised-write warning once."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        with caplog.at_level(logging.WARNING, logger="eero.api.forwards"):
            await forwards_api.update_forward(
                "/2.2/networks/network_123/forwards/f_1", {"enabled": False}
            )

        assert any("not been fully characterised" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_update_forward_bare_id_without_network_raises(self, forwards_api):
        from eero.exceptions import EeroValidationException

        with pytest.raises(EeroValidationException):
            await forwards_api.update_forward("f_1", {"enabled": True})

    @pytest.mark.asyncio
    async def test_update_forward_not_authenticated(self, forwards_api):
        forwards_api._auth_api.get_auth_token = AsyncMock(return_value=None)
        with pytest.raises(EeroAuthenticationException):
            await forwards_api.update_forward(
                "/2.2/networks/network_123/forwards/f_1", {"enabled": True}
            )
