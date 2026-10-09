"""Log hygiene tests for identifier redaction in API-domain modules.

Item 3 of the security follow-ups: MAC addresses, serials, device IDs and
eero IDs must never appear in a log record as a bare positional argument.
This module exercises one representative read and one representative write
per affected domain module (``blacklist``, ``devices``, ``eeros``,
``insights``) against a mocked HTTP transport, using distinctive
placeholder identifiers, and asserts that none of those placeholders
appears in any captured log record at any level.

Only the identifier classes in scope for item 3 -- MAC, serial, device ID,
eero ID -- are asserted here. Other identifiers (network ID, profile ID,
etc.) are logged intentionally elsewhere in the SDK and are out of scope.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from eero.api.blacklist import BlacklistAPI
from eero.api.devices import DevicesAPI
from eero.api.eeros import EerosAPI
from eero.api.insights import InsightsAPI
from eero.exceptions import EeroNetworkException

from .conftest import api_success_response, create_mock_response

# Distinctive placeholder identifiers: unlikely to collide with any
# incidental substring already present in module/method names or fixture
# data, so a match in the captured logs can only mean the identifier itself
# was logged.
PLACEHOLDER_MAC = "aa:bb:cc:dd:ee:ff-CANARY-MAC-9f21"
PLACEHOLDER_EERO_ID = "eero-CANARY-ID-7d4a"
PLACEHOLDER_EERO_SERIAL = "SERIAL-CANARY-3c8e"
PLACEHOLDER_DEVICE_ID = "device-CANARY-ID-b105"

ALL_PLACEHOLDERS = (
    PLACEHOLDER_MAC,
    PLACEHOLDER_EERO_ID,
    PLACEHOLDER_EERO_SERIAL,
    PLACEHOLDER_DEVICE_ID,
)


def _auth_api(mock_session):
    """Build a minimal authenticated-auth_api double, as used across tests/api/."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return auth_api


def _assert_no_placeholder_leaked(caplog) -> None:
    """Assert none of the canary identifiers appear in any permitted log record.

    The only lines exempt from the check are the ``DEBUG``-level lines of
    ``eero.api.base``, whose transport-level ``Request: %s %s`` /
    ``Resource not found at %s`` debug logging deliberately includes the
    full request URL (and therefore any identifier baked into the URL path)
    -- a separate, pre-existing, documented design decision unrelated to
    item 3, which is scoped to bare positional identifier arguments passed
    to ``_LOGGER`` calls. Every other record is checked, including
    ``WARNING`` and above from ``eero.api.base``: the transport must never
    put the URL on a line a default logging configuration would show.
    """
    checked_text = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name != "eero.api.base" or record.levelno > logging.DEBUG
    )
    for placeholder in ALL_PLACEHOLDERS:
        assert (
            placeholder not in checked_text
        ), f"identifier placeholder {placeholder!r} leaked into a log record"


class TestBlacklistLogHygiene:
    """blacklist.py: MAC must not be logged as a bare positional argument."""

    @pytest.mark.asyncio
    async def test_read_and_write_do_not_log_mac(self, mock_session, caplog):
        """Test get_blacklist (read) and add_to_blacklist (write) never log the MAC."""
        api = BlacklistAPI(_auth_api(mock_session))
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"blacklist": []})
        )

        with caplog.at_level(logging.DEBUG):
            await api.get_blacklist("network_123")
            await api.add_to_blacklist("network_123", PLACEHOLDER_MAC)

        _assert_no_placeholder_leaked(caplog)


class TestDevicesLogHygiene:
    """devices.py: MAC must not be logged as a bare positional argument."""

    @pytest.mark.asyncio
    async def test_read_and_write_do_not_log_mac(self, mock_session, caplog):
        """Test get_device (read) and set_device_nickname (write) never log the MAC."""
        api = DevicesAPI(_auth_api(mock_session))
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"mac": PLACEHOLDER_MAC})
        )

        with caplog.at_level(logging.DEBUG):
            await api.get_device("network_123", PLACEHOLDER_MAC)
            await api.set_device_nickname("network_123", PLACEHOLDER_MAC, "nickname")

        _assert_no_placeholder_leaked(caplog)

    @pytest.mark.asyncio
    async def test_every_mac_bearing_call_does_not_log_mac(self, mock_session, caplog):
        """Test the remaining device methods that accept a bare MAC (item 3 fix set)."""
        api = DevicesAPI(_auth_api(mock_session))
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"mac": PLACEHOLDER_MAC})
        )

        with caplog.at_level(logging.DEBUG):
            await api.pause_device("network_123", PLACEHOLDER_MAC, True)
            await api.update_device_via_link("network_123", PLACEHOLDER_MAC, nickname="new-name")
            await api.set_device_type("network_123", PLACEHOLDER_MAC, "computer")
            await api.get_device_labels("network_123", PLACEHOLDER_MAC)
            await api.set_device_labels("network_123", PLACEHOLDER_MAC, make_label="Acme")

        _assert_no_placeholder_leaked(caplog)


class TestEerosLogHygiene:
    """eeros.py: eero ID / serial must not be logged as a bare positional argument."""

    @pytest.mark.asyncio
    async def test_read_and_write_do_not_log_eero_id(self, mock_session, caplog):
        """Test get_eero (read) and reboot_eero (write) never log the eero ID."""
        api = EerosAPI(_auth_api(mock_session))
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"id": PLACEHOLDER_EERO_ID})
        )

        with caplog.at_level(logging.DEBUG):
            await api.get_eero("network_123", PLACEHOLDER_EERO_ID)
            await api.reboot_eero("network_123", PLACEHOLDER_EERO_ID)

        _assert_no_placeholder_leaked(caplog)

    @pytest.mark.asyncio
    async def test_every_eero_id_bearing_call_does_not_log_identifier(self, mock_session, caplog):
        """Test the remaining eero methods that accept a bare eero ID/serial (item 3 fix set)."""
        api = EerosAPI(_auth_api(mock_session))
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"id": PLACEHOLDER_EERO_ID})
        )

        with caplog.at_level(logging.DEBUG):
            await api.get_connections("network_123", PLACEHOLDER_EERO_ID)
            try:
                await api.get_eero_support(PLACEHOLDER_EERO_SERIAL)
            except Exception:
                # Only log hygiene is under test here; the mocked transport's
                # response shape for this endpoint is irrelevant.
                pass

        _assert_no_placeholder_leaked(caplog)


class TestInsightsLogHygiene:
    """insights.py: device MAC must not be logged as a bare positional argument."""

    @pytest.mark.asyncio
    async def test_device_insights_read_does_not_log_mac(self, mock_session, caplog):
        """Test get_device_insights (read) never logs the device MAC."""
        api = InsightsAPI(_auth_api(mock_session))
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"values": []})
        )

        with caplog.at_level(logging.DEBUG):
            await api.get_device_insights(
                "network_123",
                PLACEHOLDER_MAC,
                start="2026-01-01T00:00:00Z",
                end="2026-01-02T00:00:00Z",
                cadence="daily",
                insight_type="blocked",
            )

        _assert_no_placeholder_leaked(caplog)


class TestTransportLogHygiene:
    """eero.api.base: WARNING and above must not carry the request URL."""

    @pytest.fixture(autouse=True)
    def no_real_sleep(self, monkeypatch):
        """Avoid real delays between retry attempts in tests."""
        monkeypatch.setattr("eero.api.base.asyncio.sleep", AsyncMock(return_value=None))

    @pytest.mark.asyncio
    async def test_read_failures_and_retries_do_not_log_mac_above_debug(
        self, mock_session, caplog, monkeypatch
    ):
        """Test timeout, network-error and retry lines for a read never carry the MAC."""
        api = DevicesAPI(_auth_api(mock_session))
        # Domain APIs do not expose get_retries; enable the opt-in GET retry directly.
        monkeypatch.setattr(api, "_get_retries", 2)
        mock_session.request.side_effect = [
            asyncio.TimeoutError(),
            aiohttp.ClientError(f"connection reset for {PLACEHOLDER_MAC}"),
            aiohttp.ClientError(f"connection reset for {PLACEHOLDER_MAC}"),
        ]

        with caplog.at_level(logging.DEBUG), pytest.raises(EeroNetworkException):
            await api.get_device("network_123", PLACEHOLDER_MAC)

        base_records = [r for r in caplog.records if r.name == "eero.api.base"]
        loud = [r for r in base_records if r.levelno >= logging.WARNING]
        assert {r.levelno for r in loud} == {logging.WARNING, logging.ERROR}
        _assert_no_placeholder_leaked(caplog)
        # Guard against a vacuous pass: the DEBUG lines (exempt by design)
        # do carry the identifier, so the check above is genuinely selective.
        debug_text = "\n".join(r.getMessage() for r in base_records if r.levelno == logging.DEBUG)
        assert PLACEHOLDER_MAC in debug_text

    @pytest.mark.asyncio
    async def test_write_failure_does_not_log_mac_above_debug(self, mock_session, caplog):
        """Test a failed write's ERROR line never carries the MAC."""
        api = DevicesAPI(_auth_api(mock_session))
        mock_session.request.side_effect = aiohttp.ClientError(f"reset {PLACEHOLDER_MAC}")

        with caplog.at_level(logging.DEBUG), pytest.raises(EeroNetworkException):
            await api.set_device_nickname("network_123", PLACEHOLDER_MAC, "nickname")

        assert any(r.levelno == logging.ERROR for r in caplog.records)
        _assert_no_placeholder_leaked(caplog)
