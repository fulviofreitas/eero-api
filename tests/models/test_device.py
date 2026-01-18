"""Tests for Device model.

Tests cover:
- Device model with minimal fields
- Device model with all optional fields
- Device connection status handling
- Device status enum (connected/disconnected/blocked)
- ID extraction from URL
- MAC address handling
- Profile association
"""

from datetime import datetime

from eero.const import EeroDeviceStatus
from eero.models.device import (
    Device,
    DeviceConnection,
    DeviceConnectivity,
    DeviceProfile,
    DeviceSource,
    DeviceTag,
)

# ========================== DeviceTag Tests ==========================


class TestDeviceTag:
    """Tests for DeviceTag model."""

    def test_device_tag_all_fields(self):
        """Test DeviceTag with all fields."""
        tag = DeviceTag(id="tag_1", name="IoT Device", color="blue")

        assert tag.id == "tag_1"
        assert tag.name == "IoT Device"
        assert tag.color == "blue"

    def test_device_tag_optional_fields(self):
        """Test DeviceTag with optional fields as None."""
        tag = DeviceTag()

        assert tag.id is None
        assert tag.name is None
        assert tag.color is None


# ========================== DeviceConnection Tests ==========================


class TestDeviceConnection:
    """Tests for DeviceConnection model."""

    def test_device_connection_wireless(self):
        """Test DeviceConnection for wireless device."""
        conn = DeviceConnection(
            type="wireless",
            connected_to="eero_001",
            connected_via="wifi",
            frequency="5GHz",
            signal_strength=-45,
            tx_rate=866,
            rx_rate=866,
        )

        assert conn.type == "wireless"
        assert conn.connected_to == "eero_001"
        assert conn.frequency == "5GHz"
        assert conn.signal_strength == -45

    def test_device_connection_wired(self):
        """Test DeviceConnection for wired device."""
        conn = DeviceConnection(
            type="wired",
            connected_to="eero_001",
            connected_via="ethernet",
        )

        assert conn.type == "wired"
        assert conn.connected_via == "ethernet"
        assert conn.frequency is None


# ========================== DeviceSource Tests ==========================


class TestDeviceSource:
    """Tests for DeviceSource model."""

    def test_device_source_gateway(self):
        """Test DeviceSource for gateway eero."""
        source = DeviceSource(
            location="Living Room",
            is_gateway=True,
            model="eero Pro 6E",
            display_name="Living Room",
            serial_number="ABC123",
            url="/2.2/eeros/eero_001",
        )

        assert source.location == "Living Room"
        assert source.is_gateway is True
        assert source.model == "eero Pro 6E"

    def test_device_source_extender(self):
        """Test DeviceSource for extender eero."""
        source = DeviceSource(
            location="Bedroom",
            is_gateway=False,
            model="eero Beacon",
        )

        assert source.is_gateway is False


# ========================== DeviceConnectivity Tests ==========================


class TestDeviceConnectivity:
    """Tests for DeviceConnectivity model."""

    def test_device_connectivity_wireless(self):
        """Test DeviceConnectivity for wireless device."""
        connectivity = DeviceConnectivity(
            rx_bitrate="866 Mbps",
            tx_bitrate="866 Mbps",
            signal="-45 dBm",
            score=0.95,
            score_bars=4,
            frequency=5180,
        )

        assert connectivity.rx_bitrate == "866 Mbps"
        assert connectivity.score == 0.95
        assert connectivity.score_bars == 4
        assert connectivity.frequency == 5180


# ========================== DeviceProfile Tests ==========================


class TestDeviceProfile:
    """Tests for DeviceProfile model."""

    def test_device_profile(self):
        """Test DeviceProfile model."""
        profile = DeviceProfile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            paused=True,
        )

        assert profile.name == "Kids"
        assert profile.paused is True


# ========================== Device Basic Tests ==========================


class TestDeviceBasic:
    """Tests for basic Device model functionality."""

    def test_device_minimal_fields(self):
        """Test Device with minimal fields."""
        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
        )

        assert device.url == "/2.2/networks/network_123/devices/abc123"

    def test_device_core_fields(self):
        """Test Device with core identification fields."""
        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            mac="AA:BB:CC:DD:EE:FF",
            hostname="iPhone",
            display_name="John's iPhone",
            nickname="John's Phone",
            ip="192.168.1.100",
            manufacturer="Apple Inc.",
        )

        assert device.mac == "AA:BB:CC:DD:EE:FF"
        assert device.hostname == "iPhone"
        assert device.display_name == "John's iPhone"
        assert device.nickname == "John's Phone"
        assert device.ip == "192.168.1.100"
        assert device.manufacturer == "Apple Inc."


# ========================== Device ID Extraction Tests ==========================


class TestDeviceIDExtraction:
    """Tests for Device ID extraction from URL."""

    def test_extract_device_id_from_url(self):
        """Test device ID extraction from URL."""
        device = Device(
            url="/2.2/networks/3401709/devices/44070b35c7b2",
        )

        assert device.id == "44070b35c7b2"

    def test_extract_network_id_from_url(self):
        """Test network ID extraction from URL."""
        device = Device(
            url="/2.2/networks/3401709/devices/44070b35c7b2",
        )

        assert device.network_id == "3401709"

    def test_no_extraction_without_url(self):
        """Test no ID extraction when URL not provided."""
        device = Device()

        assert device.id is None
        assert device.network_id is None


# ========================== Device Connection Status Tests ==========================


class TestDeviceConnectionStatus:
    """Tests for Device connection status."""

    def test_device_connected(self):
        """Test connected device status."""
        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            connected=True,
            blacklisted=False,
        )

        assert device.connected is True
        assert device.status == EeroDeviceStatus.CONNECTED

    def test_device_disconnected(self):
        """Test disconnected device status."""
        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            connected=False,
        )

        assert device.connected is False
        assert device.status == EeroDeviceStatus.DISCONNECTED

    def test_device_blocked(self):
        """Test blocked device status."""
        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            connected=True,
            blacklisted=True,
        )

        assert device.blacklisted is True
        assert device.status == EeroDeviceStatus.BLOCKED


# ========================== Device Wireless Tests ==========================


class TestDeviceWireless:
    """Tests for Device wireless settings."""

    def test_device_wireless(self):
        """Test wireless device."""
        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            wireless=True,
            connection_type="wireless",
        )

        assert device.wireless is True
        assert device.connection_type == "wireless"

    def test_device_wired(self):
        """Test wired device."""
        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            wireless=False,
            connection_type="wired",
        )

        assert device.wireless is False
        assert device.connection_type == "wired"


# ========================== Device IP Addresses Tests ==========================


class TestDeviceIPAddresses:
    """Tests for Device IP address handling."""

    def test_device_single_ip(self):
        """Test device with single IP."""
        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            ip="192.168.1.100",
            ipv4="192.168.1.100",
        )

        assert device.ip == "192.168.1.100"
        assert device.ipv4 == "192.168.1.100"

    def test_device_multiple_ips(self):
        """Test device with multiple IPs."""
        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            ips=["192.168.1.100", "192.168.1.101"],
        )

        assert len(device.ips) == 2
        assert "192.168.1.100" in device.ips


# ========================== Device Source Association Tests ==========================


class TestDeviceSourceAssociation:
    """Tests for Device source (connected eero) association."""

    def test_device_with_source(self):
        """Test device with source eero information."""
        source = DeviceSource(
            location="Living Room",
            is_gateway=True,
            model="eero Pro 6E",
            url="/2.2/eeros/eero_001",
        )

        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            source=source,
        )

        assert device.source is not None
        assert device.source.location == "Living Room"
        assert device.source.is_gateway is True


# ========================== Device Profile Association Tests ==========================


class TestDeviceProfileAssociation:
    """Tests for Device profile association."""

    def test_device_with_profile(self):
        """Test device with profile association."""
        profile = DeviceProfile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            paused=False,
        )

        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            profile=profile,
        )

        assert device.profile is not None
        assert device.profile.name == "Kids"
        assert device.profile_id == "profile_001"


# ========================== Device Timestamps Tests ==========================


class TestDeviceTimestamps:
    """Tests for Device timestamp handling."""

    def test_device_with_timestamps(self):
        """Test device with last_active and first_active."""
        now = datetime.now()

        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            last_active=now,
            first_active=now,
        )

        assert device.last_active == now
        assert device.first_active == now


# ========================== Device Status Flags Tests ==========================


class TestDeviceStatusFlags:
    """Tests for Device status flags."""

    def test_device_guest(self):
        """Test guest device flag."""
        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            is_guest=True,
        )

        assert device.is_guest is True

    def test_device_paused(self):
        """Test paused device flag."""
        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            paused=True,
        )

        assert device.paused is True

    def test_device_private(self):
        """Test private device flag."""
        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            is_private=True,
        )

        assert device.is_private is True


# ========================== Device API Response Tests ==========================


class TestDeviceAPIResponse:
    """Tests for parsing Device from API response."""

    def test_parse_from_api_response(self):
        """Test parsing Device from typical API response."""
        api_response = {
            "url": "/2.2/networks/network_123/devices/abc123",
            "mac": "AA:BB:CC:DD:EE:FF",
            "manufacturer": "Apple Inc.",
            "hostname": "iPhone",
            "nickname": "John's iPhone",
            "ip": "192.168.1.100",
            "connected": True,
            "blocked": False,
            "connection_type": "wireless",
            "source": {
                "location": "Living Room",
            },
        }

        device = Device.model_validate(api_response)

        assert device.mac == "AA:BB:CC:DD:EE:FF"
        assert device.hostname == "iPhone"
        assert device.connected is True
        assert device.status == EeroDeviceStatus.CONNECTED

    def test_parse_with_extra_fields(self):
        """Test that extra fields are allowed."""
        api_response = {
            "url": "/2.2/networks/network_123/devices/abc123",
            "unknown_field": "value",
            "another_unknown": 123,
        }

        # Should not raise - extra fields are allowed
        device = Device.model_validate(api_response)

        assert device.url == "/2.2/networks/network_123/devices/abc123"


# ========================== Device Tags Tests ==========================


class TestDeviceTags:
    """Tests for Device tags."""

    def test_device_with_tags(self):
        """Test device with multiple tags."""
        tags = [
            DeviceTag(id="tag_1", name="IoT", color="blue"),
            DeviceTag(id="tag_2", name="Critical", color="red"),
        ]

        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
            tags=tags,
        )

        assert len(device.tags) == 2
        assert device.tags[0].name == "IoT"
        assert device.tags[1].name == "Critical"

    def test_device_empty_tags(self):
        """Test device with no tags."""
        device = Device(
            url="/2.2/networks/network_123/devices/abc123",
        )

        assert device.tags == []
