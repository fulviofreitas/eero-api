"""Deterministic worker ordering and cancellation checks without a live keyring."""

import asyncio
import os
import threading
from unittest.mock import patch

import pytest

from eero.api.auth_storage import AuthCredentials, FileStorage, KeyringStorage


@pytest.mark.asyncio
async def test_keyring_worker_does_not_block_the_event_loop():
    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    release = threading.Event()
    main_thread = threading.get_ident()

    def slow_read(*args):
        assert threading.get_ident() != main_thread
        loop.call_soon_threadsafe(started.set)
        assert release.wait(5)
        return None

    with patch("eero.api.auth_storage.keyring.get_password", side_effect=slow_read):
        task = asyncio.create_task(KeyringStorage().load())
        try:
            await asyncio.wait_for(started.wait(), 2)
            heartbeat = asyncio.Event()
            loop.call_soon(heartbeat.set)
            await asyncio.wait_for(heartbeat.wait(), 2)
            assert not task.done()
        finally:
            release.set()
            await task


@pytest.mark.asyncio
async def test_cancelled_save_finishes_before_queued_clear(tmp_path):
    storage = FileStorage(str(tmp_path / "credentials"))
    loop = asyncio.get_running_loop()
    started, clear_queued = asyncio.Event(), asyncio.Event()
    release = threading.Event()
    original = os.fsync

    def blocked_fsync(fd):
        loop.call_soon_threadsafe(started.set)
        assert release.wait(5)
        original(fd)

    async def clear():
        clear_queued.set()
        await storage.clear()

    with patch("eero.api.auth_storage.os.fsync", blocked_fsync):
        saving = asyncio.create_task(storage.save(AuthCredentials("new")))
        clearing = None
        try:
            await asyncio.wait_for(started.wait(), 2)
            saving.cancel()
            clearing = asyncio.create_task(clear())
            await asyncio.wait_for(clear_queued.wait(), 2)
            assert not clearing.done()
            assert not saving.done()
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await saving
            if clearing is not None:
                await clearing
    assert (await storage.load()).session_id is None
