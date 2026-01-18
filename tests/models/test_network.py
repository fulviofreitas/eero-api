"""Tests for Network model.

Tests cover:
- Network model with minimal required fields
- Network model with all optional fields
- DHCP configuration parsing
- Guest network settings
- Network status enum handling
- NetworkSettings model
"""

from datetime import datetime

from eero.const import EeroNetworkStatus
from eero.models.network import DHCP, Network, NetworkSettings

# ========================== NetworkSettings Tests ==========================


class TestNetworkSettings:
    """Tests for NetworkSettings model."""

    def test_default_settings(self):
        """Test NetworkSettings with default values."""
        settings = NetworkSettings()

        assert settings.ipv6_upstream is False
        assert settings.band_steering is False
        assert settings.thread_enabled is False
        assert settings.upnp_enabled is False
        assert settings.wpa3_transition is False
        assert settings.dns_caching is True  # Default is True
        assert settings.ipv6_downstream is False
        assert settings.target_firmware is None
        assert settings.gateway_mac_address is None

    def test_settings_all_enabled(self):
        """Test NetworkSettings with all features enabled."""
        settings = NetworkSettings(
            ipv6_upstream=True,
            band_steering=True,
            thread_enabled=True,
            upnp_enabled=True,
            wpa3_transition=True,
            dns_caching=True,
            ipv6_downstream=True,
            target_firmware="7.1.0",
            gateway_mac_address="AA:BB:CC:DD:EE:FF",
        )

        assert settings.ipv6_upstream is True
        assert settings.band_steering is True
        assert settings.thread_enabled is True
        assert settings.upnp_enabled is True
        assert settings.wpa3_transition is True
        assert settings.target_firmware == "7.1.0"
        assert settings.gateway_mac_address == "AA:BB:CC:DD:EE:FF"


# ========================== DHCP Tests ==========================


class TestDHCP:
    """Tests for DHCP model."""

    def test_dhcp_defaults(self):
        """Test DHCP with default values."""
        dhcp = DHCP()

        assert dhcp.lease_time_seconds == 86400  # 24 hours
        assert dhcp.dns_server is None
        assert dhcp.subnet_mask == "255.255.255.0"
        assert dhcp.starting_address == "192.168.4.2"
        assert dhcp.ending_address == "192.168.4.254"

    def test_dhcp_custom_values(self):
        """Test DHCP with custom values."""
        dhcp = DHCP(
            lease_time_seconds=3600,
            dns_server="8.8.8.8",
            subnet_mask="255.255.0.0",
            starting_address="10.0.0.2",
            ending_address="10.0.255.254",
        )

        assert dhcp.lease_time_seconds == 3600
        assert dhcp.dns_server == "8.8.8.8"
        assert dhcp.subnet_mask == "255.255.0.0"
        assert dhcp.starting_address == "10.0.0.2"
        assert dhcp.ending_address == "10.0.255.254"


# ========================== Network Basic Tests ==========================


class TestNetworkBasic:
    """Tests for basic Network model functionality."""

    def test_network_minimal_fields(self):
        """Test Network with only required fields."""
        network = Network(
            id="network_123",
            name="Home Network",
        )

        assert network.id == "network_123"
        assert network.name == "Home Network"
        # Status should have a default
        assert network.status is not None

    def test_network_all_core_fields(self):
        """Test Network with all core fields."""
        network = Network(
            id="network_123",
            name="Home Network",
            status="online",
            public_ip="203.0.113.42",
            isp_name="Example ISP",
            guest_network_enabled=True,
            guest_network_name="Guest Network",
            guest_network_password="guest123",
            url="/2.2/networks/network_123",
        )

        assert network.id == "network_123"
        assert network.name == "Home Network"
        assert network.public_ip == "203.0.113.42"
        assert network.isp_name == "Example ISP"
        assert network.guest_network_enabled is True
        assert network.guest_network_name == "Guest Network"
        assert network.guest_network_password == "guest123"
        assert network.url == "/2.2/networks/network_123"

    def test_network_with_timestamps(self):
        """Test Network with timestamp fields."""
        now = datetime.now()
        network = Network(
            id="network_123",
            name="Home Network",
            created_at=now,
            updated_at=now,
        )

        assert network.created_at == now
        assert network.updated_at == now


# ========================== Network Status Tests ==========================


class TestNetworkStatus:
    """Tests for Network status handling."""

    def test_status_string_online(self):
        """Test status with 'online' string."""
        network = Network(
            id="network_123",
            name="Home Network",
            status="online",
        )

        assert network.status == EeroNetworkStatus.ONLINE

    def test_status_string_connected(self):
        """Test status with 'connected' string (API format)."""
        network = Network(
            id="network_123",
            name="Home Network",
            status="connected",
        )

        # "connected" should be converted to ONLINE
        assert network.status == EeroNetworkStatus.ONLINE

    def test_status_string_offline(self):
        """Test status with 'offline' string."""
        network = Network(
            id="network_123",
            name="Home Network",
            status="offline",
        )

        assert network.status == EeroNetworkStatus.OFFLINE

    def test_status_string_updating(self):
        """Test status with 'updating' string."""
        network = Network(
            id="network_123",
            name="Home Network",
            status="updating",
        )

        assert network.status == EeroNetworkStatus.UPDATING

    def test_status_enum_direct(self):
        """Test status with enum value directly."""
        network = Network(
            id="network_123",
            name="Home Network",
            status=EeroNetworkStatus.ONLINE,
        )

        assert network.status == EeroNetworkStatus.ONLINE


# ========================== Network DHCP Tests ==========================


class TestNetworkDHCP:
    """Tests for Network DHCP configuration."""

    def test_network_with_dhcp(self):
        """Test Network with DHCP configuration."""
        network = Network(
            id="network_123",
            name="Home Network",
            dhcp=DHCP(
                lease_time_seconds=7200,
                subnet_mask="255.255.255.0",
                starting_address="192.168.1.100",
                ending_address="192.168.1.200",
            ),
        )

        assert network.dhcp is not None
        assert network.dhcp.lease_time_seconds == 7200
        assert network.dhcp.starting_address == "192.168.1.100"
        assert network.dhcp.ending_address == "192.168.1.200"

    def test_network_without_dhcp(self):
        """Test Network without DHCP configuration."""
        network = Network(
            id="network_123",
            name="Home Network",
        )

        assert network.dhcp is None


# ========================== Network Guest Network Tests ==========================


class TestNetworkGuestNetwork:
    """Tests for Network guest network settings."""

    def test_guest_network_enabled(self):
        """Test Network with guest network enabled."""
        network = Network(
            id="network_123",
            name="Home Network",
            guest_network_enabled=True,
            guest_network_name="My Guest",
            guest_network_password="securepass",
        )

        assert network.guest_network_enabled is True
        assert network.guest_network_name == "My Guest"
        assert network.guest_network_password == "securepass"

    def test_guest_network_disabled(self):
        """Test Network with guest network disabled."""
        network = Network(
            id="network_123",
            name="Home Network",
            guest_network_enabled=False,
        )

        assert network.guest_network_enabled is False
        assert network.guest_network_name is None
        assert network.guest_network_password is None


# ========================== Network Additional Fields Tests ==========================


class TestNetworkAdditionalFields:
    """Tests for additional Network fields."""

    def test_network_security_settings(self):
        """Test Network security-related fields."""
        network = Network(
            id="network_123",
            name="Home Network",
            wpa3=True,
            band_steering=True,
            upnp=False,
            thread=True,
            ipv6_upstream=True,
            sqm=True,
        )

        assert network.wpa3 is True
        assert network.band_steering is True
        assert network.upnp is False
        assert network.thread is True
        assert network.ipv6_upstream is True
        assert network.sqm is True

    def test_network_wan_settings(self):
        """Test Network WAN-related fields."""
        network = Network(
            id="network_123",
            name="Home Network",
            public_ip="203.0.113.42",
            gateway_ip="192.168.1.1",
            wan_type="dhcp",
            connection_mode="bridge",
        )

        assert network.public_ip == "203.0.113.42"
        assert network.gateway_ip == "192.168.1.1"
        assert network.wan_type == "dhcp"
        assert network.connection_mode == "bridge"

    def test_network_premium_status(self):
        """Test Network premium status fields."""
        network = Network(
            id="network_123",
            name="Home Network",
            premium_status="active",
            premium_details={"plan": "eero Plus", "expires_at": "2025-12-31"},
        )

        assert network.premium_status == "active"
        assert network.premium_details is not None
        assert network.premium_details["plan"] == "eero Plus"

    def test_network_integration_flags(self):
        """Test Network integration flags."""
        network = Network(
            id="network_123",
            name="Home Network",
            amazon_account_linked=True,
            alexa_skill=True,
            ffs=False,
            backup_internet_enabled=True,
            power_saving=False,
        )

        assert network.amazon_account_linked is True
        assert network.alexa_skill is True
        assert network.ffs is False
        assert network.backup_internet_enabled is True
        assert network.power_saving is False


# ========================== Network API Response Tests ==========================


class TestNetworkAPIResponse:
    """Tests for parsing Network from API response."""

    def test_parse_from_api_response(self):
        """Test parsing Network from typical API response."""
        api_response = {
            "id": "network_123",
            "url": "/2.2/networks/network_123",
            "name": "Home Network",
            "status": "connected",
            "wan_ip": "203.0.113.42",
            "geo_ip": {"isp": "Example ISP"},
            "guest_network": {
                "enabled": True,
                "name": "Guest",
                "password": "pass123",
            },
            "band_steering": True,
            "wpa3": True,
            "upnp": False,
        }

        network = Network.model_validate(api_response)

        assert network.id == "network_123"
        assert network.name == "Home Network"
        assert network.status == EeroNetworkStatus.ONLINE
        assert network.band_steering is True
        assert network.wpa3 is True
        assert network.upnp is False

    def test_parse_with_extra_fields(self):
        """Test that extra fields are ignored."""
        api_response = {
            "id": "network_123",
            "name": "Home Network",
            "unknown_field": "some_value",
            "another_unknown": 123,
        }

        # Should not raise
        network = Network.model_validate(api_response)

        assert network.id == "network_123"
        assert network.name == "Home Network"

    def test_parse_minimal_response(self):
        """Test parsing Network from minimal API response."""
        api_response = {
            "id": "network_123",
            "name": "Home",
        }

        network = Network.model_validate(api_response)

        assert network.id == "network_123"
        assert network.name == "Home"
        # Defaults should be applied
        assert network.guest_network_enabled is False


# ========================== Network Settings Integration Tests ==========================


class TestNetworkSettingsIntegration:
    """Tests for NetworkSettings integration with Network."""

    def test_network_with_custom_settings(self):
        """Test Network with custom NetworkSettings."""
        custom_settings = NetworkSettings(
            ipv6_upstream=True,
            band_steering=True,
            wpa3_transition=True,
        )

        network = Network(
            id="network_123",
            name="Home Network",
            settings=custom_settings,
        )

        assert network.settings.ipv6_upstream is True
        assert network.settings.band_steering is True
        assert network.settings.wpa3_transition is True

    def test_network_default_settings(self):
        """Test Network has default settings when not provided."""
        network = Network(
            id="network_123",
            name="Home Network",
        )

        assert network.settings is not None
        assert isinstance(network.settings, NetworkSettings)
