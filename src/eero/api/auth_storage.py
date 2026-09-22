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
"""

import json
import os
import stat
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import keyring

from ..const import CREDENTIAL_SCHEMA_VERSION
from ..logging import get_secure_logger

_LOGGER = get_secure_logger(__name__)


@dataclass
class AuthCredentials:
    """Container for the session token.

    Note: User preferences (like preferred_network_id) should be managed
    by the consuming application, not stored with auth credentials.
    """

    session_id: Optional[str] = None

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
    async def save(self, credentials: AuthCredentials) -> None:
        """Save credentials to storage.

        Args:
            credentials: The credentials to save
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all stored credentials."""
        pass


class KeyringStorage(CredentialStorage):
    """Credential storage using OS keyring for secure storage."""

    SERVICE_NAME = "eero-api"
    ACCOUNT_NAME = "auth-tokens"

    async def load(self) -> AuthCredentials:
        """Load credentials from keyring, migrating a legacy record in place.

        When a legacy record is migrated, the write is read back and
        compared against the migrated in-memory credentials; the outcome is
        logged at DEBUG (match) or WARNING (mismatch), never the values
        themselves (see :func:`_log_migration_readback`). The in-memory
        credentials are returned to the caller either way -- a failed
        read-back does not fail the load.
        """
        try:
            token_data = keyring.get_password(self.SERVICE_NAME, self.ACCOUNT_NAME)
            if token_data:
                data = json.loads(token_data)
                credentials, migrated = _parse_stored_record(data)

                if migrated:
                    _LOGGER.debug("Migrated legacy credential record in keyring storage")
                    await self.save(credentials)
                    readback_raw = keyring.get_password(self.SERVICE_NAME, self.ACCOUNT_NAME)
                    readback_matched = (
                        readback_raw is not None
                        and _parse_stored_record(json.loads(readback_raw))[0].session_id
                        == credentials.session_id
                    )
                    _log_migration_readback("keyring", readback_matched)

                return credentials
        except Exception as e:
            _LOGGER.debug("Error loading from keyring: %s", e)

        return AuthCredentials()

    async def save(self, credentials: AuthCredentials) -> None:
        """Save credentials to keyring."""
        try:
            data = json.dumps(credentials.to_dict())
            keyring.set_password(self.SERVICE_NAME, self.ACCOUNT_NAME, data)
            _LOGGER.debug("Saved authentication data to keyring")
        except Exception as e:
            # Log at debug level since file fallback works
            _LOGGER.debug("Error saving to keyring (using file fallback): %s", e)

    async def clear(self) -> None:
        """Clear credentials from keyring."""
        try:
            keyring.delete_password(self.SERVICE_NAME, self.ACCOUNT_NAME)
            _LOGGER.debug("Cleared authentication data from keyring")
        except keyring.errors.PasswordDeleteError:
            # Password didn't exist, that's fine
            pass
        except Exception as e:
            _LOGGER.debug("Error clearing keyring: %s", e)


class FileStorage(CredentialStorage):
    """Credential storage using JSON file with restricted permissions."""

    def __init__(self, file_path: str) -> None:
        """Initialize file storage.

        Args:
            file_path: Path to the cookie/credential file
        """
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
        """
        try:
            if not os.path.exists(self._file_path):
                _LOGGER.debug("Cookie file not found: %s", self._file_path)
                return AuthCredentials()

            with open(self._file_path, "r") as f:
                data = json.load(f)

            credentials, migrated = _parse_stored_record(data)

            if migrated:
                _LOGGER.debug("Migrated legacy credential record in file storage")
                await self.save(credentials)
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

    async def save(self, credentials: AuthCredentials) -> None:
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
        """
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

            _LOGGER.debug("Saved authentication data to %s", self._file_path)

        except Exception as e:
            _LOGGER.error("Error saving to file: %s", e)

    async def clear(self) -> None:
        """Clear the credential file."""
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
        """Load credentials from memory."""
        return self._credentials

    async def save(self, credentials: AuthCredentials) -> None:
        """Save credentials to memory."""
        self._credentials = credentials

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
            else:
                _LOGGER.debug("Primary storage did not retain the promoted record; fallback kept")

        return credentials

    async def save(self, credentials: AuthCredentials) -> None:
        """Save to primary storage, falling back only if primary fails.

        Only uses fallback storage if primary fails, to avoid duplicating
        credentials across multiple storage backends.

        A primary backend that swallows its own write errors (as every
        concrete ``CredentialStorage`` does) can return successfully without
        actually persisting anything - a lying or no-op keyring backend is
        indistinguishable from a working one by return value alone. To catch
        that, a successful primary write is verified with a read-back
        (mirroring the promotion logic in ``load()``); only a verified write
        skips the fallback.
        """
        try:
            await self._primary.save(credentials)
        except Exception as e:
            _LOGGER.debug("Primary storage save failed, trying fallback: %s", e)
            try:
                await self._fallback.save(credentials)
                _LOGGER.debug("Saved to fallback storage")
            except Exception as fallback_error:
                _LOGGER.error("Both primary and fallback storage failed: %s", fallback_error)
            return

        verified = await self._primary.load()
        if verified.session_id == credentials.session_id:
            _LOGGER.debug("Saved to primary storage")
            return

        _LOGGER.debug("Primary storage did not retain the saved record; trying fallback")
        try:
            await self._fallback.save(credentials)
            _LOGGER.debug("Saved to fallback storage")
        except Exception as fallback_error:
            _LOGGER.error("Both primary and fallback storage failed: %s", fallback_error)

    async def clear(self) -> None:
        """Clear both storages."""
        await self._primary.clear()
        await self._fallback.clear()


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
            primary=KeyringStorage(),
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
