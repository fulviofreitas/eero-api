"""Tests for eero.api._params shared helpers."""

import pytest

from eero.api._params import CADENCE_VALUES, resolve_network_url, validate_cadence
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
