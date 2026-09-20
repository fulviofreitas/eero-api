"""Account API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

Every write in this module is unverified: its request shape follows the
API's own field declarations, but no write here has been confirmed against
a live account. Each write logs one warning via `warn_uncharacterised_write`
before it is issued; follow the read-compare-skip discipline and never
retry a failed write in a loop.

Identifier values -- the email address, phone number, and verification
codes passed to these methods -- are never logged, including at DEBUG
level: log lines in this module never interpolate an argument's value, only
the fact that the call was made.

Account deletion is deliberately not exposed by this module. It is a
destructive, irreversible operation and was excluded by product decision,
independent of whether its wire shape is known.
"""

from typing import Any, Dict

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._writes import warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = get_secure_logger(__name__)


class AccountAPI(AuthenticatedAPI):
    """Account API for Eero.

    Manages the caller's own account profile: display name, email, phone,
    marketing consent, and the SMS country-code catalogue. All methods
    return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the AccountAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def set_name(self, name: str) -> Dict[str, Any]:
        """Set the account's display name.

        Issues a form-encoded PUT (``name=<value>``) to ``account/name``.

        Args:
            name: The new display name.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Setting account display name")
        warn_uncharacterised_write(_LOGGER, "set account name")
        return await self.put("account/name", auth_token=auth_token, data={"name": name})

    async def set_email(self, email: str) -> Dict[str, Any]:
        """Set the account's email address.

        Issues a form-encoded PUT (``email=<value>``) to ``account/email``.
        The new address is not active until confirmed via `verify_email`.
        The email value is never logged.

        Args:
            email: The new email address.

        Returns:
            Raw API response: {"meta": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Setting account email")
        warn_uncharacterised_write(_LOGGER, "set account email")
        return await self.put("account/email", auth_token=auth_token, data={"email": email})

    async def verify_email(self, code: str) -> Dict[str, Any]:
        """Confirm a pending email change with its verification code.

        Issues a form-encoded POST (``code=<value>``) to
        ``account/email/verify``. The code value is never logged.

        Args:
            code: The verification code sent to the new email address.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Verifying account email change")
        warn_uncharacterised_write(_LOGGER, "verify account email")
        return await self.post("account/email/verify", auth_token=auth_token, data={"code": code})

    async def set_phone(self, phone: str) -> Dict[str, Any]:
        """Set the account's phone number.

        Issues a form-encoded PUT (``phone=<value>``) to ``account/phone``.
        The new number is not active until confirmed via `verify_phone`.
        The phone value is never logged.

        Args:
            phone: The new phone number.

        Returns:
            Raw API response: {"meta": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Setting account phone number")
        warn_uncharacterised_write(_LOGGER, "set account phone")
        return await self.put("account/phone", auth_token=auth_token, data={"phone": phone})

    async def verify_phone(self, code: str) -> Dict[str, Any]:
        """Confirm a pending phone number change with its verification code.

        Issues a form-encoded POST (``code=<value>``) to
        ``account/phone/verify``. The code value is never logged.

        Args:
            code: The verification code sent to the new phone number.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Verifying account phone number change")
        warn_uncharacterised_write(_LOGGER, "verify account phone")
        return await self.post("account/phone/verify", auth_token=auth_token, data={"code": code})

    async def set_consents(self, *, marketing_emails: bool) -> Dict[str, Any]:
        """Set the account's marketing-email consent.

        Issues a form-encoded PUT (``marketing_emails=<"true"|"false">``) to
        ``account/consents``.

        Args:
            marketing_emails: Whether marketing emails are consented to.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Setting account marketing-email consent")
        warn_uncharacterised_write(_LOGGER, "set account consents")
        return await self.put(
            "account/consents",
            auth_token=auth_token,
            data={"marketing_emails": "true" if marketing_emails else "false"},
        )

    async def get_sms_countries(self) -> Dict[str, Any]:
        """Get the SMS country-code catalogue.

        GETs ``countries/sms``.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting SMS country-code catalogue")
        return await self.get("countries/sms", auth_token=auth_token)


__all__ = ["AccountAPI"]
