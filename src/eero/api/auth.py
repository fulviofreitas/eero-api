"""Authentication API for Eero."""

from datetime import datetime, timedelta
from typing import Optional

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
from ..logging import get_secure_logger
from .auth_storage import AuthCredentials, CredentialStorage, create_storage
from .base import BaseAPI

_LOGGER = get_secure_logger(__name__)


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

    async def __aenter__(self) -> "AuthAPI":
        """Enter async context manager."""
        await super().__aenter__()
        await self._load_credentials()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def _load_credentials(self) -> None:
        """Load authentication credentials from storage."""
        self._credentials = await self._storage.load()

        # Set session cookie if we have a valid session
        if self._credentials.session_id and not self._credentials.is_session_expired():
            self.session.cookie_jar.update_cookies({"s": self._credentials.session_id})
            _LOGGER.debug("Loaded session cookie from storage")

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

            # Extract user_token from API response and store as session_id
            # (it becomes the session token after verification)
            user_token = response.get("data", {}).get("user_token")
            _LOGGER.debug(
                "User token %s",
                "received" if user_token else "not received",
            )

            if not user_token:
                _LOGGER.error("Login failed: No user token received")
                return False

            # Store as session_id (will be validated after verify_login)
            self._credentials.session_id = user_token

            # Save the token (session_expiry is None until verified)
            await self._save_credentials()

            return True
        except EeroAPIException as err:
            _LOGGER.error("Login failed: %s", err)
            raise EeroAuthenticationException(f"Login failed: {err}") from err
        except aiohttp.ClientError as err:
            error_msg = f"Network error during login: {err}"
            _LOGGER.error(error_msg)
            raise EeroNetworkException(error_msg) from err

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
        if not self._credentials.session_id:
            raise EeroAuthenticationException("No session token available. Login first.")

        try:
            # Log the verification attempt (sensitive data masked)
            _LOGGER.debug("Starting verification process")
            _LOGGER.debug("Verification code: [REDACTED]")

            # Set the session token as a cookie for verification
            self.session.cookie_jar.update_cookies({"s": self._credentials.session_id})

            # Make the verification request
            await self.post(
                LOGIN_VERIFY_ENDPOINT,
                auth_token=self._credentials.session_id,
                json={"code": verification_code},
            )

            # Session ID is already set from login, now it's validated
            self._login_in_progress = False

            # Set expiry to 30 days from now (typical session length)
            self._credentials.session_expiry = datetime.now().replace(microsecond=0) + timedelta(
                days=30
            )

            # Update session cookie for future requests
            self.session.cookie_jar.update_cookies({"s": self._credentials.session_id})
            _LOGGER.debug("Session cookie updated successfully")
            await self._save_credentials()
            return True

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
        if not self._credentials.session_id:
            raise EeroAuthenticationException("No session token available. Login first.")

        try:
            _LOGGER.debug("Resending verification code")

            # Set the session token as a cookie
            self.session.cookie_jar.update_cookies({"s": self._credentials.session_id})

            # Make the resend request
            await self.post(
                f"{LOGIN_ENDPOINT}/resend",
                auth_token=self._credentials.session_id,
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
            True if logout was successful (or session was already invalid)

        Raises:
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
            _LOGGER.debug("Logout API call succeeded")
        except EeroAuthenticationException:
            # 401 means session is already invalid on server - that's fine
            _LOGGER.debug("Session already invalid on server, clearing local credentials")
        except EeroAPIException as err:
            _LOGGER.warning("Logout API call failed: %s", err)
            # Still clear local credentials even if server call failed
        except aiohttp.ClientError as err:
            _LOGGER.warning("Network error during logout: %s", err)
            # Still clear local credentials even if network failed

        # Always clear local credentials regardless of API response
        self._credentials.clear_all()

        # Clear cookies
        self.session.cookie_jar.clear()

        # Update storage
        await self._save_credentials()
        return True

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
        """Clear all authentication data including stored credentials.

        This completely removes all authentication data from storage,
        including session tokens and refresh tokens.
        """
        # Clear in-memory credentials
        self._credentials.clear_all()
        self._login_in_progress = False

        # Clear cookies
        self.session.cookie_jar.clear()

        # Delete stored credentials entirely (removes file/keyring entry)
        await self._storage.clear()

        _LOGGER.debug("Cleared all authentication data")
