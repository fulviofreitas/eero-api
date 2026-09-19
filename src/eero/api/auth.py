"""Authentication API for Eero.

Implements the login -> verify -> authenticated-request -> refresh -> logout
lifecycle against the eero cloud API. All requests go through the shared
transport in ``base.py`` (``BaseAPI.post`` / ``RequestEncoding``); this
module never constructs headers, cookies, URLs, or body encodings directly.
"""

from __future__ import annotations

import asyncio
from typing import Final, FrozenSet, Optional

from aiohttp import ClientSession

from ..const import (
    API_ENDPOINT,
    DEFAULT_ACCEPT_LANGUAGE,
    LOGIN_ENDPOINT,
    LOGIN_REFRESH_ENDPOINT,
    LOGIN_RESEND_ENDPOINT,
    LOGIN_VERIFY_ENDPOINT,
    LOGOUT_COOKIE_FIELD_NAME,
    LOGOUT_ENDPOINT,
    SESSION_COOKIE_PREFIX,
)
from ..errors import ErrorGroup, classify_error_code
from ..exceptions import (
    EeroAPIException,
    EeroAuthenticationException,
    EeroNetworkException,
    EeroTimeoutException,
    EeroValidationException,
)
from ..logging import get_secure_logger
from .auth_storage import AuthCredentials, CredentialStorage, create_storage
from .base import BaseAPI, RequestEncoding

_LOGGER = get_secure_logger(__name__)

# The single-flight refresh guard waits this long for an in-flight refresh
# before giving up and letting the waiting caller fail with its own original
# authentication error. Matches BaseAPI._request's default total timeout, so
# a waiter never outlives the request that would have triggered its own
# refresh anyway.
_SESSION_REFRESH_GUARD_TIMEOUT_SECONDS: Final[float] = 30.0

# Credentials are cleared on a 401 from the refresh endpoint only when the
# error_code falls in the catalogue's Session group (a terminal, "your
# session is really gone" signal) or is absent/unrecognised. Every other
# recognised 401 error_code -- notably the verification/login-state group,
# where the token is mid-verification rather than gone -- leaves stored
# credentials untouched so the caller can finish verify() and retry.
_CREDENTIAL_CLEARING_GROUPS: Final[FrozenSet[ErrorGroup]] = frozenset({ErrorGroup.SESSION})


class AuthAPI(BaseAPI):
    """Authentication API for Eero."""

    def __init__(
        self,
        session: Optional[ClientSession] = None,
        cookie_file: Optional[str] = None,
        use_keyring: bool = True,
        *,
        send_legacy_cookie: bool = True,
        accept_language: str = DEFAULT_ACCEPT_LANGUAGE,
        get_retries: int = 0,
    ) -> None:
        """Initialize the AuthAPI.

        Args:
            session: Optional aiohttp ClientSession to use for requests
            cookie_file: Optional path to a file for storing authentication cookies
            use_keyring: Whether to use keyring for secure token storage
            send_legacy_cookie: See ``BaseAPI.__init__``.
            accept_language: See ``BaseAPI.__init__``.
            get_retries: See ``BaseAPI.__init__``.
        """
        super().__init__(
            session,
            cookie_file,
            API_ENDPOINT,
            send_legacy_cookie=send_legacy_cookie,
            accept_language=accept_language,
            get_retries=get_retries,
        )
        self._storage: CredentialStorage = create_storage(use_keyring, cookie_file)
        self._credentials = AuthCredentials()
        self._login_in_progress = False
        # Single-flight guard for refresh_session(): the future for the
        # currently in-flight refresh, or None when no refresh is running.
        self._refresh_future: "Optional[asyncio.Future[bool]]" = None

    @property
    def is_authenticated(self) -> bool:
        """Check whether a session token is present.

        There is no client-side session expiry -- the server is the sole
        authority on session validity, signalled via 401 responses.

        Returns:
            True if a session token is present, False otherwise
        """
        return bool(self._credentials.session_id)

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

    async def _save_credentials(self) -> None:
        """Save authentication credentials to storage."""
        await self._storage.save(self._credentials)

    async def login(self, user_identifier: str) -> bool:
        """Start the login process by requesting a verification code.

        Args:
            user_identifier: Email address or phone number for the Eero account

        Returns:
            True if a session token was received, False otherwise

        Raises:
            EeroAuthenticationException: If the login request itself fails
                (e.g. the identifier is rejected)
            EeroNetworkException: If there's a network error
        """
        # Clear any previous authentication data
        self._credentials.clear_all()
        self._login_in_progress = True

        # Save to ensure we don't have stale data
        await self._save_credentials()

        try:
            _LOGGER.debug("Starting login process")

            response = await self.post(
                LOGIN_ENDPOINT,
                data={"login": user_identifier},
            )

            # Extract user_token from API response and store as session_id
            # (it becomes the session token once verify() succeeds).
            user_token = response.get("data", {}).get("user_token")
            if not user_token:
                _LOGGER.debug("Login response did not include a session token")
                return False

            self._credentials.session_id = user_token
            await self._save_credentials()

            return True
        except EeroAPIException as err:
            _LOGGER.error("Login failed: %s", err)
            raise EeroAuthenticationException(
                f"Login failed: {err}", envelope=err.envelope, error_code=err.error_code
            ) from err

    async def verify(self, verification_code: str) -> bool:
        """Verify login with the code sent to the user.

        Args:
            verification_code: The verification code sent to the user

        Returns:
            True if verification was successful

        Raises:
            EeroAuthenticationException: If verification fails (an incorrect
                code surfaces here with the response envelope and error_code
                attached)
            EeroNetworkException: If there's a network error
        """
        if not self._credentials.session_id:
            raise EeroAuthenticationException("No session token available. Login first.")

        try:
            _LOGGER.debug("Starting verification process")
            _LOGGER.debug("Verification code: [REDACTED]")

            await self.post(
                LOGIN_VERIFY_ENDPOINT,
                auth_token=self._credentials.session_id,
                data={"code": verification_code},
            )

            # The response carries the user object, not a new token -- the
            # session_id set during login() is what's now verified.
            self._login_in_progress = False
            await self._save_credentials()
            return True

        except EeroAuthenticationException as err:
            # A wrong code (or any other verification failure) surfaces here
            # as a 401 from the transport, already carrying the envelope and
            # error_code -- no further wrapping needed.
            _LOGGER.error("Verification failed: %s", err)
            raise
        except EeroAPIException as err:
            _LOGGER.error("Verification failed: %s", err)
            raise EeroAuthenticationException(
                f"Verification failed: {err}", envelope=err.envelope, error_code=err.error_code
            ) from err

    async def resend_verification_code(self) -> bool:
        """Resend the verification code.

        Returns:
            True if resend was successful, False on any API-level failure

        Raises:
            EeroAuthenticationException: If no session token is available
            EeroNetworkException: If there's a network error
        """
        if not self._credentials.session_id:
            raise EeroAuthenticationException("No session token available. Login first.")

        try:
            _LOGGER.debug("Resending verification code")

            await self.post(
                LOGIN_RESEND_ENDPOINT,
                auth_token=self._credentials.session_id,
                json={},
            )

            _LOGGER.debug("Verification code resent successfully")
            return True
        except EeroAPIException as err:
            _LOGGER.error("Failed to resend verification code: %s", err)
            return False

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

        session_id = self._credentials.session_id

        try:
            await self.post(
                LOGOUT_ENDPOINT,
                auth_token=session_id,
                data={LOGOUT_COOKIE_FIELD_NAME: f"{SESSION_COOKIE_PREFIX}{session_id}"},
            )
            _LOGGER.debug("Logout API call succeeded")
        except EeroAuthenticationException:
            # 401 means session is already invalid on server - that's fine
            _LOGGER.debug("Session already invalid on server, clearing local credentials")
        except EeroAPIException as err:
            _LOGGER.warning("Logout API call failed: %s", err)
            # Still clear local credentials even if server call failed
        except (EeroNetworkException, EeroTimeoutException) as err:
            _LOGGER.warning("Logout API call failed: %s", err)
            # Still clear local credentials even if the request never reached
            # the server -- the whole point of logging out locally.

        # Always clear local credentials regardless of API response
        self._credentials.clear_all()
        await self._save_credentials()
        return True

    async def refresh_session(self) -> bool:
        """Refresh the current session, coalescing concurrent callers.

        The API's refresh endpoint reuses the existing session
        token -- there is no separate refresh token. A successful refresh
        response carries a token in its body, but per SDK policy this value
        is intentionally ignored: the current session token remains the one
        in use.

        Concurrent callers (e.g. several domain APIs each hitting a
        server-driven ``error.session.refresh`` signal at once) share a
        single in-flight refresh: the first caller performs the request,
        later callers await its outcome instead of issuing their own. A
        caller that has waited longer than the guard timeout gives up and
        returns False, which causes its own original authentication error
        to be raised by the transport rather than fabricating a new one.

        Returns:
            True if session refresh was successful (HTTP 200), False on any
            API error.

        Raises:
            EeroAuthenticationException: If no session token is available to
                refresh
            EeroNetworkException: If there's a network error
        """
        existing_future = self._refresh_future
        if existing_future is not None and not existing_future.done():
            try:
                return await asyncio.wait_for(
                    asyncio.shield(existing_future),
                    timeout=_SESSION_REFRESH_GUARD_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                _LOGGER.debug("Timed out waiting for an in-flight session refresh")
                return False

        future: "asyncio.Future[bool]" = asyncio.get_running_loop().create_future()
        self._refresh_future = future
        try:
            result = await self._do_refresh()
        except BaseException as exc:
            future.set_exception(exc)
            raise
        else:
            future.set_result(result)
            return result
        finally:
            if self._refresh_future is future:
                self._refresh_future = None

    async def _do_refresh(self) -> bool:
        """Perform the actual refresh request. Only called by the single-flight leader.

        Returns:
            True on HTTP 200, False on any API-level error.

        Raises:
            EeroAuthenticationException: If no session token is available
            EeroNetworkException: If there's a network error
        """
        if not self._credentials.session_id:
            raise EeroAuthenticationException("No session token available. Login first.")

        try:
            await self.post(
                LOGIN_REFRESH_ENDPOINT,
                auth_token=self._credentials.session_id,
                encoding=RequestEncoding.EMPTY_JSON_STRING,
            )
        except EeroAuthenticationException as err:
            group = classify_error_code(err.error_code)
            if group not in _CREDENTIAL_CLEARING_GROUPS and group is not None:
                # A recognised, non-Session error_code (e.g. the
                # verification/login-state group, or the session-refresh
                # signal itself) means the session is mid-verification or
                # otherwise not gone -- retaining credentials lets the
                # caller finish verify() and retry.
                _LOGGER.debug(
                    "Session refresh blocked by a non-terminal authentication error (%s); "
                    "retaining credentials",
                    err.error_code,
                )
                return False
            _LOGGER.debug(
                "Session refresh failed with a terminal authentication error (%s); "
                "clearing credentials",
                err.error_code or "no error_code",
            )
            self._credentials.clear_all()
            await self._save_credentials()
            return False
        except EeroAPIException as err:
            _LOGGER.debug("Session refresh failed: %s", err)
            return False

        _LOGGER.debug("Session refreshed; server-issued token ignored per SDK policy")
        return True

    async def ensure_authenticated(self) -> bool:
        """Report whether a session token is currently present.

        There is no client-driven refresh-on-expiry path -- refreshes are
        exclusively server-driven (see ``BaseAPI._request``'s handling of the
        ``error.session.refresh`` signal).

        Returns:
            True if authenticated, False otherwise
        """
        return self.is_authenticated

    async def get_auth_token(self) -> Optional[str]:
        """Get the current authentication token.

        Returns:
            Current authentication token or None
        """
        if self.is_authenticated:
            return self._credentials.session_id
        return None

    async def clear_auth_data(self) -> None:
        """Clear all authentication data including stored credentials.

        This completely removes all authentication data from storage,
        including the session token.
        """
        # Clear in-memory credentials
        self._credentials.clear_all()
        self._login_in_progress = False

        # Delete stored credentials entirely (removes file/keyring entry)
        await self._storage.clear()

        _LOGGER.debug("Cleared all authentication data")

    async def set_session_token(self, token: str) -> None:
        """Seed the active session with a pre-existing session token.

        Bypasses the interactive login + verify flow.  Useful when the token
        is supplied externally (e.g. from a secret manager, environment
        variable, or test fixture).

        Args:
            token: The opaque session token (the value the API expects as
                the ``s=`` cookie / ``X-User-Token`` header).

        Raises:
            EeroValidationException: If the token is empty or non-string.
        """
        if not isinstance(token, str) or not token:
            raise EeroValidationException("token", "must be a non-empty string")

        self._credentials.session_id = token
        await self._save_credentials()

        _LOGGER.debug("Session token injected externally")

    async def clear_session_token(self) -> None:
        """Clear the active session token from in-memory credentials and storage.

        This is a narrower counterpart to ``clear_auth_data``: it removes the
        session token but does not touch any other persisted state beyond
        what is implied by re-saving credentials after clearing.
        """
        self._credentials.session_id = None
        await self._save_credentials()

        _LOGGER.debug("Session token cleared")
