"""Read-only inventory and status endpoint contracts."""

import copy
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.networks import NetworksAPI
from eero.client import EeroClient
from eero.exceptions import EeroAPIException, EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def api(mock_session):
    auth = MagicMock()
    auth.session = mock_session
    auth.get_auth_token = AsyncMock(return_value="token")
    return NetworksAPI(auth)


@pytest.mark.asyncio
@pytest.mark.parametrize("method,suffix", [("get_clients", "clients"), ("get_status", "status")])
@pytest.mark.parametrize(
    "network", ["123", "/2.2/networks/123", "https://api-user.e2ro.com/2.2/networks/123"]
)
async def test_raw_read(api, mock_session, method, suffix, network):
    data = (
        [{"mac": "aa", "ips": ["192.168.1.2"], "unknown": True}]
        if suffix == "clients"
        else {"health": {"status": "green", "eeros": {"online": 2}}, "unknown": True}
    )
    response = api_success_response(data)
    mock_session.request.return_value = create_mock_response(200, response)
    parent = {"resources": {suffix: "/2.3/networks/other/incorrect"}}
    before = copy.deepcopy(parent)
    assert await getattr(api, method)(network, parent=parent) == response
    request = mock_session.request.call_args
    assert request.args == ("GET", f"https://api-user.e2ro.com/2.2/networks/123/{suffix}")
    assert parent == before


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get_clients", "get_status"])
async def test_authentication_required(api, mock_session, method):
    api._auth_api.get_auth_token.return_value = None
    with pytest.raises(EeroAuthenticationException):
        await getattr(api, method)("123")
    mock_session.request.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get_clients", "get_status"])
async def test_service_error_propagates(api, mock_session, method):
    mock_session.request.return_value = create_mock_response(
        400, {"meta": {"code": 400}, "error": "bad request"}
    )
    with pytest.raises(EeroAPIException):
        await getattr(api, method)("123")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,resource", [("get_clients", "get_clients"), ("get_network_status", "get_status")]
)
@pytest.mark.parametrize("selection", ["explicit", "preferred", "discovered"])
async def test_client_selection_and_fresh_reads(method, resource, selection):
    client = EeroClient()
    client._api.networks.get_networks = AsyncMock(
        return_value=api_success_response({"networks": [{"id": "123"}]})
    )
    if selection == "preferred":
        client.set_preferred_network("123")
    read = AsyncMock(
        side_effect=[api_success_response({"snapshot": 1}), api_success_response({"snapshot": 2})]
    )
    setattr(client._api.networks, resource, read)
    kwargs = {"network_id": "123"} if selection == "explicit" else {}
    first = await getattr(client, method)(**kwargs)
    second = await getattr(client, method)(**kwargs)
    assert first["data"]["snapshot"] == 1
    assert second["data"]["snapshot"] == 2
    assert read.await_count == 2
    read.assert_awaited_with("123")
    assert client._api.networks.get_networks.await_count == (1 if selection == "discovered" else 0)
