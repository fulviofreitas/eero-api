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

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.blacklist import BlacklistAPI
from eero.api.devices import DevicesAPI
from eero.api.eeros import EerosAPI
from eero.api.insights import InsightsAPI

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
    """Assert none of the canary identifiers appear in any domain-module log record.

    Excludes ``eero.api.base``, whose transport-level ``Request: %s %s`` /
    ``Resource not found at %s`` debug logging deliberately includes the
    full request URL (and therefore any identifier baked into the URL path)
    -- a separate, pre-existing, documented design decision unrelated to
    item 3, which is scoped to bare positional identifier arguments passed
    to ``_LOGGER`` calls in the domain modules themselves.
    """
    domain_text = "\n".join(
        record.getMessage() for record in caplog.records if record.name != "eero.api.base"
    )
    for placeholder in ALL_PLACEHOLDERS:
        assert (
            placeholder not in domain_text
        ), f"identifier placeholder {placeholder!r} leaked into a domain-module log record"


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
