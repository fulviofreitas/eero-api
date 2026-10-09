"""A login attempt must not replace a verified session before verification."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from eero.api.auth import AuthAPI
from eero.api.auth_storage import AuthCredentials, FileStorage
from eero.exceptions import (
    EeroAPIException,
    EeroAuthenticationException,
    EeroNetworkException,
)


@pytest.fixture
def stored_session(tmp_path):
    path = tmp_path / "credentials.json"
    path.write_text(json.dumps(AuthCredentials(session_id="working-session").to_dict()))
    api = AuthAPI(use_keyring=False)
    api._storage = FileStorage(str(path))
    api._credentials = AuthCredentials(session_id="working-session")
    return api, path


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["network", "api", "tokenless", "cancelled"])
async def test_failed_login_preserves_memory_and_stored_session(stored_session, failure):
    api, path = stored_session
    before = path.read_bytes()
    if failure == "tokenless":
        api.post = AsyncMock(return_value={"data": {}})
        assert await api.login("user@example.test") is False
    else:
        error = {
            "network": EeroNetworkException("offline"),
            "api": EeroAPIException(400, "rejected"),
            "cancelled": asyncio.CancelledError(),
        }[failure]
        api.post = AsyncMock(side_effect=error)
        expected = EeroAuthenticationException if failure == "api" else type(error)
        with pytest.raises(expected):
            await api.login("user@example.test")
    assert path.read_bytes() == before
    assert api._credentials.session_id == "working-session"
    assert api._login_in_progress is False


@pytest.mark.asyncio
async def test_pending_login_is_not_persisted_and_can_be_abandoned(stored_session):
    api, path = stored_session
    before = path.read_bytes()
    api.post = AsyncMock(return_value={"data": {"user_token": "pending-token"}})
    assert await api.login("user@example.test") is True
    assert api._credentials.session_id == "pending-token"
    assert api._login_in_progress is True
    assert path.read_bytes() == before
    # Another process still loads the verified session if the code is never entered.
    assert (await FileStorage(str(path)).load()).session_id == "working-session"


@pytest.mark.asyncio
async def test_only_successful_verification_replaces_stored_session(stored_session):
    api, path = stored_session
    before = path.read_bytes()
    api.post = AsyncMock(return_value={"data": {"user_token": "pending-token"}})
    await api.login("user@example.test")
    api.post = AsyncMock(side_effect=EeroAuthenticationException("wrong code"))
    with pytest.raises(EeroAuthenticationException):
        await api.verify("wrong")
    assert path.read_bytes() == before
    api.post = AsyncMock(return_value={"data": {"id": "user"}})
    assert await api.verify("correct") is True
    assert (await FileStorage(str(path)).load()).session_id == "pending-token"
    assert api._login_in_progress is False
