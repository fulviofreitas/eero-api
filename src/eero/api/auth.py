"""Authentication API for Eero."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

import aiohttp
from aiohttp import ClientSession

from ..const import (
    ACCOUNT_ENDPOINT,
    API_ENDPOINT,
    LOGIN_ENDPOINT,
    LOGIN_VERIFY_ENDPOINT,
    LOGOUT_ENDPOINT,
    SESSION_TOKEN_KEY,
)
from ..exceptions import (
    EeroAPIException,
    EeroAuthenticationException,
    EeroNetworkException,
)
from .auth_storage import AuthCredentials, CredentialStorage, create_storage
from .base import BaseAPI

_LOGGER = logging.getLogger(__name__)


def _mask_sensitive(value: Optional[str], visible_chars: int = 8) -> str:
    """Mask sensitive data for logging, showing only first few characters.

    Args:
        value: The sensitive value to mask
        visible_chars: Number of characters to show before masking

    Returns:
        Masked string or 'None' if value is None
    """
    if not value:
        return "None"
    if len(value) <= visible_chars:
        return "*" * len(value)
    return f"{value[:visible_chars]}...***"


class AuthAPI(BaseAPI):
    """Authentication API for Eero."""

    def __init__(
        self,
        session: Optional[ClientSession] = None,
        cookie_file: Optional[str] = None,
        use_keyring: bool = True,
    ) -> None:
        """Initialize the AuthAPI.

        Args:
            session: Optional aiohttp ClientSession to use for requests
            cookie_file: Optional path to a file for storing authentication cookies
            use_keyring: Whether to use keyring for secure token storage
        """
        super().__init__(session, cookie_file, API_ENDPOINT)
        self._storage: CredentialStorage = create_storage(use_keyring, cookie_file)
        self._credentials = AuthCredentials()
        self._login_in_progress = False
        self._preferred_network_dirty = False

    @property
    def is_authenticated(self) -> bool:
        """Check if the client is authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        if self._credentials.has_valid_session():
            return True
        if self._credentials.session_id:
            _LOGGER.debug("Session expired")
        return False

    @property
    def preferred_network_id(self) -> Optional[str]:
        """Get the preferred network ID.

        Returns:
            Preferred network ID or None
        """
        return self._credentials.preferred_network_id

    @preferred_network_id.setter
    def preferred_network_id(self, value: str) -> None:
        """Set the preferred network ID.

        Args:
            value: Network ID to set as preferred

        Note:
            The preference is saved in memory and will be persisted
            when save_preferred_network() is called or on context exit.
        """
        self._credentials.preferred_network_id = value
        self._preferred_network_dirty = True

    async def save_preferred_network(self) -> None:
        """Save the preferred network ID if it was changed.

        Call this method to persist the preferred network setting.
        """
        if self._preferred_network_dirty:
            await self._storage.save(self._credentials)
            self._preferred_network_dirty = False

    async def __aenter__(self) -> "AuthAPI":
        """Enter async context manager."""
        await super().__aenter__()
        await self._load_credentials()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        await self.save_preferred_network()
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def _load_credentials(self) -> None:
        """Load authentication credentials from storage."""
        self._credentials = await self._storage.load()

        # Set session cookie if we have a valid session
        if self._credentials.session_id and not self._credentials.is_session_expired():
            self.session.cookie_jar.update_cookies({"s": self._credentials.session_id})
            _LOGGER.debug(
                "Loaded session cookie: s=%s",
                _mask_sensitive(self._credentials.session_id),
            )

    async def _save_credentials(self) -> None:
        """Save authentication credentials to storage."""
        await self._storage.save(self._credentials)

    async def login(self, user_identifier: str) -> bool:
        """Start the login process by requesting a verification code.

        Args:
            user_identifier: Email address or phone number for the Eero account

        Returns:
            True if login request was successful

        Raises:
            EeroAuthenticationException: If login fails
            EeroNetworkException: If there's a network error
        """
        # Clear any previous authentication data
        self._credentials.clear_all()
        self._login_in_progress = True

        # Save to ensure we don't have stale data
        await self._save_credentials()

        try:
            # Clear cookies to ensure fresh login
            self.session.cookie_jar.clear()

            _LOGGER.debug("Starting login process")

            response = await self.post(
                LOGIN_ENDPOINT,
                json={"login": user_identifier},
            )

            # Extract user_token from the nested structure
            self._credentials.user_token = response.get("data", {}).get("user_token")
            _LOGGER.debug(
                "Extracted user_token: %s",
                _mask_sensitive(self._credentials.user_token),
            )

            if not self._credentials.user_token:
                _LOGGER.error("Login failed: No user token received")
                return False

            # Save the token
            await self._save_credentials()

            return bool(self._credentials.user_token)
        except EeroAPIException as err:
            _LOGGER.error("Login failed: %s", err)
            raise EeroAuthenticationException(f"Login failed: {err}") from err
        except aiohttp.ClientError as err:
            error_msg = f"Network error during login: {err}"
            _LOGGER.error(error_msg)
            raise EeroNetworkException(error_msg) from err

    def _extract_network_id_from_response(self, response_data: Dict) -> Optional[str]:
        """Extract network ID from the response data.

        Args:
            response_data: Response data

        Returns:
            Network ID or None if not found
        """
        try:
            # Check for networks in the new format (networks list in data)
            networks = response_data.get("networks", {}).get("data", [])

            # If that's empty, try the old format (data.data array)
            if not networks:
                networks = response_data.get("data", [])

            # If still empty, bail out
            if not networks or not isinstance(networks, list) or len(networks) == 0:
                return None

            # Get the first network
            network = networks[0]

            # Try to get ID directly from the network
            network_id = network.get("id")
            if network_id:
                _LOGGER.debug("Found network ID directly: %s", network_id)
                return network_id

            # Try to extract from URL
            network_url = network.get("url")
            if network_url:
                # URL format is usually "/2.2/networks/network_id"
                parts = network_url.split("/")
                if len(parts) > 0:
                    network_id = parts[-1]
                    _LOGGER.debug("Extracted network ID from URL: %s", network_id)
                    return network_id
        except Exception as e:
            _LOGGER.warning("Error extracting network ID: %s", e)

        # Couldn't find network ID
        return None

    async def verify(self, verification_code: str) -> bool:
        """Verify login with the code sent to the user.

        Args:
            verification_code: The verification code sent to the user

        Returns:
            True if verification was successful

        Raises:
            EeroAuthenticationException: If verification fails
            EeroNetworkException: If there's a network error
        """
        if not self._credentials.user_token:
            raise EeroAuthenticationException("No user token available. Login first.")

        try:
            # Log the verification attempt (sensitive data masked)
            _LOGGER.debug(
                "Verifying with token: %s",
                _mask_sensitive(self._credentials.user_token),
            )
            _LOGGER.debug("Verification code: [REDACTED]")

            # Make sure we have the user token set as a cookie
            self.session.cookie_jar.update_cookies({"s": self._credentials.user_token})

            # Make the verification request
            response = await self.post(
                LOGIN_VERIFY_ENDPOINT,
                auth_token=self._credentials.user_token,
                json={"code": verification_code},
            )

            # Per the workflow, the user_token becomes the session token
            self._credentials.session_id = self._credentials.user_token

            # Set login not in progress
            self._login_in_progress = False

            # Extract user and network data if available
            try:
                response_data = response.get("data", {})

                # Extract network ID using helper method
                network_id = self._extract_network_id_from_response(response_data)
                if network_id:
                    self._credentials.preferred_network_id = network_id
                    _LOGGER.debug("Set preferred network ID")
            except Exception as e:
                _LOGGER.warning("Error parsing verification response: %s", e)

            # Set expiry to 30 days from now (typical session length)
            self._credentials.session_expiry = datetime.now().replace(microsecond=0) + timedelta(
                days=30
            )

            # Update session cookie for future requests
            if self._credentials.session_id:
                self.session.cookie_jar.update_cookies({"s": self._credentials.session_id})
                _LOGGER.debug(
                    "Updated session cookie: s=%s",
                    _mask_sensitive(self._credentials.session_id),
                )
                await self._save_credentials()
                return True

            _LOGGER.error("Verification succeeded but no session ID was set")
            return False

        except EeroAPIException as err:
            # Check for specific error codes
            if getattr(err, "status_code", 0) == 401:
                _LOGGER.error("Verification code incorrect")
                raise EeroAuthenticationException("Verification code incorrect") from err
            else:
                _LOGGER.error("Verification failed: %s", err)
                raise EeroAuthenticationException(f"Verification failed: {err}") from err
        except aiohttp.ClientError as err:
            error_msg = f"Network error during verification: {err}"
            _LOGGER.error(error_msg)
            raise EeroNetworkException(error_msg) from err

    async def resend_verification_code(self) -> bool:
        """Resend the verification code.

        Returns:
            True if resend was successful

        Raises:
            EeroAuthenticationException: If resend fails
            EeroNetworkException: If there's a network error
        """
        if not self._credentials.user_token:
            raise EeroAuthenticationException("No user token available. Login first.")

        try:
            _LOGGER.debug(
                "Resending verification code with token: %s",
                _mask_sensitive(self._credentials.user_token),
            )

            # Make sure we have the user token set as a cookie
            self.session.cookie_jar.update_cookies({"s": self._credentials.user_token})

            # Make the resend request
            await self.post(
                f"{LOGIN_ENDPOINT}/resend",
                auth_token=self._credentials.user_token,
                json={},
            )

            _LOGGER.info("Verification code resent successfully")
            return True
        except EeroAPIException as err:
            _LOGGER.error("Failed to resend verification code: %s", err)
            return False
        except aiohttp.ClientError as err:
            error_msg = f"Network error during resend: {err}"
            _LOGGER.error(error_msg)
            raise EeroNetworkException(error_msg) from err

    async def logout(self) -> bool:
        """Log out from the Eero API.

        Returns:
            True if logout was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroNetworkException: If there's a network error
        """
        if not self.is_authenticated:
            _LOGGER.warning("Attempted to logout when not authenticated")
            return False

        try:
            await self.post(
                LOGOUT_ENDPOINT,
                auth_token=self._credentials.session_id,
                json={},  # Empty payload for logout
            )

            # Clear session data (preserves preferred_network_id)
            self._credentials.clear_all()

            # Clear cookies
            self.session.cookie_jar.clear()

            # Update storage
            await self._save_credentials()
            return True
        except EeroAPIException as err:
            _LOGGER.error("Logout failed: %s", err)
            return False
        except aiohttp.ClientError as err:
            raise EeroNetworkException(f"Network error during logout: {err}") from err

    async def refresh_session(self) -> bool:
        """Refresh the session using the refresh token.

        Returns:
            True if session refresh was successful

        Raises:
            EeroAuthenticationException: If refresh fails
            EeroNetworkException: If there's a network error
        """
        if not self._credentials.refresh_token:
            raise EeroAuthenticationException("No refresh token available")

        try:
            response = await self.post(
                f"{ACCOUNT_ENDPOINT}/refresh",
                json={"refresh_token": self._credentials.refresh_token},
            )

            response_data = response.get("data", {})
            self._credentials.session_id = response_data.get(SESSION_TOKEN_KEY)
            self._credentials.refresh_token = response_data.get("refresh_token")

            # Set expiry to 30 days from now
            self._credentials.session_expiry = datetime.now().replace(microsecond=0) + timedelta(
                days=30
            )

            # Update session cookie for future requests
            if self._credentials.session_id:
                self.session.cookie_jar.update_cookies({"s": self._credentials.session_id})
                await self._save_credentials()
                return True
            return False
        except EeroAPIException as err:
            _LOGGER.error("Session refresh failed: %s", err)
            # Clear all tokens on failure
            self._credentials.clear_all()
            await self._save_credentials()
            return False
        except aiohttp.ClientError as err:
            raise EeroNetworkException(f"Network error during session refresh: {err}") from err

    async def ensure_authenticated(self) -> bool:
        """Ensure the client is authenticated, refreshing if necessary.

        Returns:
            True if authenticated, False otherwise
        """
        if not self.is_authenticated:
            return False

        # Check if session needs refresh
        if (
            self._credentials.session_expiry
            and datetime.now() > self._credentials.session_expiry
            and self._credentials.refresh_token
        ):
            _LOGGER.debug("Session expired, attempting to refresh")
            return await self.refresh_session()

        return True

    async def get_auth_token(self) -> Optional[str]:
        """Get the current authentication token.

        Returns:
            Current authentication token or None
        """
        if await self.ensure_authenticated():
            return self._credentials.session_id
        return None

    async def clear_auth_data(self) -> None:
        """Clear all authentication data."""
        self._credentials.clear_all()
        self._login_in_progress = False

        # Clear cookies
        self.session.cookie_jar.clear()

        # Save cleared data
        await self._save_credentials()

        _LOGGER.debug("Cleared all authentication data")
