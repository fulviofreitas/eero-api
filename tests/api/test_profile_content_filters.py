"""Verify the separate policy resource and flat POST, not the legacy profile view."""

from unittest.mock import AsyncMock

import pytest

from eero.client import EeroClient
from eero.exceptions import EeroAuthenticationException, EeroValidationException

from .conftest import api_success_response, create_mock_response


@pytest.mark.asyncio
async def test_policy_read_and_flat_post(mock_session):
    client = EeroClient(session=mock_session, use_keyring=False)
    client._api.auth._credentials.session_id = "established"
    envelope = api_success_response({"unified_content_filters": {"block_gaming_content": False}})
    mock_session.request.return_value = create_mock_response(200, envelope)
    assert await client.get_profile_dns_policies("p", network_id="/2.2/networks/n") == envelope
    read = mock_session.request.call_args
    assert read.args == ("GET", "https://api-user.e2ro.com/2.2/networks/n/dns_policies/profiles/p")
    flags = {"block_gaming_content": True, "block_pornographic_content": False}
    await client.set_profile_content_filters("p", flags, network_id="n")
    write = mock_session.request.call_args
    assert write.args[0] == "POST"
    assert write.args[1].endswith("/networks/n/dns_policies/profiles/p")
    assert write.kwargs["json"] == flags
    assert flags == {"block_gaming_content": True, "block_pornographic_content": False}


@pytest.mark.asyncio
@pytest.mark.parametrize("filters", [{}, {"unknown": True}, {"block_gaming_content": "false"}, []])
async def test_invalid_flags_refused_before_request(mock_session, filters):
    client = EeroClient(session=mock_session, use_keyring=False)
    with pytest.raises(EeroValidationException):
        await client.set_profile_content_filters("p", filters, network_id="n")
    mock_session.request.assert_not_called()


@pytest.mark.asyncio
async def test_policy_requires_authentication(mock_session):
    client = EeroClient(session=mock_session, use_keyring=False)
    with pytest.raises(EeroAuthenticationException):
        await client.get_profile_dns_policies("p", network_id="n")
    mock_session.request.assert_not_called()


@pytest.mark.asyncio
async def test_policy_write_invalidates_profile_cache():
    client = EeroClient(use_keyring=False)
    client._update_cache("profiles", "n_p", {"data": {"premium_dns": {}}})
    client._api.dns_policies.set_profile_content_filters = AsyncMock(
        return_value={"meta": {"code": 200}}
    )
    await client.set_profile_content_filters("p", {"block_gaming_content": True}, network_id="n")
    assert not client._is_cache_valid("profiles", "n_p")
