"""Control concurrent reads with events so invalidation races reproduce deterministically."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from eero.client import EeroClient

CASES = [
    (
        "get_network",
        (),
        "networks",
        "get_network",
        "network",
        "n1",
        "_invalidate_network_cache",
        ("n1",),
    ),
    (
        "get_eeros",
        (),
        "eeros",
        "get_eeros",
        "eeros",
        "n1_eeros",
        "_invalidate_eeros_cache",
        ("n1",),
    ),
    (
        "get_devices",
        (),
        "devices",
        "get_devices",
        "devices",
        "n1_devices",
        "_invalidate_device_cache",
        ("n1", "d1"),
    ),
    (
        "get_device",
        ("d1",),
        "devices",
        "get_device",
        "devices",
        "n1_d1",
        "_invalidate_device_cache",
        ("n1", "d1"),
    ),
    (
        "get_profiles",
        (),
        "profiles",
        "get_profiles",
        "profiles",
        "n1_profiles",
        "_invalidate_profiles_list_cache",
        ("n1",),
    ),
    (
        "get_profile",
        ("p1",),
        "profiles",
        "get_profile",
        "profiles",
        "n1_p1",
        "_invalidate_profile_cache",
        ("n1", "p1"),
    ),
    (
        "get_profile",
        ("p1",),
        "profiles",
        "get_profile",
        "profiles",
        "n1_p1",
        "_invalidate_all_profile_caches",
        ("n1",),
    ),
    ("get_account", (), "auth", "get", "account", None, "clear_cache", ()),
    (
        "get_networks",
        (),
        "networks",
        "get_networks",
        "networks",
        None,
        "clear_cache",
        (),
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=[f"{c[0]}-{c[6]}" for c in CASES])
@pytest.mark.parametrize("cached_before", [False, True])
async def test_invalidation_rejects_inflight_cache_fill(case, cached_before):
    reader, args, resource, api_method, key, subkey, invalidator, invalidate_args = case
    client = EeroClient(use_keyring=False)
    client._preferred_network_id = "n1"
    client._api.auth.get_auth_token = AsyncMock(return_value="token")
    started, release = asyncio.Event(), asyncio.Event()
    stale = {"meta": {"code": 200}, "data": {"networks": [{"id": "n1"}], "name": "old"}}
    fresh = {"meta": {"code": 200}, "data": {"networks": [{"id": "n1"}], "name": "new"}}

    async def delayed(*args, **kwargs):
        started.set()
        await release.wait()
        return stale

    request = AsyncMock(side_effect=delayed)
    setattr(getattr(client._api, resource), api_method, request)
    if cached_before:
        client._update_cache(key, subkey, fresh)
    read = getattr(client, reader)
    task = asyncio.create_task(read(*args, refresh_cache=True))
    try:
        await asyncio.wait_for(started.wait(), 2)
        getattr(client, invalidator)(*invalidate_args)
    finally:
        release.set()
    assert await task == stale
    assert client._get_from_cache(key, subkey) is None
    request.side_effect = None
    request.return_value = fresh
    assert await read(*args) == fresh
    assert await read(*args) == fresh
    assert request.await_count == 2


@pytest.mark.asyncio
async def test_public_write_cannot_be_undone_by_an_inflight_read():
    client = EeroClient(use_keyring=False)
    client._preferred_network_id = "n1"
    started, release = asyncio.Event(), asyncio.Event()
    stale = {"data": {"nickname": "old"}}
    fresh = {"data": {"nickname": "new"}}

    async def delayed(*args, **kwargs):
        started.set()
        await release.wait()
        return stale

    client._api.devices.get_device = AsyncMock(side_effect=delayed)
    client._api.devices.set_device_nickname = AsyncMock(return_value={"data": {}})
    task = asyncio.create_task(client.get_device("d1"))
    try:
        await asyncio.wait_for(started.wait(), 2)
        await client.set_device_nickname("d1", "new")
    finally:
        release.set()
    assert await task == stale
    client._api.devices.get_device.side_effect = None
    client._api.devices.get_device.return_value = fresh
    assert await client.get_device("d1") == fresh
    assert await client.get_device("d1") == fresh
    assert client._api.devices.get_device.await_count == 2
