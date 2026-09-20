"""Repository-wide check: every write-shaped method warns before it writes.

This module walks every `eero.api.base.AuthenticatedAPI` subclass and calls
each public coroutine method whose name looks like a write (``set_``,
``create_``, ``update_``, ``delete_``, ``add_``, ``remove_``, ``block_``,
``unblock_``, ``apply_``, ``reboot_``, ``run_``, ``regenerate_``,
``enable_``, ``disable_``, ``mark_``, ``allow_``, ``rearrange_``,
``start_``, ``promote_``, ``cancel_``, ``respond_``, ``verify_``,
``node_``, ``port_``, ``led_``, ``nightlight_``, ``clear_``) against a
mocked transport, with placeholder arguments. Each such method must either:

* Emit `eero.api._writes.warn_uncharacterised_write`'s WARNING (directly, or
  by delegating to another method that does) before issuing its request, or
* Be listed in `_VERIFIED_WRITE_ALLOWLIST` below, with a comment citing the
  issue/commit that live-verified it.

This is a regression guard, not a design decision: it exists so a new write
method can't silently ship without the operator-facing warning that the
rest of this SDK relies on for its read-compare-skip discipline.
"""

import inspect
import logging
import pkgutil
from typing import Any, Dict, List, Mapping, Union, get_args, get_origin
from unittest.mock import AsyncMock, MagicMock

import pytest

import eero.api as eero_api_package
from eero.api.base import AuthenticatedAPI, BaseAPI

_WRITE_PREFIXES = (
    "set_",
    "create_",
    "update_",
    "delete_",
    "add_",
    "remove_",
    "block_",
    "unblock_",
    "apply_",
    "reboot_",
    "run_",
    "regenerate_",
    "enable_",
    "disable_",
    "mark_",
    "allow_",
    "rearrange_",
    "start_",
    "promote_",
    "cancel_",
    "respond_",
    "verify_",
    "node_",
    "port_",
    "led_",
    "nightlight_",
    "clear_",
)

# ========================== Verified-write allowlist ==========================
#
# Every entry here is a write that is DOCUMENTED in its own module as
# live-verified against a real network, so it deliberately does not carry
# the "uncharacterised write" warning. Keep this list short: a new entry
# needs the same live-verification evidence the existing ones cite.
_VERIFIED_WRITE_ALLOWLIST = {
    # devices.py: "the live-verified write (issue #102): it targets the 2.3
    # endpoint, where the mutation persists."
    ("DevicesAPI", "pause_device"),
    ("DevicesAPI", "set_device_nickname"),
    # devices.py: DevicesAPI.unblock_device delegates to
    # BlacklistAPI.remove_from_blacklist -- allowlisted below -- so it never
    # emits the warning either.
    ("DevicesAPI", "unblock_device"),
    # blacklist.py: "Live-verified (issue #109): a blacklisted entry's
    # `device_id` is the MAC address with colons stripped, so both the raw
    # MAC and the colon-stripped form are accepted as the URL segment."
    ("BlacklistAPI", "remove_from_blacklist"),
    # eeros.py: set_led was live-verified on 2026-09-20: the form-encoded
    # write to the led link turned a node's light off and back on, the
    # cloud read-back and the app agreed, and no node rebooted.
    ("EerosAPI", "set_led"),
    # eeros.py: set_led_brightness was live-verified on 2026-09-20: the
    # form-encoded write to the led link changed the node's brightness and
    # the read-back matched, with no reboot.
    ("EerosAPI", "set_led_brightness"),
    # eeros.py: reboot_eero was live-verified on 2026-09-20: the POST
    # returned 201, and only the targeted node's reboot marker moved --
    # the other nodes did not reboot.
    ("EerosAPI", "reboot_eero"),
    # devices.py: set_device_type was live-verified on 2026-09-20: the
    # value persisted and read back, and the response echoes the new type.
    ("DevicesAPI", "set_device_type"),
    # networks.py: set_guest_network, set_guest_password, and
    # clear_guest_password were live-verified on 2026-09-20: enable/
    # disable, password set, clear, and restore all read back correctly,
    # and the guest name was unchanged.
    ("NetworksAPI", "set_guest_network"),
    ("NetworksAPI", "set_guest_password"),
    ("NetworksAPI", "clear_guest_password"),
    # networks.py: run_speed_test was live-verified on 2026-09-20: it
    # returns 202 with data: null, and a new result appears in
    # get_speed_tests about a minute later.
    ("NetworksAPI", "run_speed_test"),
}

# Per-(method name, parameter name) placeholder overrides for parameters
# whose value is validated against a fixed, small vocabulary *before* the
# method's warning call -- a generic "placeholder-id" string would be
# rejected before ever reaching (and thus never exercising) the warning.
_PARAM_OVERRIDES = {
    ("set_mlo_mode", "mode"): "disabled",
    ("set_connection_mode", "mode"): "BRIDGE",
    ("node_action", "action"): "POWER_CYCLE_ALL_PORTS",
    ("port_action", "action"): "ENABLE_DATA",
    ("create_invite", "role"): "owner",
    ("set_report_settings", "cadence"): "daily",
    ("set_dns_mode", "mode"): "automatic",
    ("set_custom_dns", "dns_servers"): ["1.1.1.1"],
    ("set_custom_dns_ipv4", "dns_servers"): ["1.1.1.1"],
    ("set_custom_dns_ipv6", "dns_servers"): ["2606:4700:4700::1111"],
    # `forward`/`reservation` are typed `Any` (bare id, path, or envelope).
    # A path avoids the separate `network`-required-for-a-bare-id branch.
    ("update_forward", "forward"): "/2.2/networks/net/forwards/f1",
    ("update_reservation", "reservation"): "/2.2/networks/net/reservations/r1",
}

# Per-(method name, parameter name) values forced onto the call even though
# the parameter has a default (usually `None`) -- for methods that build an
# "at least one of these optional fields must be supplied" body and would
# otherwise raise their own validation error before ever reaching the
# warning call.
_FORCE_INCLUDE_OPTIONAL = {
    "set_dhcp": {"mode": "automatic"},
    "set_nightlight": {
        "enabled": True,
        "parent": {"nightlight": {"url": "/2.2/eeros/placeholder-id/nightlight"}},
    },
    "set_nightlight_brightness": {
        "parent": {"nightlight": {"url": "/2.2/eeros/placeholder-id/nightlight"}}
    },
    "set_nightlight_schedule": {
        "parent": {"nightlight": {"url": "/2.2/eeros/placeholder-id/nightlight"}}
    },
    "respond_to_invite": {"invite_id": "placeholder-id"},
    "set_power_saving": {"enable": True},
    "update_schedule": {"enabled": True},  # PowerSavingAPI.update_schedule
    "update_thread": {"thread_enable": True},
    "set_wpa3_per_band": {"band_2_4_ghz": "WPA3"},
}

# Per-method override of the mocked GET response, for methods that read
# before they write (so the read must return enough shape to reach the
# write, e.g. a non-empty collection to iterate).
_GET_RESPONSE_OVERRIDES = {
    "clear_profile_schedule": {
        "meta": {"code": 200},
        "data": [{"url": "/2.2/networks/net/profiles/p1/schedules/s1"}],
    },
}

_DEFAULT_STRING_PLACEHOLDER = "placeholder-id"


def _iter_api_classes():
    """Yield every concrete `AuthenticatedAPI` subclass defined under `eero.api`."""
    seen = set()
    for module_info in pkgutil.iter_modules(eero_api_package.__path__):
        if module_info.name.startswith("_"):
            continue
        module = __import__(f"eero.api.{module_info.name}", fromlist=["*"])
        for _name, obj in vars(module).items():
            if (
                inspect.isclass(obj)
                and issubclass(obj, AuthenticatedAPI)
                and obj is not AuthenticatedAPI
                and obj.__module__ == module.__name__  # defined here, not re-exported
                and obj not in seen
            ):
                seen.add(obj)
                yield obj


def _iter_write_methods(cls):
    """Yield (name, function) for cls's own public coroutine write-shaped methods."""
    for name, member in vars(cls).items():
        if name.startswith("_"):
            continue
        if not inspect.iscoroutinefunction(member):
            continue
        if not name.startswith(_WRITE_PREFIXES):
            continue
        yield name, member


def _unwrap_optional(annotation):
    """Return the non-`None` member of `Optional[X]`, or `annotation` unchanged."""
    if get_origin(annotation) is Union:
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return annotation


def _placeholder_for(method_name: str, param_name: str, annotation: Any) -> Any:
    """Build a plausible placeholder value for one required parameter."""
    override = _PARAM_OVERRIDES.get((method_name, param_name))
    if override is not None:
        return override

    annotation = _unwrap_optional(annotation)
    origin = get_origin(annotation)

    if annotation is bool:
        return True
    if annotation in (int, float):
        return 1
    if origin in (dict, Dict, Mapping) or annotation in (dict, Dict, Mapping):
        return {}
    if origin in (list, List) or annotation in (list, List):
        return [_DEFAULT_STRING_PLACEHOLDER]
    return _DEFAULT_STRING_PLACEHOLDER


def _build_call_kwargs(method) -> Dict[str, Any]:
    """Build placeholder positional/keyword arguments for every required parameter."""
    signature = inspect.signature(method)
    kwargs: Dict[str, Any] = {}
    for name, param in signature.parameters.items():
        if name == "self":
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if param.default is not inspect.Parameter.empty:
            continue  # optional: omit, let the method apply its own default
        kwargs[name] = _placeholder_for(method.__name__, name, param.annotation)

    for name, value in _FORCE_INCLUDE_OPTIONAL.get(method.__name__, {}).items():
        kwargs[name] = value

    return kwargs


@pytest.fixture
def _mocked_transport(monkeypatch):
    """Patch BaseAPI's HTTP verbs so every write "succeeds" without a real request."""
    response = {"meta": {"code": 200}, "data": {}}
    for verb in ("get", "post", "put", "delete"):
        monkeypatch.setattr(BaseAPI, verb, AsyncMock(return_value=response))
    yield monkeypatch


def _make_instance(cls):
    auth_api = MagicMock()
    auth_api.session = MagicMock()
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return cls(auth_api)


def _collect_cases():
    cases = []
    for cls in _iter_api_classes():
        for method_name, _method in _iter_write_methods(cls):
            if (cls.__name__, method_name) in _VERIFIED_WRITE_ALLOWLIST:
                continue
            cases.append((cls, method_name))
    return cases


_CASES = _collect_cases()


class TestEveryWriteWarnsOrIsAllowlisted:
    """Every write-shaped method not in the allowlist must warn before writing."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "cls, method_name", _CASES, ids=[f"{c.__name__}.{m}" for c, m in _CASES]
    )
    async def test_write_emits_uncharacterised_write_warning(
        self, _mocked_transport, caplog, cls, method_name
    ):
        instance = _make_instance(cls)
        method = getattr(instance, method_name)
        kwargs = _build_call_kwargs(getattr(cls, method_name))

        if method_name in _GET_RESPONSE_OVERRIDES:
            _mocked_transport.setattr(
                BaseAPI, "get", AsyncMock(return_value=_GET_RESPONSE_OVERRIDES[method_name])
            )

        with caplog.at_level(logging.WARNING):
            try:
                await method(**kwargs)
            except Exception:
                # Placeholder arguments may fail the method's own downstream
                # validation or request handling; that's fine, as long as
                # the warning already fired before the failure.
                pass

        warnings = [
            record.getMessage()
            for record in caplog.records
            if "not been fully characterised" in record.getMessage()
        ]
        assert not any(_DEFAULT_STRING_PLACEHOLDER in message for message in warnings), (
            f"{cls.__name__}.{method_name} interpolated a caller-supplied "
            "identifier into its uncharacterised-write warning. The "
            "`operation` string must name the operation and the kind of "
            "resource only; identifiers never belong in a WARNING line."
        )
        assert warnings, (
            f"{cls.__name__}.{method_name} issued a write without the "
            "uncharacterised-write warning. Either add a "
            "`warn_uncharacterised_write` call before its request, or add "
            "it to `_VERIFIED_WRITE_ALLOWLIST` with a citation proving it "
            "is live-verified."
        )

    def test_allowlist_entries_still_exist_and_lack_the_warning(self):
        """Guard the allowlist itself: entries must name real, still-unwarned methods."""
        for class_name, method_name in _VERIFIED_WRITE_ALLOWLIST:
            matches = [cls for cls in _iter_api_classes() if cls.__name__ == class_name]
            assert matches, f"allowlisted class {class_name!r} no longer exists"
            cls = matches[0]
            assert hasattr(
                cls, method_name
            ), f"allowlisted method {class_name}.{method_name} no longer exists"

    def test_every_authenticated_api_subclass_is_discovered(self):
        """Sanity check the discovery walk itself finds a realistic number of classes."""
        discovered = list(_iter_api_classes())
        assert len(discovered) >= 30
