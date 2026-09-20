"""API module for Eero."""

from typing import Optional

from aiohttp import ClientSession

from ..const import DEFAULT_ACCEPT_LANGUAGE
from .ac_compat import ACCompatAPI
from .account import AccountAPI
from .auth import AuthAPI
from .backup import BackupAPI
from .backup_access_points import BackupAccessPointsAPI
from .blacklist import BlacklistAPI
from .burst_reporters import BurstReportersAPI
from .data_usage import DataUsageAPI
from .ddns import DdnsAPI
from .devices import DevicesAPI
from .dhcp import DhcpAPI
from .diagnostics import DiagnosticsAPI
from .dns import DnsAPI
from .dns_policies import DnsPoliciesAPI
from .eeros import EerosAPI
from .entitlements import EntitlementsAPI
from .events import EventsAPI
from .forwards import ForwardsAPI
from .insights import InsightsAPI
from .members import MembersAPI
from .networks import NetworksAPI
from .notifications import NotificationsAPI
from .ouicheck import OUICheckAPI
from .permissions import PermissionsAPI
from .power_saving import PowerSavingAPI
from .profiles import ProfilesAPI
from .reservations import ReservationsAPI
from .routing import RoutingAPI
from .schedule import ScheduleAPI
from .security import SecurityAPI
from .sqm import SqmAPI
from .subnets import SubnetsAPI
from .support import SupportAPI
from .thread import ThreadAPI
from .transfer import TransferAPI
from .updates import UpdatesAPI
from .wan import WanAPI
from .wpa3 import Wpa3API


class EeroAPI:
    """API client for interacting with the Eero API."""

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
        """Initialize the EeroAPI.

        Args:
            session: Optional aiohttp ClientSession to use for requests
            cookie_file: Optional path to a file for storing authentication cookies
            use_keyring: Whether to use keyring for secure token storage
            send_legacy_cookie: When True (default), also send the session
                token as the legacy ``s=<token>`` cookie, per request, on
                requests to the configured API host. Exists for compatibility
                with the eero mobile app for one major version and defaults
                on; it is expected to be removed in a future major once the
                cookie is confirmed unnecessary.
            accept_language: Value sent as the ``X-Accept-Language`` header
                on every request. Validated as printable ASCII with no
                CR/LF.
            get_retries: Number of additional attempts for GET requests that
                fail with a transport error or a 5xx response. 0 (default)
                disables retrying. Never applies to writes
                (POST/PUT/DELETE/PATCH).
        """
        self.auth = AuthAPI(
            session,
            cookie_file,
            use_keyring,
            send_legacy_cookie=send_legacy_cookie,
            accept_language=accept_language,
            get_retries=get_retries,
        )
        self.backup = BackupAPI(self.auth)
        self.dns = DnsAPI(self.auth)
        self.networks = NetworksAPI(self.auth)
        self.devices = DevicesAPI(self.auth)
        self.eeros = EerosAPI(self.auth)
        self.profiles = ProfilesAPI(self.auth)
        self.schedule = ScheduleAPI(self.auth)
        self.security = SecurityAPI(self.auth)
        self.sqm = SqmAPI(self.auth)
        self.diagnostics = DiagnosticsAPI(self.auth)
        self.updates = UpdatesAPI(self.auth)
        self.insights = InsightsAPI(self.auth)
        self.routing = RoutingAPI(self.auth)
        self.thread = ThreadAPI(self.auth)
        self.support = SupportAPI(self.auth)
        self.blacklist = BlacklistAPI(self.auth)
        self.reservations = ReservationsAPI(self.auth)
        self.forwards = ForwardsAPI(self.auth)
        self.transfer = TransferAPI(self.auth)
        self.burst_reporters = BurstReportersAPI(self.auth)
        self.data_usage = DataUsageAPI(self.auth)
        self.ac_compat = ACCompatAPI(self.auth)
        self.ouicheck = OUICheckAPI(self.auth)
        self.entitlements = EntitlementsAPI(self.auth)
        self.events = EventsAPI(self.auth)
        self.permissions = PermissionsAPI(self.auth)
        self.notifications = NotificationsAPI(self.auth)
        self.dns_policies = DnsPoliciesAPI(self.auth)
        self.members = MembersAPI(self.auth)
        self.account = AccountAPI(self.auth)
        self.dhcp = DhcpAPI(self.auth)
        self.wpa3 = Wpa3API(self.auth)
        self.power_saving = PowerSavingAPI(self.auth)
        self.ddns = DdnsAPI(self.auth)
        self.backup_access_points = BackupAccessPointsAPI(self.auth)
        self.subnets = SubnetsAPI(self.auth)
        self.wan = WanAPI(self.auth)

    async def __aenter__(self) -> "EeroAPI":
        """Enter async context manager."""
        await self.auth.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        await self.auth.__aexit__(exc_type, exc_val, exc_tb)

    @property
    def is_authenticated(self) -> bool:
        """Check if the client is authenticated."""
        return self.auth.is_authenticated

    async def login(self, user_identifier: str) -> bool:
        """Start the login process by requesting a verification code.

        Args:
            user_identifier: Email address or phone number for the Eero account

        Returns:
            True if login request was successful
        """
        return await self.auth.login(user_identifier)

    async def verify(self, verification_code: str) -> bool:
        """Verify login with the code sent to the user.

        Args:
            verification_code: The verification code sent to the user

        Returns:
            True if verification was successful
        """
        return await self.auth.verify(verification_code)

    async def logout(self) -> bool:
        """Log out from the Eero API.

        Returns:
            True if logout was successful
        """
        return await self.auth.logout()
