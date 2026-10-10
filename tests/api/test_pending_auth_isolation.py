"""A pending token cannot authenticate resource reads or destroy stored sessions."""

from unittest.mock import AsyncMock

import pytest

from eero.api.auth import AuthAPI
from eero.api.auth_storage import AuthCredentials, MemoryStorage
from eero.api.networks import NetworksAPI
from eero.exceptions import EeroAuthenticationException


@pytest.mark.asyncio
async def test_pending_login_refuses_reads_and_refresh_without_touching_storage():
    storage = MemoryStorage()
    await storage.save(AuthCredentials("established"))
    auth = AuthAPI(use_keyring=False)
    auth._storage = storage
    await auth._load_credentials()
    auth.post = AsyncMock(return_value={"data": {"user_token": "pending"}})
    assert await auth.login("example@example.com")
    assert not auth.is_authenticated
    assert await auth.get_auth_token() is None
    with pytest.raises(EeroAuthenticationException):
        await NetworksAPI(auth).get_networks()
    assert not await auth.refresh_session()
    assert auth.post.await_count == 1
    assert (await storage.load()).session_id == "established"
    assert await auth.verify("123456")
    assert await auth.get_auth_token() == "pending"
    assert (await storage.load()).session_id == "pending"


@pytest.mark.asyncio
async def test_explicit_clear_removes_pending_and_stored_tokens():
    auth = AuthAPI(use_keyring=False)
    auth._storage = MemoryStorage()
    await auth.set_session_token("established")
    auth.post = AsyncMock(return_value={"data": {"user_token": "pending"}})
    await auth.login("example@example.com")
    await auth.clear_session_token()
    assert auth._credentials.session_id is None
    assert (await auth._storage.load()).session_id is None
    await auth.set_session_token("externally_verified")
    assert auth.is_authenticated


@pytest.mark.asyncio
async def test_memory_storage_copies_on_both_boundaries():
    storage = MemoryStorage()
    credentials = AuthCredentials("established")
    await storage.save(credentials)
    credentials.clear_all()
    loaded = await storage.load()
    assert loaded.session_id == "established"
    loaded.clear_all()
    assert (await storage.load()).session_id == "established"


@pytest.mark.asyncio
async def test_explicit_logout_clears_pending_and_durable_session():
    auth = AuthAPI(use_keyring=False)
    auth._storage = MemoryStorage()
    await auth.set_session_token("established")
    auth.post = AsyncMock(return_value={"data": {"user_token": "pending"}})
    await auth.login("example@example.com")
    assert await auth.logout()
    assert (await auth._storage.load()).session_id is None
    assert auth._credentials.session_id is None
    assert auth.post.await_count == 1


@pytest.mark.asyncio
async def test_client_pending_login_cannot_reuse_old_cached_resources():
    from eero.client import EeroClient

    client = EeroClient(use_keyring=False)
    await client.set_session_token("established")
    client._update_cache("network", "n", {"data": {"name": "Old account"}})
    client._api.auth.post = AsyncMock(return_value={"data": {"user_token": "pending"}})
    await client.login("example@example.com")
    with pytest.raises(EeroAuthenticationException):
        await client.get_network("n")


@pytest.mark.asyncio
async def test_old_refresh_failure_cannot_destroy_pending_login_or_durable_session():
    import asyncio

    auth = AuthAPI(use_keyring=False)
    auth._storage = MemoryStorage()
    await auth.set_session_token("established")
    started, release = asyncio.Event(), asyncio.Event()

    async def post(endpoint, **kwargs):
        if endpoint.endswith("/refresh"):
            started.set()
            await release.wait()
            raise EeroAuthenticationException(
                "old session expired", error_code="error.session.expired"
            )
        return {"data": {"user_token": "pending"}}

    auth.post = AsyncMock(side_effect=post)
    refreshing = asyncio.create_task(auth.refresh_session())
    await asyncio.wait_for(started.wait(), 2)
    await auth.login("example@example.com")
    release.set()
    assert not await refreshing
    assert auth._credentials.session_id == "pending"
    assert (await auth._storage.load()).session_id == "established"
