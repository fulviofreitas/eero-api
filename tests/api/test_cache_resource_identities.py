"""Follow-up cache regressions: identity, related writes and account boundaries."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from eero.client import EeroClient
from eero.exceptions import EeroException


@pytest.mark.asyncio
async def test_mac_spellings_share_cache_and_write_invalidation():
    client = EeroClient(use_keyring=False)
    client._api.devices.get_device = AsyncMock(return_value={"data": {"paused": False}})
    client._api.devices.pause_device = AsyncMock(return_value={"meta": {"code": 200}})
    await client.get_device("aabbccddeeff", network_id="n")
    await client.get_device("AA:BB:CC:DD:EE:FF", network_id="/2.2/networks/n")
    client._api.devices.get_device.assert_awaited_once()
    await client.pause_device("AA:BB:CC:DD:EE:FF", True, network_id="n")
    await client.get_device("aabbccddeeff", network_id="n")
    assert client._api.devices.get_device.await_count == 2


@pytest.mark.asyncio
async def test_profile_membership_invalidates_devices_and_old_profiles():
    client = EeroClient(use_keyring=False)
    client._update_cache("devices", "n_aabbccddeeff", {"data": {"profile": "old"}})
    client._update_cache("profiles", "n_old", {"data": {"devices": ["aabbccddeeff"]}})
    client._api.profiles.set_profile_devices = AsyncMock(return_value={"meta": {"code": 200}})
    await client.set_profile_devices(
        "new", ["/2.2/networks/n/devices/aabbccddeeff"], network_id="n"
    )
    assert not client._is_cache_valid("devices", "n_aabbccddeeff")
    assert not client._is_cache_valid("profiles", "n_old")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    [
        "create_schedule",
        "update_schedule",
        "delete_schedule",
        "clear_profile_schedule",
        "enable_bedtime",
    ],
)
async def test_schedule_writes_invalidate_cached_profile(method):
    client = EeroClient(use_keyring=False)
    client._update_cache("profiles", "n_p", {"data": {"schedule": []}})
    setattr(client._api.schedule, method, AsyncMock(return_value={"meta": {"code": 200}}))
    if method == "create_schedule":
        await client.create_schedule(
            "p", network_id="n", name="x", days=["Monday"], start="21:00", end="07:00"
        )
    elif method == "enable_bedtime":
        await client.enable_bedtime("p", "21:00", "07:00", network_id="n")
    elif method == "clear_profile_schedule":
        await client.clear_profile_schedule("p", network_id="n")
    elif method == "update_schedule":
        await client.update_schedule("/2.2/networks/n/profiles/p/schedules/s", enabled=False)
    else:
        await client.delete_schedule("/2.2/networks/n/profiles/p/schedules/s")
    assert not client._is_cache_valid("profiles", "n_p")


@pytest.mark.asyncio
async def test_session_change_forgets_discovered_network_but_retains_explicit_choice():
    client = EeroClient(use_keyring=False)
    client._api.networks.get_networks = AsyncMock(
        return_value={"data": {"networks": [{"id": "A"}]}}
    )
    await client.get_networks()
    assert client.preferred_network_id == "A"
    await client.set_session_token("account_B")
    assert client.preferred_network_id is None
    client.set_preferred_network("chosen")
    await client.set_session_token("account_C")
    assert client.preferred_network_id == "chosen"


@pytest.mark.asyncio
async def test_old_session_discovery_cannot_select_an_old_network():
    client = EeroClient(use_keyring=False)
    started, release = asyncio.Event(), asyncio.Event()

    async def held_read():
        started.set()
        await release.wait()
        return {"data": {"networks": [{"id": "A"}]}}

    client._api.networks.get_networks = AsyncMock(side_effect=held_read)
    read = asyncio.create_task(client.get_networks())
    await asyncio.wait_for(started.wait(), 2)
    await client.set_session_token("account_B")
    release.set()
    with pytest.raises(EeroException, match="Session changed"):
        await read
    assert client.preferred_network_id is None
    assert client._cache["networks"]["data"] is None


def test_expired_entries_are_pruned_when_other_keys_are_used():
    client = EeroClient(cache_timeout=10, use_keyring=False)
    with patch("eero.client.time.monotonic", return_value=100):
        client._update_cache("devices", "n_old", {"data": {"id": "old"}})
    with patch("eero.client.time.monotonic", return_value=111):
        client._update_cache("devices", "n_new", {"data": {"id": "new"}})
    assert "n_old" not in client._cache["devices"]
    assert "n_new" in client._cache["devices"]


@pytest.mark.asyncio
async def test_partial_schedule_clear_invalidates_after_failure():
    client = EeroClient(use_keyring=False)
    client._update_cache("profiles", "n_p", {"data": {"schedule": ["old"]}})
    client._api.schedule.clear_profile_schedule = AsyncMock(
        side_effect=EeroException("second delete failed")
    )
    with pytest.raises(EeroException):
        await client.clear_profile_schedule("p", network_id="n")
    assert not client._is_cache_valid("profiles", "n_p")


def test_non_device_identifiers_keep_case():
    assert EeroClient._cache_id("ABCDEF123456") == "ABCDEF123456"
    assert EeroClient._cache_id("ABCDEF123456", mac=True) == "abcdef123456"
