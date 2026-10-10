"""Storage must distinguish successful persistence from a usable in-memory session."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.auth import AuthAPI
from eero.api.auth_storage import (
    AuthCredentials,
    ChainedStorage,
    FileStorage,
    KeyringStorage,
    MemoryStorage,
)


@pytest.mark.asyncio
async def test_file_and_keyring_saves_raise_on_failure(tmp_path):
    with patch(
        "eero.api.auth_storage.keyring.set_password", side_effect=RuntimeError("unavailable")
    ):
        with pytest.raises(RuntimeError):
            await KeyringStorage().save(AuthCredentials("new"))
    with patch("eero.api.auth_storage.os.fsync", side_effect=OSError("full")):
        with pytest.raises(OSError):
            await FileStorage(str(tmp_path / "credentials")).save(AuthCredentials("new"))
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_successful_primary_retires_stale_fallback():
    primary, fallback = MemoryStorage(), MemoryStorage()
    await fallback.save(AuthCredentials("old"))
    storage = ChainedStorage(primary, fallback)
    await storage.save(AuthCredentials("new"))
    assert (await primary.load()).session_id == "new"
    assert (await fallback.load()).session_id is None


@pytest.mark.asyncio
async def test_noop_fallback_is_not_a_success():
    primary, fallback = AsyncMock(), AsyncMock()
    primary.load.return_value = AuthCredentials()
    fallback.load.return_value = AuthCredentials()
    with pytest.raises(OSError):
        await ChainedStorage(primary, fallback).save(AuthCredentials("new"))


@pytest.mark.asyncio
async def test_clear_attempts_fallback_when_primary_raises():
    primary, fallback = AsyncMock(), MemoryStorage()
    primary.clear.side_effect = OSError("locked")
    await fallback.save(AuthCredentials("old"))
    with pytest.raises(OSError):
        await ChainedStorage(primary, fallback).clear()
    assert (await fallback.load()).session_id is None


@pytest.mark.asyncio
async def test_auth_warns_and_keeps_usable_session_when_save_fails(caplog):
    auth = AuthAPI(use_keyring=False)
    auth._storage = AsyncMock()
    auth._storage.save.side_effect = OSError("full")
    await auth.set_session_token("new")
    assert await auth.get_auth_token() == "new"
    assert "Could not persist" in caplog.text


@pytest.mark.asyncio
async def test_failed_primary_replacement_cannot_shadow_new_fallback():
    primary, fallback = MemoryStorage(), MemoryStorage()
    await primary.save(AuthCredentials("old"))
    with patch.object(primary, "save", AsyncMock(side_effect=OSError("locked"))):
        storage = ChainedStorage(primary, fallback)
        await storage.save(AuthCredentials("new"))
        assert (await storage.load()).session_id == "new"


@pytest.mark.asyncio
async def test_legacy_load_keeps_token_when_migration_cannot_save(tmp_path):
    import json

    path = tmp_path / "credentials"
    path.write_text(json.dumps({"session_id": "old"}))
    storage = FileStorage(str(path))
    with patch.object(storage, "_save", side_effect=OSError("full")):
        assert (await storage.load()).session_id == "old"


@pytest.mark.asyncio
async def test_plain_noop_keyring_is_not_reported_as_persisted():
    with (
        patch("eero.api.auth_storage.keyring.set_password"),
        patch("eero.api.auth_storage.keyring.get_password", return_value=None),
    ):
        with pytest.raises(OSError, match="did not retain"):
            await KeyringStorage().save(AuthCredentials("new"))
