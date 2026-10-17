"""Repository-wide check: every domain-API method has an `EeroClient` wrapper.

This module builds a real `eero.api.EeroAPI` (construction performs no I/O),
walks every attribute on it that is an `eero.api.base.AuthenticatedAPI`
instance, and enumerates each class's OWN public coroutine methods
(``vars(cls)``, so the transport verbs inherited from `BaseAPI` --
``get``/``post``/``put``/``delete``/``close`` -- are excluded). For each
``(attribute, method)`` pair, the source of `eero.client.EeroClient` must
contain a call to ``self._api.<attribute>.<method>(``, or the pair must be
listed in `_FACADE_PARITY_ALLOWLIST` below, with a comment saying why the
facade intentionally has no same-named wrapper.

Scope: `eero.api.auth.AuthAPI` is not an `AuthenticatedAPI`, so it is out of
scope by construction. Its facade counterparts are ``login``, ``verify``,
``logout``, ``resend_verification_code``, ``clear_auth_data``,
``set_session_token`` and ``clear_session_token``. ``refresh_session``,
``ensure_authenticated`` and ``get_auth_token`` are session plumbing that the
facade deliberately does not wrap.

This is a regression guard, not a design decision: it exists so a new
domain-API method can't silently ship without a facade wrapper (the
high-level `EeroClient` is what most callers use, so a method missing there is
effectively unreachable for them). Allowlist discipline: an entry is only
legitimate when the facade exposes the same capability under a DIFFERENT
name or by delegating through another domain method, and its comment must
say which. Never allowlist a method just to make this test pass -- add the
wrapper instead. Stale entries fail `test_allowlist_entries_name_real_methods`.
"""

import inspect
import re
from typing import Iterator, List, Set, Tuple

import pytest

import eero.client
from eero.api import EeroAPI
from eero.api.base import AuthenticatedAPI

# ========================== Facade-parity allowlist ==========================
#
# Each entry is an (EeroAPI attribute, method) pair whose facade wrapper has a
# different name, or reaches the domain layer through a different method.
_FACADE_PARITY_ALLOWLIST: Set[Tuple[str, str]] = {
    # client.py: EeroClient.set_nightlight_brightness exists under the same
    # name but is a convenience wrapper that delegates to
    # EeroClient.set_nightlight(brightness_percentage=...), which is the
    # method that calls EerosAPI.set_nightlight. It never calls the
    # same-named domain method.
    ("eeros", "set_nightlight_brightness"),
    # client.py: EeroClient.set_nightlight_schedule exists under the same name
    # but delegates to EeroClient.set_nightlight(schedule=...) in the same
    # way, so EerosAPI.set_nightlight_schedule is never called directly.
    ("eeros", "set_nightlight_schedule"),
}


def _discover_domain_apis() -> List[Tuple[str, type]]:
    """Return (attribute name, class) for every AuthenticatedAPI wired into EeroAPI."""
    api = EeroAPI()
    return [
        (attr, type(value))
        for attr, value in vars(api).items()
        if isinstance(value, AuthenticatedAPI)
    ]


def _iter_public_coroutines(cls: type) -> Iterator[str]:
    """Yield the names of cls's own public coroutine methods."""
    for name, member in vars(cls).items():
        if not name.startswith("_") and inspect.iscoroutinefunction(member):
            yield name


def _collect_pairs() -> List[Tuple[str, str]]:
    return [
        (attr, method)
        for attr, cls in _discover_domain_apis()
        for method in _iter_public_coroutines(cls)
    ]


def _facade_source() -> str:
    """Return EeroClient's module source with all whitespace runs collapsed."""
    path = inspect.getsourcefile(eero.client.EeroClient)
    assert path is not None, "cannot locate the source file of EeroClient"
    with open(path, encoding="utf-8") as handle:
        return re.sub(r"\s+", " ", handle.read())


_PAIRS = _collect_pairs()
_CHECKED = [pair for pair in _PAIRS if pair not in _FACADE_PARITY_ALLOWLIST]
_FACADE_SOURCE = _facade_source()


class TestFacadeParity:
    """Every domain-API method is called from some `EeroClient` wrapper."""

    @pytest.mark.parametrize("attr, method", _CHECKED, ids=[f"{a}.{m}" for a, m in _CHECKED])
    def test_domain_method_has_facade_wrapper(self, attr, method):
        needle = f"self._api.{attr}.{method}("
        assert needle in _FACADE_SOURCE, (
            f"EeroClient has no wrapper that calls `{needle}`. Add a same-named "
            "wrapper to src/eero/client.py, or (only if the facade exposes the "
            "capability under a different name) add the pair to "
            "`_FACADE_PARITY_ALLOWLIST` with a comment naming the wrapper."
        )

    def test_allowlist_entries_name_real_methods(self):
        """Guard the allowlist itself: entries must name real domain methods."""
        known = set(_PAIRS)
        stale = sorted(_FACADE_PARITY_ALLOWLIST - known)
        assert not stale, f"allowlisted pairs no longer exist on EeroAPI: {stale}"

    def test_allowlist_entries_are_actually_unwrapped(self):
        """Guard the allowlist itself: an entry whose wrapper now exists is redundant."""
        redundant = sorted(
            (attr, method)
            for attr, method in _FACADE_PARITY_ALLOWLIST
            if f"self._api.{attr}.{method}(" in _FACADE_SOURCE
        )
        assert not redundant, f"allowlisted pairs now have a same-named wrapper: {redundant}"

    def test_discovery_finds_a_realistic_surface(self):
        """Sanity check the discovery walk itself finds a realistic number of APIs/methods."""
        assert len(_discover_domain_apis()) >= 30
        assert len(_PAIRS) >= 150
