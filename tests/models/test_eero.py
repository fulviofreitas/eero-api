"""Tests for Eero model.

Tests cover:
- Eero model with required fields
- Eero model with optional fields
- Gateway vs extender eeros
- LED settings
- Nightlight settings (Beacon only)
- Health status
- Ethernet status
- ID extraction from URL
"""

from eero.const import EeroDeviceType
from eero.models.eero import (
    Eero,
    EeroHealth,
    EthernetStatus,
    EthernetStatuses,
    Location,
)

# ========================== Location Tests ==========================


class TestLocation:
    """Tests for Location model."""

    def test_location_all_fields(self):
        """Test Location with all fields."""
        location = Location(
            lat=37.7749,
            lon=-122.4194,
            address="123 Main St",
            city="San Francisco",
            state="CA",
            country="USA",
            zip_code="94102",
        )

        assert location.lat == 37.7749
        assert location.lon == -122.4194
        assert location.city == "San Francisco"
        assert location.state == "CA"
        assert location.zip_code == "94102"

    def test_location_partial_fields(self):
        """Test Location with only some fields."""
        location = Location(city="New York", country="USA")

        assert location.city == "New York"
        assert location.country == "USA"
        assert location.lat is None
        assert location.lon is None


# ========================== EeroHealth Tests ==========================


class TestEeroHealth:
    """Tests for EeroHealth model."""

    def test_health_green(self):
        """Test healthy eero status."""
        health = EeroHealth(status="green", issues=[])

        assert health.status == "green"
        assert health.issues == []

    def test_health_with_issues(self):
        """Test eero health with issues."""
        health = EeroHealth(
            status="yellow",
            issues=[
                {"type": "weak_signal", "severity": "warning"},
                {"type": "high_utilization", "severity": "info"},
            ],
        )

        assert health.status == "yellow"
        assert len(health.issues) == 2


# ========================== EthernetStatus Tests ==========================


class TestEthernetStatus:
    """Tests for EthernetStatus model."""

    def test_ethernet_status_wan(self):
        """Test ethernet status for WAN port."""
        status = EthernetStatus(
            interfaceNumber=0,
            hasCarrier=True,
            speed="1000 Mbps",
            isWanPort=True,
            isLte=False,
            port_name="WAN",
        )

        assert status.interfaceNumber == 0
        assert status.hasCarrier is True
        assert status.speed == "1000 Mbps"
        assert status.isWanPort is True
        assert status.isLte is False

    def test_ethernet_status_lan(self):
        """Test ethernet status for LAN port."""
        status = EthernetStatus(
            interfaceNumber=1,
            hasCarrier=True,
            speed="1000 Mbps",
            isWanPort=False,
            port_name="LAN1",
        )

        assert status.isWanPort is False
        assert status.port_name == "LAN1"


# ========================== EthernetStatuses Tests ==========================


class TestEthernetStatuses:
    """Tests for EthernetStatuses model."""

    def test_ethernet_statuses_multiple_ports(self):
        """Test ethernet statuses with multiple ports."""
        statuses = EthernetStatuses(
            statuses=[
                EthernetStatus(interfaceNumber=0, hasCarrier=True, isWanPort=True),
                EthernetStatus(interfaceNumber=1, hasCarrier=True, isWanPort=False),
            ],
            wiredInternet=True,
            segmentId="segment_1",
        )

        assert len(statuses.statuses) == 2
        assert statuses.wiredInternet is True
        assert statuses.segmentId == "segment_1"


# ========================== Eero Basic Tests ==========================


class TestEeroBasic:
    """Tests for basic Eero model functionality."""

    def test_eero_required_fields(self):
        """Test Eero with only required fields."""
        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123456789",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",
            status="green",
        )

        assert eero.url == "/2.2/eeros/26172144"
        assert eero.serial == "ABC123456789"
        assert eero.mac_address == "AA:BB:CC:DD:EE:FF"
        assert eero.model == "eero Pro 6E"
        assert eero.status == "green"

    def test_eero_all_core_fields(self):
        """Test Eero with all core fields."""
        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123456789",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",
            status="green",
            name="Living Room",
            ip_address="192.168.4.1",
            firmware_version="7.1.0",
            connected=True,
            gateway=True,
            connected_clients_count=15,
        )

        assert eero.name == "Living Room"
        assert eero.ip_address == "192.168.4.1"
        assert eero.firmware_version == "7.1.0"
        assert eero.connected is True
        assert eero.gateway is True
        assert eero.connected_clients_count == 15


# ========================== Eero ID Extraction Tests ==========================


class TestEeroIDExtraction:
    """Tests for Eero ID extraction from URL."""

    def test_extract_eero_id_from_url(self):
        """Test eero ID extraction from URL."""
        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro",
            status="green",
        )

        assert eero.eero_id == "26172144"

    def test_extract_id_from_network_scoped_url(self):
        """Test eero ID extraction from network-scoped URL."""
        eero = Eero(
            url="/2.2/networks/network_123/eeros/eero_001",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro",
            status="green",
        )

        assert eero.eero_id == "eero_001"


# ========================== Eero Gateway Tests ==========================


class TestEeroGateway:
    """Tests for Eero gateway identification."""

    def test_eero_is_gateway(self):
        """Test gateway eero."""
        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",
            status="green",
            gateway=True,
            is_gateway=True,
            using_wan=True,
        )

        assert eero.gateway is True
        assert eero.is_gateway is True
        assert eero.using_wan is True

    def test_eero_is_extender(self):
        """Test extender (non-gateway) eero."""
        eero = Eero(
            url="/2.2/eeros/26172145",
            serial="DEF456",
            mac_address="11:22:33:44:55:66",
            model="eero Beacon",
            status="green",
            gateway=False,
            is_gateway=False,
            wired=False,
        )

        assert eero.gateway is False
        assert eero.is_gateway is False


# ========================== Eero LED Tests ==========================


class TestEeroLED:
    """Tests for Eero LED settings."""

    def test_eero_led_on(self):
        """Test eero with LED on."""
        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",
            status="green",
            led_on=True,
            led_brightness=100,
        )

        assert eero.led_on is True
        assert eero.led_brightness == 100

    def test_eero_led_off(self):
        """Test eero with LED off."""
        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",
            status="green",
            led_on=False,
        )

        assert eero.led_on is False

    def test_eero_led_dimmed(self):
        """Test eero with LED dimmed."""
        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",
            status="green",
            led_on=True,
            led_brightness=50,
        )

        assert eero.led_on is True
        assert eero.led_brightness == 50


# ========================== Eero Nightlight Tests ==========================


class TestEeroNightlight:
    """Tests for Eero Beacon nightlight settings."""

    def test_eero_nightlight_enabled(self):
        """Test eero beacon with nightlight enabled."""
        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Beacon",
            status="green",
            nightlight={
                "enabled": True,
                "brightness": 75,
                "brightness_percentage": 75,
                "ambient_light_enabled": False,
                "schedule": {"on": "20:00", "off": "06:00"},
            },
        )

        assert eero.nightlight is not None
        assert eero.nightlight["enabled"] is True
        assert eero.nightlight["brightness"] == 75

    def test_eero_nightlight_with_schedule(self):
        """Test eero beacon with nightlight schedule."""
        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Beacon",
            status="green",
            nightlight={
                "enabled": True,
                "schedule": {
                    "enabled": True,
                    "on": "21:00",
                    "off": "07:00",
                },
            },
        )

        assert eero.nightlight["schedule"]["enabled"] is True
        assert eero.nightlight["schedule"]["on"] == "21:00"
        assert eero.nightlight["schedule"]["off"] == "07:00"

    def test_eero_no_nightlight(self):
        """Test eero without nightlight (non-Beacon)."""
        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",  # Not a Beacon
            status="green",
        )

        assert eero.nightlight is None


# ========================== Eero Health Tests ==========================


class TestEeroHealthIntegration:
    """Tests for Eero health integration."""

    def test_eero_with_health(self):
        """Test eero with health status."""
        health = EeroHealth(status="green", issues=[])

        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",
            status="green",
            health=health,
        )

        assert eero.health is not None
        assert eero.health.status == "green"

    def test_eero_with_health_issues(self):
        """Test eero with health issues."""
        health = EeroHealth(
            status="yellow",
            issues=[{"type": "weak_mesh_connection", "severity": "warning"}],
        )

        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",
            status="yellow",
            health=health,
        )

        assert eero.health.status == "yellow"
        assert len(eero.health.issues) == 1


# ========================== Eero Ethernet Status Tests ==========================


class TestEeroEthernetIntegration:
    """Tests for Eero ethernet status integration."""

    def test_eero_with_ethernet_status(self):
        """Test eero with ethernet status."""
        eth_status = EthernetStatuses(
            statuses=[
                EthernetStatus(
                    interfaceNumber=0, hasCarrier=True, isWanPort=True, speed="1000 Mbps"
                ),
                EthernetStatus(interfaceNumber=1, hasCarrier=False, isWanPort=False),
            ],
            wiredInternet=True,
        )

        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",
            status="green",
            ethernet_status=eth_status,
        )

        assert eero.ethernet_status is not None
        assert len(eero.ethernet_status.statuses) == 2
        assert eero.ethernet_status.wiredInternet is True


# ========================== Eero Location Tests ==========================


class TestEeroLocation:
    """Tests for Eero location handling."""

    def test_eero_location_string(self):
        """Test eero with string location (room name)."""
        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",
            status="green",
            location="Living Room",
        )

        assert eero.location == "Living Room"

    def test_eero_location_object(self):
        """Test eero with Location object."""
        location = Location(city="San Francisco", state="CA")

        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",
            status="green",
            location=location,
        )

        assert isinstance(eero.location, Location)
        assert eero.location.city == "San Francisco"


# ========================== Eero API Client Counts Tests ==========================


class TestEeroClientCounts:
    """Tests for Eero API client count fields."""

    def test_eero_client_counts(self):
        """Test eero with client count fields."""
        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",
            status="green",
            connected_clients_count=20,
            connected_wired_clients_count=5,
            connected_wireless_clients_count=15,
        )

        assert eero.connected_clients_count == 20
        assert eero.connected_wired_clients_count == 5
        assert eero.connected_wireless_clients_count == 15


# ========================== Eero API Response Tests ==========================


class TestEeroAPIResponse:
    """Tests for parsing Eero from API response."""

    def test_parse_from_api_response(self):
        """Test parsing Eero from typical API response."""
        api_response = {
            "url": "/2.2/eeros/26172144",
            "serial": "ABC123456789",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "model": "eero Pro 6E",
            "status": "green",
            "location": "Living Room",
            "led_on": True,
            "gateway": True,
            "connected_clients_count": 15,
            "os_version": "7.1.0",
        }

        eero = Eero.model_validate(api_response)

        assert eero.serial == "ABC123456789"
        assert eero.model == "eero Pro 6E"
        assert eero.status == "green"
        assert eero.led_on is True
        assert eero.gateway is True

    def test_parse_with_extra_fields(self):
        """Test that extra fields are allowed."""
        api_response = {
            "url": "/2.2/eeros/26172144",
            "serial": "ABC123",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "model": "eero Pro",
            "status": "green",
            "unknown_field": "value",
            "another_unknown": 123,
        }

        # Should not raise - extra fields are allowed
        eero = Eero.model_validate(api_response)

        assert eero.serial == "ABC123"


# ========================== Eero Device Type Tests ==========================


class TestEeroDeviceType:
    """Tests for Eero device type."""

    def test_eero_default_device_type(self):
        """Test eero with default device type."""
        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",
            status="green",
        )

        assert eero.device_type == EeroDeviceType.UNKNOWN

    def test_eero_explicit_device_type(self):
        """Test eero with explicit device type."""
        eero = Eero(
            url="/2.2/eeros/26172144",
            serial="ABC123",
            mac_address="AA:BB:CC:DD:EE:FF",
            model="eero Pro 6E",
            status="green",
            device_type=EeroDeviceType.GATEWAY,
        )

        assert eero.device_type == EeroDeviceType.GATEWAY
