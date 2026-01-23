"""Credential storage backends for Eero authentication.

This module provides storage backends for persisting authentication tokens:
- KeyringStorage: Uses OS keyring for secure credential storage
- FileStorage: Uses JSON file with restricted permissions
- MemoryStorage: In-memory only, no persistence (for testing/ephemeral use)
"""

import json
import logging
import os
import stat
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import keyring

_LOGGER = logging.getLogger(__name__)


@dataclass
class AuthCredentials:
    """Container for authentication credentials."""

    user_token: Optional[str] = None
    refresh_token: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    preferred_network_id: Optional[str] = None
    session_expiry: Optional[datetime] = None

    def is_session_expired(self) -> bool:
        """Check if the session has expired."""
        if self.session_expiry is None:
            return True
        return datetime.now() > self.session_expiry

    def has_valid_session(self) -> bool:
        """Check if we have a valid, non-expired session."""
        return bool(self.session_id and not self.is_session_expired())

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "user_token": self.user_token,
            "refresh_token": self.refresh_token,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "preferred_network_id": self.preferred_network_id,
            "session_expiry": (self.session_expiry.isoformat() if self.session_expiry else None),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuthCredentials":
        """Create from dictionary."""
        expiry = data.get("session_expiry")
        session_expiry = None
        if expiry:
            try:
                session_expiry = datetime.fromisoformat(expiry)
            except ValueError:
                _LOGGER.warning("Invalid session_expiry date format in stored credentials")

        return cls(
            user_token=data.get("user_token"),
            refresh_token=data.get("refresh_token"),
            session_id=data.get("session_id"),
            user_id=data.get("user_id"),
            preferred_network_id=data.get("preferred_network_id"),
            session_expiry=session_expiry,
        )

    def clear_session(self) -> None:
        """Clear session-related credentials."""
        self.session_id = None
        self.session_expiry = None

    def clear_all(self, include_preferences: bool = False) -> None:
        """Clear all credentials.

        Args:
            include_preferences: If True, also clear preferred_network_id.
                                Default False to preserve user preferences.
        """
        self.user_token = None
        self.refresh_token = None
        self.session_id = None
        self.user_id = None
        self.session_expiry = None
        if include_preferences:
            self.preferred_network_id = None


class CredentialStorage(ABC):
    """Abstract base class for credential storage backends."""

    @abstractmethod
    async def load(self) -> AuthCredentials:
        """Load credentials from storage.

        Returns:
            AuthCredentials instance (may have None values if not found)
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
        """Load credentials from keyring."""
        try:
            token_data = keyring.get_password(self.SERVICE_NAME, self.ACCOUNT_NAME)
            if token_data:
                data = json.loads(token_data)
                credentials = AuthCredentials.from_dict(data)

                # Clear expired sessions
                if credentials.is_session_expired() and credentials.session_id:
                    _LOGGER.debug("Session expired, clearing from keyring")
                    credentials.clear_session()
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
        """Load credentials from file."""
        try:
            if not os.path.exists(self._file_path):
                _LOGGER.debug("Cookie file not found: %s", self._file_path)
                return AuthCredentials()

            with open(self._file_path, "r") as f:
                data = json.load(f)
                credentials = AuthCredentials.from_dict(data)

                # Clear expired sessions
                if credentials.is_session_expired() and credentials.session_id:
                    _LOGGER.debug("Session expired, clearing from file")
                    credentials.clear_session()
                    await self.save(credentials)

                return credentials

        except (FileNotFoundError, json.JSONDecodeError) as e:
            _LOGGER.debug("Error loading cookie file: %s", e)
            return AuthCredentials()
        except Exception as e:
            _LOGGER.warning("Unexpected error loading cookie file: %s", e)
            return AuthCredentials()

    async def save(self, credentials: AuthCredentials) -> None:
        """Save credentials to file with restricted permissions."""
        try:
            # Ensure directory exists
            cookie_dir = os.path.dirname(self._file_path)
            if cookie_dir:
                os.makedirs(cookie_dir, exist_ok=True)

            # Write credentials
            with open(self._file_path, "w") as f:
                json.dump(credentials.to_dict(), f)

            # Set restrictive permissions (owner read/write only)
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

    Useful for trying keyring first, then falling back to file storage.
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
        """Load credentials, trying primary first then fallback."""
        # Try primary first
        credentials = await self._primary.load()
        if credentials.session_id:
            return credentials

        # Fall back to secondary
        credentials = await self._fallback.load()
        if credentials.session_id:
            # Migrate to primary storage
            await self._primary.save(credentials)

        return credentials

    async def save(self, credentials: AuthCredentials) -> None:
        """Save to both storages for consistency.

        Saves to both primary and fallback to ensure credentials are
        persisted even if one storage backend fails.
        """
        # Save to both storages - if primary fails, fallback still works
        try:
            await self._primary.save(credentials)
        except Exception as e:
            _LOGGER.debug("Primary storage save failed, continuing with fallback: %s", e)

        try:
            await self._fallback.save(credentials)
        except Exception as e:
            _LOGGER.debug("Fallback storage save failed: %s", e)

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
