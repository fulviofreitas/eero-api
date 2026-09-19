"""Tests for EntitlementsAPI module.

Tests cover:
- Getting entitled features, upsell features, model capabilities, and the
  premium customer record (all raw responses)
- id/path/URL polymorphism on the network-scoped reads
- The exact ``networkId`` query-parameter casing on the model-capabilities read
- Not-authenticated handling on every method
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.entitlements import EntitlementsAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def entitlements_api(mock_session):
    """Create an EntitlementsAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return EntitlementsAPI(auth_api)


class TestEntitlementsAPIInit:
    """Tests for EntitlementsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = EntitlementsAPI(auth_api)

        assert api._auth_api is auth_api


class TestEntitlementsAPIGetFeatures:
    """Tests for get_features method."""

    @pytest.mark.asyncio
    async def test_get_features_accepts_bare_id(self, entitlements_api, mock_session):
        """Test get_features builds the entitlements URL from a bare network id."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"features": []})
        )

        result = await entitlements_api.get_features("network_123")

        assert result["data"]["features"] == []
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/entitlements/networks/network_123/features")

    @pytest.mark.asyncio
    async def test_get_features_accepts_absolute_entitlements_url(
        self, entitlements_api, mock_session
    ):
        """Test get_features accepts an absolute URL already on the entitlements path."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"features": []})
        )
        absolute_url = "https://api-user.e2ro.com/2.2/entitlements/networks/network_123"

        await entitlements_api.get_features(absolute_url)

        call_args = mock_session.request.call_args
        assert call_args.args[1] == f"{absolute_url}/features"

    @pytest.mark.asyncio
    async def test_get_features_not_authenticated(self, entitlements_api):
        """Test get_features raises when not authenticated."""
        entitlements_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await entitlements_api.get_features("network_123")


class TestEntitlementsAPIGetUpsellFeatures:
    """Tests for get_upsell_features method."""

    @pytest.mark.asyncio
    async def test_get_upsell_features_returns_raw_response(self, entitlements_api, mock_session):
        """Test get_upsell_features GETs the upsell_features path."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"upsell_features": []})
        )

        result = await entitlements_api.get_upsell_features("network_123")

        assert result["data"]["upsell_features"] == []
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/entitlements/networks/network_123/upsell_features")

    @pytest.mark.asyncio
    async def test_get_upsell_features_not_authenticated(self, entitlements_api):
        """Test get_upsell_features raises when not authenticated."""
        entitlements_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await entitlements_api.get_upsell_features("network_123")


class TestEntitlementsAPIGetModelCapabilities:
    """Tests for get_model_capabilities method."""

    @pytest.mark.asyncio
    async def test_get_model_capabilities_sends_network_id_query_param(
        self, entitlements_api, mock_session
    ):
        """Test get_model_capabilities GETs /eero_models/capabilities with networkId."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"models": []})
        )

        result = await entitlements_api.get_model_capabilities("network_123")

        assert result["data"]["models"] == []
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/eero_models/capabilities")
        assert call_args.kwargs["params"] == {"networkId": "network_123"}

    @pytest.mark.asyncio
    async def test_get_model_capabilities_not_authenticated(self, entitlements_api):
        """Test get_model_capabilities raises when not authenticated."""
        entitlements_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await entitlements_api.get_model_capabilities("network_123")


class TestEntitlementsAPIGetPremiumCustomer:
    """Tests for get_premium_customer method."""

    @pytest.mark.asyncio
    async def test_get_premium_customer_returns_raw_response(self, entitlements_api, mock_session):
        """Test get_premium_customer GETs /premium/customer."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"is_premium": True})
        )

        result = await entitlements_api.get_premium_customer()

        assert result["data"]["is_premium"] is True
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/premium/customer")

    @pytest.mark.asyncio
    async def test_get_premium_customer_not_authenticated(self, entitlements_api):
        """Test get_premium_customer raises when not authenticated."""
        entitlements_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await entitlements_api.get_premium_customer()
