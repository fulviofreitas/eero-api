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
        """Load credentials from keyring, migrating a legacy record in place."""
        try:
            token_data = keyring.get_password(self.SERVICE_NAME, self.ACCOUNT_NAME)
            if token_data:
                data = json.loads(token_data)
                credentials, migrated = _parse_stored_record(data)

                if migrated:
                    _LOGGER.debug("Migrated legacy credential record in keyring storage")
                    await self.save(credentials)

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
        """Load credentials from file, migrating a legacy record in place."""
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

            return credentials

        except (FileNotFoundError, json.JSONDecodeError) as e:
            _LOGGER.debug("Error loading cookie file: %s", e)
            return AuthCredentials()
        except Exception as e:
            _LOGGER.warning("Unexpected error loading cookie file: %s", e)
            return AuthCredentials()

    async def save(self, credentials: AuthCredentials) -> None:
        """Save credentials to file with restricted permissions.

        The file is created (or truncated) via ``os.open`` with mode 0600
        applied at creation time -- there is no window where the file is
        briefly world/group readable, unlike ``open()`` + a later
        ``chmod()``. ``O_NOFOLLOW`` refuses to write through a symlink at
        ``file_path`` (e.g. one planted by another local user to redirect
        the write elsewhere): the open fails with ``OSError`` and nothing is
        written. The trailing ``chmod`` is kept as defense in depth in case
        a restrictive mode passed to ``os.open`` is not honoured verbatim on
        some platform/filesystem combination.
        """
        try:
            # Ensure directory exists
            cookie_dir = os.path.dirname(self._file_path)
            if cookie_dir:
                os.makedirs(cookie_dir, exist_ok=True)

            payload = json.dumps(credentials.to_dict()).encode("utf-8")
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
            fd = os.open(self._file_path, flags, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(payload)

            # Defense in depth: re-assert restrictive permissions (owner
            # read/write only) in case the mode above wasn't fully honoured.
            os.chmod(self._file_path, stat.S_IRUSR | stat.S_IWUSR)
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
        """
        try:
            await self._primary.save(credentials)
            _LOGGER.debug("Saved to primary storage")
        except Exception as e:
            _LOGGER.debug("Primary storage save failed, trying fallback: %s", e)
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
