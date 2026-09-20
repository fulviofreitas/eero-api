"""Tests for DnsPoliciesAPI module."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.dns_policies import DnsPoliciesAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestDnsPoliciesAPIInit:
    """Tests for DnsPoliciesAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = DnsPoliciesAPI(auth_api)
        assert api._auth_api is auth_api


@pytest.fixture
def dns_policies_api(mock_session):
    """Create a DnsPoliciesAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return DnsPoliciesAPI(auth_api)


class TestGetAdvancedContentFilter:
    """Tests for get_advanced_content_filter."""

    @pytest.mark.asyncio
    async def test_returns_raw_envelope(self, dns_policies_api, mock_session):
        """Test the raw envelope is returned unchanged."""
        data = {"allowed_list": [{"domain": "example.test"}], "blocked_list": []}
        envelope = api_success_response(data)
        mock_session.request.return_value = create_mock_response(200, envelope)

        result = await dns_policies_api.get_advanced_content_filter("network_123")

        assert result == envelope

    @pytest.mark.asyncio
    async def test_uses_literal_path_by_default(self, dns_policies_api, mock_session):
        """Test the default template is used with no parent."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await dns_policies_api.get_advanced_content_filter("network_123")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith(
            "/networks/network_123/dns_policies/advanced_content_filter"
        )

    @pytest.mark.asyncio
    async def test_prefers_parent_link(self, dns_policies_api, mock_session):
        """Test a published parent link is preferred over the template."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        parent = {
            "resources": {
                "advanced_content_filter": "/2.3/networks/network_123/dns_policies/advanced_content_filter"
            }
        }

        await dns_policies_api.get_advanced_content_filter("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith(
            "/2.3/networks/network_123/dns_policies/advanced_content_filter"
        )

    @pytest.mark.asyncio
    async def test_not_authenticated(self, dns_policies_api):
        """Test raises when not authenticated."""
        dns_policies_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await dns_policies_api.get_advanced_content_filter("network_123")


class TestAllowDomain:
    """Tests for allow_domain."""

    @pytest.mark.asyncio
    async def test_only_domain_sent_by_default(self, dns_policies_api, mock_session):
        """Test only the required 'domain' key is sent with no optionals."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await dns_policies_api.allow_domain("network_123", "example.test")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.kwargs["json"] == {"domain": "example.test"}
        assert call_args.args[1].endswith("/networks/network_123/dns_policies/network/allowed")

    @pytest.mark.parametrize(
        "kwargs,expected_extra",
        [
            ({"add_cname": True}, {"add_cname": True}),
            ({"reason_to_allow": 3}, {"reason_to_allow": 3}),
            ({"is_delete": True}, {"is_delete": True}),
            ({"keep_profiles": ["p_1"]}, {"keep_profiles": ["p_1"]}),
            (
                {"add_cname": False, "is_delete": False},
                {"add_cname": False, "is_delete": False},
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_only_given_optional_keys_sent(
        self, dns_policies_api, mock_session, kwargs, expected_extra
    ):
        """Test only explicitly supplied optional fields appear in the body."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await dns_policies_api.allow_domain("network_123", "example.test", **kwargs)

        call_args = mock_session.request.call_args
        expected = {"domain": "example.test", **expected_extra}
        assert call_args.kwargs["json"] == expected

    @pytest.mark.asyncio
    async def test_warns_uncharacterised_write(self, dns_policies_api, mock_session, caplog):
        """Test the write logs the unconfirmed-write warning exactly once."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.WARNING):
            await dns_policies_api.allow_domain("network_123", "example.test")

        matches = [m for m in caplog.messages if "allow domain for network" in m]
        assert len(matches) == 1

    @pytest.mark.asyncio
    async def test_not_authenticated(self, dns_policies_api):
        """Test raises when not authenticated."""
        dns_policies_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await dns_policies_api.allow_domain("network_123", "example.test")


class TestAllowCnames:
    """Tests for allow_cnames."""

    @pytest.mark.asyncio
    async def test_sends_only_domains_field(self, dns_policies_api, mock_session):
        """Test the request body declares only 'domains'."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await dns_policies_api.allow_cnames("network_123", ["cname.example.test"])

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.kwargs["json"] == {"domains": ["cname.example.test"]}
        assert call_args.args[1].endswith(
            "/networks/network_123/dns_policies/network/allowed/cnames"
        )

    @pytest.mark.asyncio
    async def test_warns_uncharacterised_write(self, dns_policies_api, mock_session, caplog):
        """Test the write logs the unconfirmed-write warning."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.WARNING):
            await dns_policies_api.allow_cnames("network_123", ["cname.example.test"])

        assert any("allow CNAMEs for network" in m for m in caplog.messages)


class TestBlockDomain:
    """Tests for block_domain."""

    @pytest.mark.asyncio
    async def test_only_domain_sent_by_default(self, dns_policies_api, mock_session):
        """Test only 'domain' is sent with no optionals."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await dns_policies_api.block_domain("network_123", "blocked.example.test")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.kwargs["json"] == {"domain": "blocked.example.test"}
        assert call_args.args[1].endswith("/networks/network_123/dns_policies/network/blocked")

    @pytest.mark.parametrize(
        "kwargs,expected_extra",
        [
            ({"is_delete": True}, {"is_delete": True}),
            ({"keep_profiles": ["p_1", "p_2"]}, {"keep_profiles": ["p_1", "p_2"]}),
        ],
    )
    @pytest.mark.asyncio
    async def test_only_given_optional_keys_sent(
        self, dns_policies_api, mock_session, kwargs, expected_extra
    ):
        """Test only explicitly supplied optional fields appear in the body."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await dns_policies_api.block_domain("network_123", "blocked.example.test", **kwargs)

        call_args = mock_session.request.call_args
        expected = {"domain": "blocked.example.test", **expected_extra}
        assert call_args.kwargs["json"] == expected


class TestAllowDomainForProfiles:
    """Tests for allow_domain_for_profiles."""

    @pytest.mark.asyncio
    async def test_domain_and_profiles_always_sent(self, dns_policies_api, mock_session):
        """Test the required fields are sent with no optionals."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await dns_policies_api.allow_domain_for_profiles(
            "network_123", "example.test", profiles=["p_1"]
        )

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.kwargs["json"] == {"domain": "example.test", "profiles": ["p_1"]}
        assert call_args.args[1].endswith("/networks/network_123/dns_policies/profiles/allowed")

    @pytest.mark.parametrize(
        "kwargs,expected_extra",
        [
            ({"override": True}, {"override": True}),
            ({"add_cname": True}, {"add_cname": True}),
            ({"reason_to_allow": 1}, {"reason_to_allow": 1}),
            ({"is_delete": True}, {"is_delete": True}),
        ],
    )
    @pytest.mark.asyncio
    async def test_only_given_optional_keys_sent(
        self, dns_policies_api, mock_session, kwargs, expected_extra
    ):
        """Test only explicitly supplied optional fields appear in the body."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await dns_policies_api.allow_domain_for_profiles(
            "network_123", "example.test", profiles=["p_1"], **kwargs
        )

        call_args = mock_session.request.call_args
        expected = {"domain": "example.test", "profiles": ["p_1"], **expected_extra}
        assert call_args.kwargs["json"] == expected


class TestAllowCnamesForProfiles:
    """Tests for allow_cnames_for_profiles."""

    @pytest.mark.asyncio
    async def test_sends_domains_and_profiles(self, dns_policies_api, mock_session):
        """Test the request body declares 'domains' and 'profiles'."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await dns_policies_api.allow_cnames_for_profiles(
            "network_123", ["cname.example.test"], profiles=["p_1"]
        )

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {
            "domains": ["cname.example.test"],
            "profiles": ["p_1"],
        }
        assert call_args.args[1].endswith(
            "/networks/network_123/dns_policies/profiles/allowed/cnames"
        )


class TestBlockDomainForProfiles:
    """Tests for block_domain_for_profiles."""

    @pytest.mark.asyncio
    async def test_domain_and_profiles_always_sent(self, dns_policies_api, mock_session):
        """Test the required fields are sent with no optionals."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await dns_policies_api.block_domain_for_profiles(
            "network_123", "blocked.example.test", profiles=["p_1"]
        )

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {
            "domain": "blocked.example.test",
            "profiles": ["p_1"],
        }
        assert call_args.args[1].endswith("/networks/network_123/dns_policies/profiles/blocked")

    @pytest.mark.parametrize(
        "kwargs,expected_extra",
        [
            ({"is_delete": True}, {"is_delete": True}),
            ({"override": True}, {"override": True}),
        ],
    )
    @pytest.mark.asyncio
    async def test_only_given_optional_keys_sent(
        self, dns_policies_api, mock_session, kwargs, expected_extra
    ):
        """Test only explicitly supplied optional fields appear in the body."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await dns_policies_api.block_domain_for_profiles(
            "network_123", "blocked.example.test", profiles=["p_1"], **kwargs
        )

        call_args = mock_session.request.call_args
        expected = {"domain": "blocked.example.test", "profiles": ["p_1"], **expected_extra}
        assert call_args.kwargs["json"] == expected


class TestGetProfileApplications:
    """Tests for get_profile_applications."""

    @pytest.mark.asyncio
    async def test_returns_raw_envelope(self, dns_policies_api, mock_session):
        """Test the raw envelope is returned unchanged."""
        data = {"applications": [], "categories_list": []}
        envelope = api_success_response(data)
        mock_session.request.return_value = create_mock_response(200, envelope)

        result = await dns_policies_api.get_profile_applications("network_123", "profile_1")

        assert result == envelope

    @pytest.mark.asyncio
    async def test_url(self, dns_policies_api, mock_session):
        """Test the literal path is used."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await dns_policies_api.get_profile_applications("network_123", "profile_1")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith(
            "/networks/network_123/dns_policies/profiles/profile_1/applications"
        )

    @pytest.mark.asyncio
    async def test_not_authenticated(self, dns_policies_api):
        """Test raises when not authenticated."""
        dns_policies_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await dns_policies_api.get_profile_applications("network_123", "profile_1")


class TestSetProfileBlockedApplications:
    """Tests for set_profile_blocked_applications."""

    @pytest.mark.asyncio
    async def test_sends_applications_field(self, dns_policies_api, mock_session):
        """Test the request body is {'applications': [...]}."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await dns_policies_api.set_profile_blocked_applications(
            "network_123", "profile_1", ["app_1", "app_2"]
        )

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.kwargs["json"] == {"applications": ["app_1", "app_2"]}
        assert call_args.args[1].endswith(
            "/networks/network_123/dns_policies/profiles/profile_1/applications/blocked"
        )

    @pytest.mark.asyncio
    async def test_warns_uncharacterised_write(self, dns_policies_api, mock_session, caplog):
        """Test the write logs the unconfirmed-write warning."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.WARNING):
            await dns_policies_api.set_profile_blocked_applications(
                "network_123", "profile_1", ["app_1"]
            )

        assert any("set blocked applications for profile" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_not_authenticated(self, dns_policies_api):
        """Test raises when not authenticated."""
        dns_policies_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await dns_policies_api.set_profile_blocked_applications(
                "network_123", "profile_1", ["app_1"]
            )
