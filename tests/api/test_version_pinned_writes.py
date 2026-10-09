"""Endpoint version pins must survive network IDs, paths and URLs."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.devices import DevicesAPI
from eero.api.wan import WanAPI

from .conftest import api_success_response, create_mock_response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "network", ["n1", "/2.2/networks/n1", "https://api-user.e2ro.com/2.2/networks/n1"]
)
@pytest.mark.parametrize(
    "device",
    [
        "aabbccddeeff",
        "/2.2/networks/n1/devices/aabbccddeeff",
        "https://api-user.e2ro.com/2.2/networks/n1/devices/aabbccddeeff",
    ],
)
@pytest.mark.parametrize(
    "method,args", [("pause_device", (True,)), ("set_device_nickname", ("desk",))]
)
async def test_device_write_pins_resolved_url(mock_session, network, device, method, args):
    auth = MagicMock()
    auth.session = mock_session
    auth.get_auth_token = AsyncMock(return_value="token")
    mock_session.request.return_value = create_mock_response(200, api_success_response({}))
    await getattr(DevicesAPI(auth), method)(network, device, *args)
    verb, url = mock_session.request.call_args.args
    assert verb == "PUT"
    assert url == "https://api-user.e2ro.com/2.3/networks/n1/devices/aabbccddeeff"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "network", ["n1", "/2.2/networks/n1", "https://api-user.e2ro.com/2.2/networks/n1"]
)
@pytest.mark.parametrize(
    "method,args,suffix",
    [
        ("set_multistaticip", ({"enabled": False},), "multistaticip"),
        (
            "set_secondary_wan_config",
            ({"devices": []},),
            "devices/secondary_wan_config",
        ),
        (
            "set_device_secondary_wan_access",
            ("aabbccddeeff", True),
            "devices/aabbccddeeff",
        ),
    ],
)
async def test_wan_write_pins_resolved_url(mock_session, network, method, args, suffix):
    auth = MagicMock()
    auth.session = mock_session
    auth.get_auth_token = AsyncMock(return_value="token")
    mock_session.request.return_value = create_mock_response(200, api_success_response({}))
    if method == "set_device_secondary_wan_access":
        await getattr(WanAPI(auth), method)(network, args[0], deny=args[1])
    else:
        await getattr(WanAPI(auth), method)(network, *args)
    verb, url = mock_session.request.call_args.args
    assert verb == "PUT"
    assert url == f"https://api-user.e2ro.com/2.3/networks/n1/{suffix}"
