"""Credential storage backends for Eero authentication.

This module provides storage backends for persisting the session token:
- KeyringStorage: Uses OS keyring for secure credential storage
- FileStorage: Uses JSON file with restricted permissions
- MemoryStorage: In-memory only, no persistence (for testing/ephemeral use)
- ChainedStorage: Tries a primary backend, falling back to a secondary one

v2.0 credential schema: the only value ever persisted is the session token
itself (as ``session_id``). There is no client-observable session expiry and
no client-held refresh token -- refreshing a session reuses the current
session token (see ``AuthAPI.refresh_session``). Records written before this
schema existed are migrated in place the first time they are loaded.

``KeyringStorage`` and ``FileStorage`` do blocking I/O (keyring calls, ``open``,
``fsync``, ``os.replace``). Each ``load``/``save``/``clear`` runs as one
synchronous unit on a worker thread, so a slow keyring or disk never stalls the
event loop; see :class:`_ThreadOffloadStorage` for the locking and cancellation
semantics.
"""

import asyncio
import json
import os
import stat
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

import keyring

from ..const import CREDENTIAL_SCHEMA_VERSION
from ..logging import get_secure_logger

_LOGGER = get_secure_logger(__name__)

_T = TypeVar("_T")


@dataclass
class AuthCredentials:
    """Container for the session token.

    Note: User preferences (like preferred_network_id) should be managed
    by the consuming application, not stored with auth credentials.

    ``session_id`` is excluded from ``repr()`` so the token cannot leak
    through a log line, an f-string or a traceback that formats the record.
    Equality and ``to_dict()``/``from_dict()`` still include it.
    """

    session_id: Optional[str] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to the persisted record shape.

        Returns:
            A dictionary with the session token and the current
            ``schema_version`` marker.
        """
        return {
            "session_id": self.session_id,
            "schema_version": CREDENTIAL_SCHEMA_VERSION,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuthCredentials":
        """Create from an already-current (``schema_version`` present) record.

        Args:
            data: A previously-persisted record carrying ``schema_version``.

        Returns:
            The corresponding ``AuthCredentials``.
        """
        return cls(session_id=data.get("session_id"))

    def clear_all(self) -> None:
        """Clear the stored session token."""
        self.session_id = None


def _log_migration_readback(backend_name: str, matched: bool) -> None:
    """Log the outcome of a post-migration read-back check.

    Never logs the credential values themselves -- only whether the record
    read back from the backend after a legacy-record migration matches what
    was just written.

    Args:
        backend_name: Human-readable name of the storage backend, used only
            in the log message (e.g. ``"keyring"``, ``"file"``).
        matched: Whether the read-back record's session token matched the
            migrated in-memory credentials.
    """
    if matched:
        _LOGGER.debug("Migration read-back verified for %s storage", backend_name)
    else:
        _LOGGER.warning(
            "Migration read-back did not match for %s storage; "
            "in-memory credentials are still returned to the caller",
            backend_name,
        )


def _parse_stored_record(data: Dict[str, Any]) -> Tuple[AuthCredentials, bool]:
    """Parse a raw stored credential record, migrating legacy shapes.

    A record written before the ``schema_version`` marker existed may carry
    a legacy ``user_token`` field instead of ``session_id``, alongside
    now-unsupported fields such as ``refresh_token`` / ``session_expiry``.
    Those extra fields are dropped -- only the token itself is retained.

    Args:
        data: The raw JSON-decoded record.

    Returns:
        A tuple of ``(credentials, migrated)`` where ``migrated`` is True
        when the record predated the ``schema_version`` marker and required
        conversion to the current shape.
    """
    if "schema_version" in data:
        return AuthCredentials.from_dict(data), False
    session_id = data.get("session_id") or data.get("user_token")
    return AuthCredentials(session_id=session_id), True


class CredentialStorage(ABC):
    """Abstract base class for credential storage backends."""

    @abstractmethod
    async def load(self) -> AuthCredentials:
        """Load credentials from storage.

        Returns:
            AuthCredentials instance (``session_id`` is None if not found)
        """
        pass

    @abstractmethod
    async def save(self, credentials: AuthCredentials) -> bool:
        """Save credentials to storage without raising.

        A backend can report success without retaining anything (a no-op or
        failing keyring), so the return value reflects what a read-back
        found, not whether the write call raised. Callers that do not care
        may ignore it.

        Args:
            credentials: The credentials to save

        Returns:
            True if the backend now holds the saved session token (verified
            by reading it back where the backend can lose a write), False if
            nothing was retained. A ``MemoryStorage`` record counts as
            retained even though it does not outlive the process. Backends
            written against the earlier ``-> None`` contract may still return
            ``None``; callers treat that as "unknown, assume persisted".
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all stored credentials."""
        pass


async def _retains(storage: CredentialStorage, credentials: AuthCredentials) -> bool:
    """Read a backend back and report whether it holds the given session token.

    A read that raises counts as "not retained" -- not every backend is
    guaranteed to swallow its own read errors.

    Args:
        storage: The backend to read back.
        credentials: The credentials that were just saved to it.

    Returns:
        True if the backend's stored ``session_id`` equals the saved one.
    """
    try:
        loaded = await storage.load()
    except Exception as e:  # pylint: disable=broad-exception-caught
        _LOGGER.debug("Storage verification read failed: %s", e)
        return False
    return loaded.session_id == credentials.session_id


class _ThreadOffloadStorage(CredentialStorage):
    """Base for backends whose ``load``/``save``/``clear`` block on I/O.

    Subclasses implement each operation as a plain synchronous method and run
    it through :meth:`_offload`, which executes the whole unit -- including any
    read-back or in-place migration -- on a worker thread via
    ``asyncio.to_thread``. That is one thread hop per public operation, and a
    synchronous unit never awaits, so it cannot re-enter the lock below.

    Operations on one instance are serialised by an ``asyncio.Lock`` held for
    the whole thread hop, so a ``save()`` and a ``clear()`` cannot interleave
    and the last one awaited wins. Different instances (for example two
    ``FileStorage`` objects on the same path) are not coordinated with each
    other, exactly as before.

    Cancellation: cancelling the task that awaits an operation does not stop a
    thread that is already running. The thread runs to completion (a ``save()``
    still finishes its atomic replace, so the destination holds either the old
    or the new record, never a partial one), and the lock stays held until it
    does, so a later operation on the same instance waits for it rather than
    racing it. Only an operation still waiting for the lock is cancelled
    outright, before any work starts. The cancelled caller never sees the
    outcome.

    The lock is per event loop. It is created lazily on first use, not in
    ``__init__``, so constructing a backend never binds to a loop, and it is
    replaced when the instance is next used from a different running loop
    (for example a second ``asyncio.run()``).
    """

    def __init__(self) -> None:
        """Initialize the (lazily created) per-loop operation lock."""
        self._op_lock: Optional[asyncio.Lock] = None
        self._op_lock_loop: Optional[asyncio.AbstractEventLoop] = None

    def _lock_for_running_loop(self) -> asyncio.Lock:
        """Return this instance's lock for the running loop, creating it lazily.

        Returns:
            The lock bound to the currently running event loop.
        """
        loop = asyncio.get_running_loop()
        if self._op_lock is None or self._op_lock_loop is not loop:
            self._op_lock = asyncio.Lock()
            self._op_lock_loop = loop
        return self._op_lock

    async def _offload(self, func: Callable[..., _T], *args: Any) -> _T:
        """Run a synchronous unit of work on a worker thread under the lock.

        The lock is released by the thread's completion callback rather than
        by this coroutine unwinding, so a cancelled caller cannot free it
        while the thread is still running.

        Args:
            func: The synchronous operation. It must not raise for expected
                failures (the concrete operations log and swallow them).
            *args: Positional arguments for ``func``.

        Returns:
            Whatever ``func`` returned.
        """
        lock = self._lock_for_running_loop()
        await lock.acquire()
        try:
            work = asyncio.ensure_future(asyncio.to_thread(func, *args))
        except BaseException:
            lock.release()
            raise
        work.add_done_callback(lambda done: _release_after(lock, done))
        return await asyncio.shield(work)

    async def _offload_save(self, credentials: AuthCredentials) -> bool:
        """Run ``self._save_sync`` offloaded, preserving ``save()``'s no-raise contract.

        The synchronous body already swallows every failure of the write. This
        additionally covers the offload itself failing to start (for example a
        worker thread that cannot be created), which would otherwise surface
        as an exception from ``save()``. Cancellation still propagates.

        Args:
            credentials: The credentials to save.

        Returns:
            The synchronous body's result, or False if it could not run.
        """
        try:
            return await self._offload(self._save_sync, credentials)
        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.error("Error saving credentials off the event loop: %s", e)
            return False

    def _save_sync(self, credentials: AuthCredentials) -> bool:
        """Blocking body of ``save()``; subclasses implement it.

        Args:
            credentials: The credentials to save.

        Returns:
            True if a read-back found the saved session token.
        """
        raise NotImplementedError


def _release_after(lock: asyncio.Lock, done: "asyncio.Future[Any]") -> None:
    """Release the operation lock once its worker thread has finished.

    Also retrieves the result's exception so an abandoned (cancelled-caller)
    operation that failed does not log "exception was never retrieved".

    Args:
        lock: The lock held for the finished operation.
        done: The completed worker future.
    """
    lock.release()
    if not done.cancelled():
        done.exception()


class KeyringStorage(_ThreadOffloadStorage):
    """Credential storage using OS keyring for secure storage.

    Keyring calls run on a worker thread, serialised per instance (see
    :class:`_ThreadOffloadStorage`).
    """

    SERVICE_NAME = "eero-api"
    ACCOUNT_NAME = "auth-tokens"

    def __init__(self, *, warn_on_unpersisted: bool = True) -> None:
        """Initialize keyring storage.

        Args:
            warn_on_unpersisted: Log a WARNING when ``save()`` finds that the
                keyring retained nothing. ``create_storage()`` turns this off
                when a file fallback is layered behind the keyring, where an
                unretained keyring write is routine and handled.
        """
        super().__init__()
        self._warn_on_unpersisted = warn_on_unpersisted

    async def load(self) -> AuthCredentials:
        """Load credentials from keyring, migrating a legacy record in place.

        When a legacy record is migrated, the write is read back and
        compared against the migrated in-memory credentials; the outcome is
        logged at DEBUG (match) or WARNING (mismatch), never the values
        themselves (see :func:`_log_migration_readback`). The in-memory
        credentials are returned to the caller either way -- a failed
        read-back does not fail the load.

        Runs on a worker thread, migration and read-back included, as one
        unit under the instance lock.
        """
        return await self._offload(self._load_sync)

    def _load_sync(self) -> AuthCredentials:
        """Blocking body of :meth:`load`; runs on a worker thread."""
        try:
            token_data = keyring.get_password(self.SERVICE_NAME, self.ACCOUNT_NAME)
            if token_data:
                data = json.loads(token_data)
                credentials, migrated = _parse_stored_record(data)

                if migrated:
                    _LOGGER.debug("Migrated legacy credential record in keyring storage")
                    _log_migration_readback("keyring", self._save_sync(credentials))

                return credentials
        # Keyring backends raise arbitrary, backend-specific exception types
        # (not just keyring.errors.*), so a broad catch is intentional here.
        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.debug("Error loading from keyring: %s", e)

        return AuthCredentials()

    async def save(self, credentials: AuthCredentials) -> bool:
        """Save credentials to keyring and verify them by reading them back.

        Never raises. A backend that raises, or that reports success without
        retaining anything (e.g. ``keyring.backends.null.Keyring``), leaves
        nothing persisted; that is logged at WARNING with fixed text (never
        the token) unless ``warn_on_unpersisted`` is off.

        Runs on a worker thread, read-back included, as one unit under the
        instance lock.

        Args:
            credentials: The credentials to save.

        Returns:
            True if the read-back matches the saved session token.
        """
        return await self._offload_save(credentials)

    def _save_sync(self, credentials: AuthCredentials) -> bool:
        """Blocking body of :meth:`save`; runs on a worker thread."""
        try:
            keyring.set_password(
                self.SERVICE_NAME, self.ACCOUNT_NAME, json.dumps(credentials.to_dict())
            )
            readback = keyring.get_password(self.SERVICE_NAME, self.ACCOUNT_NAME)
            persisted = False
            if readback:
                stored = _parse_stored_record(json.loads(readback))[0]
                persisted = stored.session_id == credentials.session_id
        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.debug("Error saving to keyring: %s", e)
            persisted = False

        if persisted:
            _LOGGER.debug("Saved authentication data to keyring")
        elif self._warn_on_unpersisted:
            _LOGGER.warning(
                "Keyring did not retain the session; credentials are not persisted "
                "and will be lost when this process exits"
            )
        return persisted

    async def clear(self) -> None:
        """Clear credentials from keyring (on a worker thread, under the lock)."""
        await self._offload(self._clear_sync)

    def _clear_sync(self) -> None:
        """Blocking body of :meth:`clear`; runs on a worker thread."""
        try:
            keyring.delete_password(self.SERVICE_NAME, self.ACCOUNT_NAME)
            _LOGGER.debug("Cleared authentication data from keyring")
        except keyring.errors.PasswordDeleteError:
            # Password didn't exist, that's fine
            pass
        except Exception as e:
            _LOGGER.debug("Error clearing keyring: %s", e)


class FileStorage(_ThreadOffloadStorage):
    """Credential storage using JSON file with restricted permissions.

    File I/O runs on a worker thread, serialised per instance (see
    :class:`_ThreadOffloadStorage`).
    """

    def __init__(self, file_path: str) -> None:
        """Initialize file storage.

        Args:
            file_path: Path to the cookie/credential file
        """
        super().__init__()
        self._file_path = os.path.abspath(os.path.expanduser(file_path))

    @property
    def file_path(self) -> str:
        """Get the file path."""
        return self._file_path

    async def load(self) -> AuthCredentials:
        """Load credentials from file, migrating a legacy record in place.

        When a legacy record is migrated, the write is read back and
        compared against the migrated in-memory credentials; the outcome is
        logged at DEBUG (match) or WARNING (mismatch), never the values
        themselves (see :func:`_log_migration_readback`). The in-memory
        credentials are returned to the caller either way -- a failed
        read-back does not fail the load.

        Runs on a worker thread, migration and read-back included, as one
        unit under the instance lock.
        """
        return await self._offload(self._load_sync)

    def _load_sync(self) -> AuthCredentials:
        """Blocking body of :meth:`load`; runs on a worker thread."""
        try:
            if not os.path.exists(self._file_path):
                _LOGGER.debug("Cookie file not found: %s", self._file_path)
                return AuthCredentials()

            with open(self._file_path, "r") as f:
                data = json.load(f)

            credentials, migrated = _parse_stored_record(data)

            if migrated:
                _LOGGER.debug("Migrated legacy credential record in file storage")
                self._save_sync(credentials)
                readback_matched = False
                try:
                    with open(self._file_path, "r") as f:
                        readback_data = json.load(f)
                    readback_matched = (
                        _parse_stored_record(readback_data)[0].session_id == credentials.session_id
                    )
                except (OSError, json.JSONDecodeError):
                    readback_matched = False
                _log_migration_readback("file", readback_matched)

            return credentials

        except (FileNotFoundError, json.JSONDecodeError) as e:
            _LOGGER.debug("Error loading cookie file: %s", e)
            return AuthCredentials()
        except Exception as e:
            _LOGGER.warning("Unexpected error loading cookie file: %s", e)
            return AuthCredentials()

    async def save(self, credentials: AuthCredentials) -> bool:
        """Save credentials to file with restricted permissions.

        The record is first written to a fresh temporary file in the same
        directory as the destination, created via ``tempfile.mkstemp`` --
        which opens with ``O_CREAT | O_EXCL`` at mode 0600 under an
        unpredictable, collision-free name -- so no window exists where the
        file is briefly world/group readable, and two saves can never
        collide on the same temp name. An earlier revision derived the temp
        name from ``os.getpid()`` alone: a process that crashed mid-write
        left that file behind, and every later save from a new process that
        happened to reuse the same PID then failed outright on the
        ``O_EXCL`` open (silently, since the failure is caught and logged
        below) until the stale file was removed by hand. ``mkstemp``'s
        per-call-unique suffix makes that collision impossible. Once the
        payload is fully written and flushed, ``os.replace()`` atomically
        swaps it into ``file_path`` -- a process interrupted mid-write
        (crash, kill -9, power loss) leaves either the untouched previous
        record or nothing at all; it can never leave a truncated/partial
        record at the final path, unlike writing in place.

        The final path is refused when it already exists as a symlink (the
        same protection the previous in-place ``O_NOFOLLOW`` open provided):
        a symlink planted by another local user to redirect the write
        elsewhere is not followed, and nothing is written. The trailing
        ``chmod`` is kept as defense in depth in case the mode passed to
        ``os.open`` is not honoured verbatim on some platform/filesystem
        combination.

        The file is read back after the swap; the result is True only if the
        stored token matches the one saved. Never raises.

        The whole sequence, read-back included, runs on a worker thread as one
        unit under the instance lock. Cancelling the awaiting task does not
        interrupt it: the swap still completes, so the file holds either the
        previous record or the new one.

        Args:
            credentials: The credentials to save.

        Returns:
            True if the read-back matches the saved session token.
        """
        return await self._offload_save(credentials)

    def _save_sync(self, credentials: AuthCredentials) -> bool:
        """Blocking body of :meth:`save`; runs on a worker thread."""
        try:
            # Ensure directory exists
            cookie_dir = os.path.dirname(self._file_path) or "."
            os.makedirs(cookie_dir, exist_ok=True)

            # Refuse to write through a symlink at the final path -- same
            # semantics as the previous O_NOFOLLOW in-place open.
            if os.path.islink(self._file_path):
                raise OSError(f"Refusing to write through symlink: {self._file_path}")

            payload = json.dumps(credentials.to_dict()).encode("utf-8")

            fd, tmp_path = tempfile.mkstemp(
                dir=cookie_dir,
                prefix=f".{os.path.basename(self._file_path)}.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(payload)
                    f.flush()
                    os.fsync(f.fileno())

                # Defense in depth: re-assert restrictive permissions (owner
                # read/write only) in case the mode above wasn't fully
                # honoured.
                os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)

                os.replace(tmp_path, self._file_path)
            except BaseException:
                # Best-effort cleanup of the temporary file on any failure
                # (including the atomic replace itself) so a half-written
                # temp file never accumulates.
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise

            with open(self._file_path, "r") as f:
                readback = _parse_stored_record(json.load(f))[0]
            if readback.session_id != credentials.session_id:
                _LOGGER.warning("Credential file did not retain the saved session")
                return False

            _LOGGER.debug("Saved authentication data to %s", self._file_path)
            return True

        except Exception as e:
            _LOGGER.error("Error saving to file: %s", e)
            return False

    async def clear(self) -> None:
        """Clear the credential file (on a worker thread, under the lock)."""
        await self._offload(self._clear_sync)

    def _clear_sync(self) -> None:
        """Blocking body of :meth:`clear`; runs on a worker thread."""
        try:
            if os.path.exists(self._file_path):
                os.remove(self._file_path)
                _LOGGER.debug("Removed cookie file: %s", self._file_path)
        except Exception as e:
            _LOGGER.warning("Error removing cookie file: %s", e)


class MemoryStorage(CredentialStorage):
    """In-memory credential storage.

    Credentials are not persisted to disk or keyring. Useful for testing
    or ephemeral sessions where persistence is not needed.
    """

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self._credentials = AuthCredentials()

    async def load(self) -> AuthCredentials:
        """Load a copy of the credentials from memory.

        A copy, so mutating the returned object in place cannot change the
        stored record behind ``save()``/``clear()``'s back.
        """
        return replace(self._credentials)

    async def save(self, credentials: AuthCredentials) -> bool:
        """Save a copy of the credentials to memory.

        Args:
            credentials: The credentials to copy into storage.

        Returns:
            Always True: the record is held for the life of the process.
        """
        self._credentials = replace(credentials)
        return True

    async def clear(self) -> None:
        """Clear credentials from memory."""
        self._credentials = AuthCredentials()


class ChainedStorage(CredentialStorage):
    """Storage that tries multiple backends in order.

    Useful for trying keyring first, then falling back to file storage. Each
    underlying backend performs its own legacy-record migration on load (see
    ``KeyringStorage.load`` / ``FileStorage.load``); this class only decides
    which backend's result to use and keeps them in sync.
    """

    def __init__(self, primary: CredentialStorage, fallback: CredentialStorage) -> None:
        """Initialize chained storage.

        Args:
            primary: Primary storage backend (e.g., keyring)
            fallback: Fallback storage backend (e.g., file)
        """
        self._primary = primary
        self._fallback = fallback
        # Session token this instance last loaded from, promoted out of, or
        # wrote to the fallback. A later verified primary save may clear the
        # fallback only if it still holds this token (or the one just saved):
        # anything else was written by someone else and is not ours to delete.
        self._fallback_token_seen: Optional[str] = None

    async def load(self) -> AuthCredentials:
        """Load credentials, trying primary first then fallback.

        A record found only in the fallback is promoted into the primary
        and then removed from the fallback (single-writer invariant): after
        this call, at most one backend ever holds the live record, so a
        later credential-clearing write to the primary can never be
        "resurrected" by a stale copy still sitting in the fallback.
        """
        # Try primary first
        credentials = await self._primary.load()
        if credentials.session_id:
            return credentials

        # Fall back to secondary
        credentials = await self._fallback.load()
        if credentials.session_id:
            self._fallback_token_seen = credentials.session_id
            # Migrate to primary storage, then remove the now-duplicate
            # fallback copy so the primary is the sole owner going forward.
            # The fallback is cleared only once a read-back proves the
            # primary holds the record; backends swallow their own write
            # errors, so without the read-back a failed primary write would
            # destroy the only surviving copy.
            await self._primary.save(credentials)
            promoted = await self._primary.load()
            if promoted.session_id == credentials.session_id:
                await self._fallback.clear()
                self._fallback_token_seen = None
            else:
                _LOGGER.debug("Primary storage did not retain the promoted record; fallback kept")

        return credentials

    async def save(self, credentials: AuthCredentials) -> bool:
        """Save to primary storage, falling back only if primary fails.

        Only uses fallback storage if primary fails, to avoid duplicating
        credentials across multiple storage backends.

        A primary backend that swallows its own write errors (as every
        concrete ``CredentialStorage`` does) can return successfully without
        actually persisting anything - a lying or no-op keyring backend is
        indistinguishable from a working one by return value alone. To catch
        that, a successful primary write is verified with a read-back
        (mirroring the promotion logic in ``load()``); only a verified write
        skips the fallback. A raising read-back is treated as a failed
        verification, and ``save()`` never raises.

        After a verified primary write, the fallback record is cleared (best
        effort) so it cannot be resurrected by ``load()``'s promotion if the
        primary is wiped later -- but only when it is a record this instance
        superseded: the token it last loaded from, promoted out of, or wrote
        to the fallback, or the token just saved. A different session left
        there by another process (two processes sharing one cookie file, one
        without a working keyring) is left alone.

        Args:
            credentials: The credentials to save.

        Returns:
            True if the primary, or failing that the fallback, was read back
            holding the saved session token.
        """
        try:
            await self._primary.save(credentials)
        except Exception as e:
            _LOGGER.debug("Primary storage save failed, trying fallback: %s", e)
        else:
            if await _retains(self._primary, credentials):
                _LOGGER.debug("Saved to primary storage")
                await self._clear_superseded_fallback(credentials)
                return True
            _LOGGER.debug("Primary storage did not retain the saved record; trying fallback")

        try:
            await self._fallback.save(credentials)
        # save() must never raise -- a failed fallback is logged, not
        # propagated, so callers can't be broken by a storage backend.
        except Exception as fallback_error:  # pylint: disable=broad-exception-caught
            _LOGGER.error("Both primary and fallback storage failed: %s", fallback_error)
            return False
        _LOGGER.debug("Saved to fallback storage")
        retained = await _retains(self._fallback, credentials)
        if retained:
            self._fallback_token_seen = credentials.session_id
        return retained

    async def _clear_superseded_fallback(self, saved: AuthCredentials) -> None:
        """Best-effort removal of a fallback record the primary has superseded.

        The fallback is read back first and cleared only if its session token
        is the one this instance last saw there or the one just saved to the
        primary. A read that raises, an empty fallback, or a different token
        leaves it untouched.

        Args:
            saved: The credentials just verified in the primary.
        """
        try:
            held = (await self._fallback.load()).session_id
            if not held:
                return
            if held not in (self._fallback_token_seen, saved.session_id):
                _LOGGER.debug("Fallback holds a record this instance did not write; left in place")
                return
            await self._fallback.clear()
            self._fallback_token_seen = None
        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.debug("Could not clear superseded fallback record: %s", e)

    async def clear(self) -> None:
        """Clear both storages, each independently of the other.

        Both backends are always attempted. A backend that raises is logged
        at WARNING (fixed text, no details of the record) and does not stop
        the other from being cleared.

        Raises:
            Exception: The first backend's exception, only when BOTH backends
                raised (so nothing is known to have been cleared).
        """
        errors: list[Exception] = []
        for backend in (self._primary, self._fallback):
            try:
                await backend.clear()
            except Exception as e:  # pylint: disable=broad-exception-caught
                errors.append(e)
                _LOGGER.debug("Error clearing a storage backend: %s", e)
        if errors:
            _LOGGER.warning(
                "Could not clear every credential storage backend; "
                "a stored session may remain in the one that failed"
            )
            if len(errors) == 2:
                raise errors[0]


def create_storage(
    use_keyring: bool = True,
    cookie_file: Optional[str] = None,
) -> CredentialStorage:
    """Create appropriate credential storage based on configuration.

    Args:
        use_keyring: Whether to use keyring for storage
        cookie_file: Optional path to cookie file for fallback

    Returns:
        Configured CredentialStorage instance
    """
    if use_keyring and cookie_file:
        # Use chained storage: keyring with file fallback
        return ChainedStorage(
            primary=KeyringStorage(warn_on_unpersisted=False),
            fallback=FileStorage(cookie_file),
        )
    elif use_keyring:
        return KeyringStorage()
    elif cookie_file:
        return FileStorage(cookie_file)
    else:
        # No storage configured - use in-memory only
        # (useful for testing or ephemeral sessions)
        return MemoryStorage()
