"""Regression guard: every nested-resource id is validated before use.

A code review of 8.0.0 found that several domain modules built a URL by
``str.format``-ing a caller-supplied id directly into a module-level
template string, then handing the *combined* template to
``eero.api.links.resource_url`` -- whose bare-id branch validates the id,
but only for the single ``{id}`` placeholder resource_url itself
substitutes. The pre-substituted id in the template was never validated,
so a value like ``"../../account"``, ``"x?y=1"``, or ``"{x}"`` could escape
its path segment, inject a query string, or raise a bare ``KeyError``/
``ValueError`` instead of a clean ``EeroValidationException``. Separately,
a path-form network id (e.g. ``"/2.2/networks/network_123"``) spliced into
one of these templates produced a doubled path
(``/2.2/networks//2.2/networks/network_123/...``).

This module asserts, for every method fixed in that review, that:

* A hostile id raises ``EeroValidationException`` before any HTTP request
  is issued (the mocked transport is asserted never called).
* A path-form network id resolves to the single expected URL, with no
  doubled ``/2.2/networks/...`` segment.

`DnsPoliciesAPI`'s two profile-applications methods, and `DevicesAPI`'s
`set_device_nickname`/`pause_device` (via the shared `_update_device`
helper), are a deliberate, documented exception: their nested id is
normalised with `id_from_url` first (so a profile/device path or URL
yields its trailing id) before being validated, so a hostile value that
merely carries extra leading path segments (e.g. ``"../../account"``,
which normalises to the harmless trailing segment ``"account"``) is *not*
expected to raise there -- only a value that is invalid even as a trailing
segment is. That subset is exercised in its own parametrised cases below.
"""

from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.backup_access_points import BackupAccessPointsAPI
from eero.api.data_usage import DataUsageAPI
from eero.api.devices import DevicesAPI
from eero.api.dns_policies import DnsPoliciesAPI
from eero.api.eeros import EerosAPI
from eero.api.forwards import ForwardsAPI
from eero.api.members import MembersAPI
from eero.api.power_saving import PowerSavingAPI
from eero.api.profiles import ProfilesAPI
from eero.api.reservations import ReservationsAPI
from eero.api.subnets import SubnetsAPI
from eero.api.wan import WanAPI
from eero.const import API_HOST
from eero.exceptions import EeroValidationException

from .conftest import api_success_response, create_mock_response

#: Ids designed to escape a single path segment, inject a query string, or
#: break a `str.format` template, in every case except a plain nested id.
HOSTILE_IDS = ("../../account", "x?y=1", "a/b", "{x}", "")

#: The subset of `HOSTILE_IDS` still expected to raise for a method whose
#: nested id is normalised via `id_from_url` before validation: everything
#: except the two values `id_from_url` legitimately reduces to a harmless
#: bare trailing segment (`"../../account"` -> `"account"`, `"a/b"` ->
#: `"b"`).
NORMALIZED_ID_HOSTILE_IDS = ("x?y=1", "{x}", "")


def _api(cls, mock_session):
    """Build a domain API instance wired to a mocked auth layer and session."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return cls(auth_api)


# ========================== Hostile-id cases ==========================
#
# Each case is (label, api_class, call) where `call` takes (api, hostile_id)
# and returns the awaitable to invoke.

CaseCall = Callable[[Any, str], Awaitable[Any]]

HOSTILE_ID_CASES: list[tuple[str, type, CaseCall]] = [
    (
        "MembersAPI.update_invite:invite_id",
        MembersAPI,
        lambda api, hid: api.update_invite("network_123", hid, invite_nickname="x"),
    ),
    (
        "MembersAPI.delete_invite:invite_id",
        MembersAPI,
        lambda api, hid: api.delete_invite("network_123", hid),
    ),
    (
        "MembersAPI.remove_admin:user_id",
        MembersAPI,
        lambda api, hid: api.remove_admin("network_123", hid),
    ),
    (
        "ForwardsAPI.update_forward:forward",
        ForwardsAPI,
        lambda api, hid: api.update_forward(hid, {}, network="network_123"),
    ),
    (
        "ForwardsAPI.delete_forward:forward",
        ForwardsAPI,
        lambda api, hid: api.delete_forward("network_123", hid),
    ),
    (
        "ReservationsAPI.update_reservation:reservation",
        ReservationsAPI,
        lambda api, hid: api.update_reservation(hid, {}, network="network_123"),
    ),
    (
        "ReservationsAPI.delete_reservation:reservation",
        ReservationsAPI,
        lambda api, hid: api.delete_reservation("network_123", hid),
    ),
    (
        "BackupAccessPointsAPI.update:backup_network_id",
        BackupAccessPointsAPI,
        lambda api, hid: api.update("network_123", hid, ssid="s"),
    ),
    (
        "BackupAccessPointsAPI.delete_backup_access_point:backup_network_id",
        BackupAccessPointsAPI,
        lambda api, hid: api.delete_backup_access_point("network_123", hid),
    ),
    (
        "DevicesAPI.get_device:mac",
        DevicesAPI,
        lambda api, hid: api.get_device("network_123", hid),
    ),
    (
        "DevicesAPI.update_device_via_link:mac",
        DevicesAPI,
        lambda api, hid: api.update_device_via_link("network_123", hid, nickname="x"),
    ),
    (
        "ProfilesAPI.get_profile:profile",
        ProfilesAPI,
        lambda api, hid: api.get_profile("network_123", hid),
    ),
    (
        "ProfilesAPI.delete_profile:profile",
        ProfilesAPI,
        lambda api, hid: api.delete_profile("network_123", hid),
    ),
    (
        "EerosAPI.port_action:interface_number",
        EerosAPI,
        lambda api, hid: api.port_action("eero_123", hid, "ENABLE_DATA"),
    ),
    (
        "WanAPI.set_device_secondary_wan_access:mac",
        WanAPI,
        lambda api, hid: api.set_device_secondary_wan_access("network_123", hid, deny=True),
    ),
    (
        "SubnetsAPI.delete_subnet:subnet_type",
        SubnetsAPI,
        lambda api, hid: api.delete_subnet("network_123", hid),
    ),
    (
        "SubnetsAPI.get_content_filters:subnet_id",
        SubnetsAPI,
        lambda api, hid: api.get_content_filters("network_123", hid),
    ),
    (
        "PowerSavingAPI.update_schedule:schedule_id",
        PowerSavingAPI,
        lambda api, hid: api.update_schedule("network_123", hid, enabled=True),
    ),
    (
        "PowerSavingAPI.delete_schedule:schedule_id",
        PowerSavingAPI,
        lambda api, hid: api.delete_schedule("network_123", hid),
    ),
    (
        "DataUsageAPI.get_device_usage:device_mac",
        DataUsageAPI,
        lambda api, hid: api.get_device_usage(
            "network_123",
            hid,
            start="2026-01-01T00:00:00Z",
            end="2026-01-02T00:00:00Z",
            cadence="daily",
        ),
    ),
    (
        "DataUsageAPI.get_eero_usage:eero_id",
        DataUsageAPI,
        lambda api, hid: api.get_eero_usage(
            "network_123",
            hid,
            start="2026-01-01T00:00:00Z",
            end="2026-01-02T00:00:00Z",
            cadence="daily",
        ),
    ),
    (
        "DataUsageAPI.get_profile_usage:profile_id",
        DataUsageAPI,
        lambda api, hid: api.get_profile_usage(
            "network_123",
            hid,
            start="2026-01-01T00:00:00Z",
            end="2026-01-02T00:00:00Z",
            cadence="daily",
        ),
    ),
]

#: Methods whose nested id is normalised with `id_from_url` before
#: validation (see the module docstring): a value with extra leading path
#: segments is trimmed to its trailing segment rather than rejected.
NORMALIZED_ID_CASES: list[tuple[str, type, CaseCall]] = [
    (
        "DnsPoliciesAPI.get_profile_applications:profile_id",
        DnsPoliciesAPI,
        lambda api, hid: api.get_profile_applications("network_123", hid),
    ),
    (
        "DnsPoliciesAPI.set_profile_blocked_applications:profile_id",
        DnsPoliciesAPI,
        lambda api, hid: api.set_profile_blocked_applications("network_123", hid, []),
    ),
    (
        "DevicesAPI.set_device_nickname:mac",
        DevicesAPI,
        lambda api, hid: api.set_device_nickname("network_123", hid, "nick"),
    ),
    (
        "DevicesAPI.pause_device:mac",
        DevicesAPI,
        lambda api, hid: api.pause_device("network_123", hid, True),
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("label, cls, call", HOSTILE_ID_CASES, ids=[c[0] for c in HOSTILE_ID_CASES])
@pytest.mark.parametrize("hostile_id", HOSTILE_IDS)
async def test_hostile_id_raises_before_any_request(label, cls, call, hostile_id, mock_session):
    """A hostile id raises EeroValidationException; no request is ever issued."""
    api = _api(cls, mock_session)

    with pytest.raises(EeroValidationException):
        await call(api, hostile_id)

    mock_session.request.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label, cls, call",
    NORMALIZED_ID_CASES,
    ids=[c[0] for c in NORMALIZED_ID_CASES],
)
@pytest.mark.parametrize("hostile_id", NORMALIZED_ID_HOSTILE_IDS)
async def test_normalized_id_hostile_id_raises_before_any_request(
    label, cls, call, hostile_id, mock_session
):
    """As above, for a nested id normalised via id_from_url before validation."""
    api = _api(cls, mock_session)

    with pytest.raises(EeroValidationException):
        await call(api, hostile_id)

    mock_session.request.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label, cls, call",
    NORMALIZED_ID_CASES,
    ids=[c[0] for c in NORMALIZED_ID_CASES],
)
async def test_normalized_id_path_prefix_is_trimmed_not_rejected(label, cls, call, mock_session):
    """An id carrying extra leading path segments is trimmed, not rejected.

    Documents the deliberate id_from_url normalisation: this is not a
    security hole (the network is a fixed, separately-supplied argument, and
    the extra ``../..`` segments in the id never reach the request line --
    only the harmless trailing segment ``"account"`` does), just a
    different-from-the-general-rule shape for these particular methods.
    """
    mock_session.request.return_value = create_mock_response(200, api_success_response({}))
    api = _api(cls, mock_session)

    await call(api, "../../account")

    mock_session.request.assert_called_once()
    call_args = mock_session.request.call_args
    url = call_args.args[1]
    assert "/account" in url
    assert ".." not in url


# ========================== Path-form network id: no doubled path ==========================


NETWORK_PATH_CASES: list[tuple[str, type, CaseCall, str]] = [
    (
        "MembersAPI.update_invite",
        MembersAPI,
        lambda api, network: api.update_invite(network, "invite_1", invite_nickname="x"),
        "/networks/network_123/invites/invite_1",
    ),
    (
        "ForwardsAPI.delete_forward",
        ForwardsAPI,
        lambda api, network: api.delete_forward(network, "forward_1"),
        "/networks/network_123/forwards/forward_1",
    ),
    (
        "ReservationsAPI.delete_reservation",
        ReservationsAPI,
        lambda api, network: api.delete_reservation(network, "reservation_1"),
        "/networks/network_123/reservations/reservation_1",
    ),
    (
        "BackupAccessPointsAPI.delete_backup_access_point",
        BackupAccessPointsAPI,
        lambda api, network: api.delete_backup_access_point(network, "backup_1"),
        "/networks/network_123/backup_access_points/backup_1",
    ),
    (
        "DevicesAPI.get_device",
        DevicesAPI,
        lambda api, network: api.get_device(network, "aabbccddeeff"),
        "/networks/network_123/devices/aabbccddeeff",
    ),
    (
        "ProfilesAPI.delete_profile",
        ProfilesAPI,
        lambda api, network: api.delete_profile(network, "profile_1"),
        "/networks/network_123/profiles/profile_1",
    ),
    (
        "WanAPI.set_device_secondary_wan_access",
        WanAPI,
        lambda api, network: api.set_device_secondary_wan_access(
            network, "aabbccddeeff", deny=True
        ),
        "/networks/network_123/devices/aabbccddeeff",
    ),
    (
        "SubnetsAPI.get_content_filters",
        SubnetsAPI,
        lambda api, network: api.get_content_filters(network, "subnet_1"),
        "/networks/network_123/subnets_config/subnet_1/dns_policies/content_filters",
    ),
    (
        "PowerSavingAPI.delete_schedule",
        PowerSavingAPI,
        lambda api, network: api.delete_schedule(network, "schedule_1"),
        "/networks/network_123/power_saving/schedules/schedule_1",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label, cls, call, expected_suffix",
    NETWORK_PATH_CASES,
    ids=[c[0] for c in NETWORK_PATH_CASES],
)
async def test_path_form_network_id_is_not_doubled(label, cls, call, expected_suffix, mock_session):
    """A path-form network id resolves to a single, correctly-joined URL."""
    mock_session.request.return_value = create_mock_response(200, api_success_response({}))
    api = _api(cls, mock_session)

    await call(api, "/2.2/networks/network_123")

    mock_session.request.assert_called_once()
    call_args = mock_session.request.call_args
    url = call_args.args[1]

    assert url == f"{API_HOST}/2.2{expected_suffix}"
    # The network path segment must appear exactly once.
    assert url.count("/networks/network_123") == 1
    assert "//2.2" not in url.removeprefix(API_HOST)
