"""Reject unintended password values before any request at either public layer."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.networks import NetworksAPI
from eero.client import EeroClient
from eero.exceptions import EeroValidationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture(params=["resource", "client"])
def password_api(request, mock_session):
    if request.param == "client":
        api = EeroClient(session=mock_session, use_keyring=False)
        api._preferred_network_id = "n1"
        auth = api._api.auth
    else:
        auth = MagicMock()
        auth.session = mock_session
        api = NetworksAPI(auth)
    auth.get_auth_token = AsyncMock(return_value="token")
    return api, auth


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["set_network_password", "set_guest_password"])
@pytest.mark.parametrize(
    "password",
    [None, "", False, 0, 123, b"bytes-password", [], {}],
    ids=["none", "empty", "bool", "zero", "number", "bytes", "list", "dict"],
)
async def test_invalid_password_sends_no_request(password_api, mock_session, method, password):
    api, auth = password_api
    args = (password,) if isinstance(api, EeroClient) else ("n1", password)
    with pytest.raises(EeroValidationException, match="password.*non-empty string"):
        await getattr(api, method)(*args)
    auth.get_auth_token.assert_not_awaited()
    mock_session.request.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,suffix",
    [("set_network_password", "password"), ("set_guest_password", "guestnetwork/password")],
)
@pytest.mark.parametrize("password", ["ordinary-password", "  preserve spaces  ", "None"])
async def test_valid_password_is_forwarded_unchanged(
    password_api, mock_session, method, suffix, password
):
    api, auth = password_api
    mock_session.request.return_value = create_mock_response(200, api_success_response({}))
    args = (password,) if isinstance(api, EeroClient) else ("n1", password)
    await getattr(api, method)(*args)
    auth.get_auth_token.assert_awaited_once()
    call = mock_session.request.call_args
    assert call.args == ("PUT", f"https://api-user.e2ro.com/2.2/networks/n1/{suffix}")
    assert call.kwargs["data"] == {"password": password}
    assert "json" not in call.kwargs
