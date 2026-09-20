"""Tests for eero.api._params shared helpers."""

import pytest

from eero.api._params import (
    CADENCE_VALUES,
    resolve_nested_url,
    resolve_network_url,
    validate_cadence,
)
from eero.exceptions import EeroValidationException


class TestValidateCadence:
    """Tests for validate_cadence."""

    @pytest.mark.parametrize("value", CADENCE_VALUES)
    def test_accepts_valid_values(self, value):
        assert validate_cadence(value) == value

    @pytest.mark.parametrize("value", ["weekly", "", None, "DAILY", 1])
    def test_rejects_invalid_values(self, value):
        with pytest.raises(EeroValidationException):
            validate_cadence(value)


class TestResolveNetworkUrl:
    """Tests for resolve_network_url."""

    def test_bare_id_builds_default_version_url(self):
        url = resolve_network_url("network_123")
        assert url == "https://api-user.e2ro.com/2.2/networks/network_123"

    def test_absolute_url_passes_through(self):
        url = resolve_network_url("https://api-user.e2ro.com/2.3/networks/network_123")
        assert url == "https://api-user.e2ro.com/2.3/networks/network_123"

    def test_path_is_joined_onto_host(self):
        url = resolve_network_url("/2.3/networks/network_123")
        assert url == "https://api-user.e2ro.com/2.3/networks/network_123"

    def test_parent_self_url_is_preferred(self):
        parent = {"url": "/2.3/networks/network_123"}
        url = resolve_network_url("network_123", parent)
        assert url == "https://api-user.e2ro.com/2.3/networks/network_123"

    def test_parent_without_url_falls_back_to_network_id(self):
        parent = {"name": "Home"}
        url = resolve_network_url("network_123", parent)
        assert url == "https://api-user.e2ro.com/2.2/networks/network_123"

    def test_parent_as_full_envelope_is_unwrapped(self):
        parent = {"meta": {"code": 200}, "data": {"url": "/2.3/networks/network_123"}}
        url = resolve_network_url("network_123", parent)
        assert url == "https://api-user.e2ro.com/2.3/networks/network_123"


class TestResolveNestedUrlChildValidation:
    """A bare child id must be a single path segment before it is templated."""

    @pytest.mark.parametrize(
        "child",
        ["../account", "device?x=1", "a/b", "id#frag", "", " "],
        ids=["dot-segment", "query", "slash", "fragment", "empty", "blank"],
    )
    def test_bare_child_that_is_not_a_single_segment_is_rejected(self, child):
        with pytest.raises(EeroValidationException):
            resolve_nested_url("network_123", child, prefix="profiles", suffix="/schedules")

    def test_valid_bare_child_is_templated_with_suffix(self):
        url = resolve_nested_url("network_123", "profile_1", prefix="profiles", suffix="/schedules")
        assert (
            url == "https://api-user.e2ro.com/2.2/networks/network_123/profiles/profile_1/schedules"
        )

    def test_path_child_bypasses_the_template(self):
        url = resolve_nested_url(
            "network_123",
            "/2.3/networks/network_123/profiles/profile_1",
            prefix="profiles",
            suffix="/schedules",
        )
        assert (
            url == "https://api-user.e2ro.com/2.3/networks/network_123/profiles/profile_1/schedules"
        )


class TestResolveNestedUrlPathChildFamily:
    """A path or URL child must name the addressed network's nested resource."""

    @pytest.mark.parametrize(
        "child",
        [
            "/2.2/account",
            "/2.2/networks/network_123/forwards/f_1",
            "/2.2/networks/other_net/profiles/profile_1",
            "/2.2/networks/network_123/profiles/profile_1?x=1",
            "/2.2/networks/network_123/profiles/profile_1#frag",
            "/2.2/networks/network_123/profiles/profile_1/extra",
            "https://api-user.e2ro.com/2.2/networks/network_123/profiles",
        ],
        ids=[
            "other-resource",
            "other-family",
            "other-network",
            "query",
            "fragment",
            "extra",
            "no-child",
        ],
    )
    def test_path_outside_the_family_is_rejected(self, child):
        with pytest.raises(EeroValidationException):
            resolve_nested_url("network_123", child, prefix="profiles", suffix="/schedules")

    def test_path_child_in_the_family_is_accepted(self):
        url = resolve_nested_url(
            "network_123",
            "/2.3/networks/network_123/profiles/profile_1",
            prefix="profiles",
            suffix="/schedules",
        )
        assert (
            url == "https://api-user.e2ro.com/2.3/networks/network_123/profiles/profile_1/schedules"
        )

    def test_path_network_and_path_child_must_agree(self):
        with pytest.raises(EeroValidationException):
            resolve_nested_url(
                "/2.2/networks/network_123", "/2.2/networks/other_net/profiles/p", prefix="profiles"
            )
        url = resolve_nested_url(
            "/2.2/networks/network_123", "/2.2/networks/network_123/profiles/p", prefix="profiles"
        )
        assert url == "https://api-user.e2ro.com/2.2/networks/network_123/profiles/p"
