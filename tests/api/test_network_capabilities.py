"""Capability inspection preserves availability and requirement semantics."""

from unittest.mock import AsyncMock

import pytest

from eero.client import EeroClient
from eero.exceptions import EeroAPIException


@pytest.fixture
def client():
    result = EeroClient()
    result.set_preferred_network("123")
    result._api.networks.get_network = AsyncMock()
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        "invalid",
        {},
        {"capabilities": None},
        {"capabilities": []},
        {"capabilities": "invalid"},
    ],
)
async def test_missing_or_malformed_directory(client, data):
    client._api.networks.get_network.return_value = {"data": data}
    assert await client.get_capabilities() == {}
    assert await client.is_capable("missing") is None
    assert await client.capability_blockers("missing") == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entry,expected",
    [
        (None, None),
        ([], None),
        ({}, None),
        ({"capable": 1}, None),
        ({"capable": "true"}, None),
        ({"capable": None}, None),
        ({"capable": True}, True),
        ({"capable": False}, False),
    ],
)
async def test_availability_requires_boolean(client, entry, expected):
    client._api.networks.get_network.return_value = {"data": {"capabilities": {"feature": entry}}}
    assert await client.is_capable("feature") is expected
    assert await client.is_capable("unknown") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entry",
    [None, [], {}, {"requirements": None}, {"requirements": []}, {"requirements": "invalid"}],
)
async def test_malformed_requirements(client, entry):
    client._api.networks.get_network.return_value = {"data": {"capabilities": {"feature": entry}}}
    assert await client.capability_blockers("feature") == []


@pytest.mark.asyncio
async def test_blockers_preserve_names_and_context(client):
    directory = {
        "feature": {
            "capable": False,
            "requirements": {
                "firmware": False,
                "hardware": None,
                "count": 0,
                "role": "",
                "supported": True,
                "gateway_model": "Trieste",
                "version": 2,
            },
        }
    }
    envelope = {"meta": {"code": 200}, "data": {"capabilities": directory, "other": 42}}
    client._api.networks.get_network.return_value = envelope
    assert await client.capability_blockers("feature") == ["firmware", "hardware", "count", "role"]
    assert await client.get_capabilities() == directory
    assert await client.get_network() == envelope


@pytest.mark.asyncio
async def test_cached_snapshot_refresh_and_mutation_isolation(client):
    client._api.networks.get_network.side_effect = [
        {"data": {"capabilities": {"feature": {"capable": True}}}},
        {"data": {"capabilities": {"feature": {"capable": False}}}},
    ]
    directory = await client.get_capabilities()
    directory["feature"]["capable"] = False
    assert await client.is_capable("feature") is True
    assert client._api.networks.get_network.await_count == 1
    assert (await client.get_capabilities(refresh_cache=True))["feature"]["capable"] is False
    assert client._api.networks.get_network.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("selection", ["explicit", "preferred", "discovered"])
async def test_network_selection(client, selection):
    client._api.networks.get_network.return_value = {"data": {"capabilities": {}}}
    client._api.networks.get_networks = AsyncMock(
        return_value={"data": {"networks": [{"id": "123"}]}}
    )
    if selection == "discovered":
        client._preferred_network_id = None
    await client.get_capabilities("123" if selection == "explicit" else None)
    client._api.networks.get_network.assert_awaited_once_with("123")
    assert client._api.networks.get_networks.await_count == (1 if selection == "discovered" else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,args",
    [("get_capabilities", ()), ("is_capable", ("feature",)), ("capability_blockers", ("feature",))],
)
async def test_errors_propagate(client, method, args):
    client._api.networks.get_network.side_effect = EeroAPIException(500, "service failure")
    with pytest.raises(EeroAPIException):
        await getattr(client, method)(*args)
