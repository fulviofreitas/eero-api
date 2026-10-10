"""Regression coverage for authenticated account reads and discovery failures."""

from unittest.mock import AsyncMock

import pytest

from eero.client import EeroClient
from eero.exceptions import EeroAuthenticationException, EeroRateLimitException

from .conftest import api_error_response, api_success_response, create_mock_response


@pytest.mark.asyncio
async def test_account_refreshes_and_replays_once(mock_session):
    client = EeroClient(session=mock_session, use_keyring=False)
    client._api.auth._credentials.session_id = "established"
    client._api.auth.refresh_session = AsyncMock(return_value=True)
    client._api.account._refresh_hook = client._api.auth.refresh_session
    expected = api_success_response({"name": "Account"})
    mock_session.request.side_effect = [
        create_mock_response(401, api_error_response(401, "error.session.refresh")),
        create_mock_response(200, expected),
    ]
    assert await client.get_account() == expected
    client._api.auth.refresh_session.assert_awaited_once()
    assert mock_session.request.call_count == 2
    assert all(call.args[1].endswith("/account") for call in mock_session.request.call_args_list)


@pytest.mark.asyncio
async def test_missing_session_refuses_account_before_request(mock_session):
    client = EeroClient(session=mock_session, use_keyring=False)
    with pytest.raises(EeroAuthenticationException):
        await client.get_account()
    mock_session.request.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [EeroAuthenticationException("expired"), EeroRateLimitException("limited")]
)
async def test_discovery_failure_is_raised_and_not_cached(error):
    client = EeroClient(use_keyring=False)
    client._api.networks.get_networks = AsyncMock(
        return_value=api_success_response({"networks": []})
    )
    client._api.account.get_account = AsyncMock(side_effect=error)
    for _ in range(2):
        with pytest.raises(type(error)):
            await client.get_networks()
    assert client._api.networks.get_networks.await_count == 2
    assert client._cache["networks"]["data"] is None


@pytest.mark.asyncio
async def test_empty_account_remains_a_success():
    client = EeroClient(use_keyring=False)
    empty = api_success_response({"networks": []})
    client._api.networks.get_networks = AsyncMock(return_value=empty)
    client._api.account.get_account = AsyncMock(return_value=empty)
    assert await client.get_networks() == empty
    assert await client.get_networks() == empty
    client._api.networks.get_networks.assert_awaited_once()
