"""API module for Eero."""

from typing import Optional

from aiohttp import ClientSession

from .ac_compat import ACCompatAPI
from .activity import ActivityAPI
from .auth import AuthAPI
from .backup import BackupAPI
from .blacklist import BlacklistAPI
from .burst_reporters import BurstReportersAPI
from .devices import DevicesAPI
from .diagnostics import DiagnosticsAPI
from .dns import DnsAPI
from .eeros import EerosAPI
from .forwards import ForwardsAPI
from .insights import InsightsAPI
from .networks import NetworksAPI
from .ouicheck import OUICheckAPI
from .password import PasswordAPI
from .profiles import ProfilesAPI
from .reservations import ReservationsAPI
from .routing import RoutingAPI
from .schedule import ScheduleAPI
from .security import SecurityAPI
from .settings import SettingsAPI
from .sqm import SqmAPI
from .support import SupportAPI
from .thread import ThreadAPI
from .transfer import TransferAPI
from .updates import UpdatesAPI


class EeroAPI:
    """API client for interacting with the Eero API."""

    def __init__(
        self,
        session: Optional[ClientSession] = None,
        cookie_file: Optional[str] = None,
        use_keyring: bool = True,
    ) -> None:
        """Initialize the EeroAPI.

        Args:
            session: Optional aiohttp ClientSession to use for requests
            cookie_file: Optional path to a file for storing authentication cookies
            use_keyring: Whether to use keyring for secure token storage
        """
        self.auth = AuthAPI(session, cookie_file, use_keyring)
        self.activity = ActivityAPI(self.auth)
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
        self.settings = SettingsAPI(self.auth)
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
        self.ac_compat = ACCompatAPI(self.auth)
        self.ouicheck = OUICheckAPI(self.auth)
        self.password = PasswordAPI(self.auth)

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

    def set_preferred_network(self, network_id: str) -> None:
        """Set the preferred network ID to use for requests.

        Args:
            network_id: ID of the network to use
        """
        self.auth.preferred_network_id = network_id

    @property
    def preferred_network_id(self) -> Optional[str]:
        """Get the preferred network ID.

        Returns:
            Preferred network ID or None
        """
        return self.auth.preferred_network_id
