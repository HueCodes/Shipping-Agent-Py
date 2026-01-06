"""Tests for the mock EasyPost client."""

import pytest

from src.mock import MockEasyPostClient, _generate_tracking
from src.easypost_client import Address, Parcel


@pytest.fixture
def mock_client():
    """Create a mock EasyPost client."""
    return MockEasyPostClient()


@pytest.fixture
def sample_address():
    """Create a sample destination address."""
    return Address(
        name="John Doe",
        street1="123 Main St",
        city="Los Angeles",
        state="CA",
        zip_code="90001",
    )


@pytest.fixture
def sample_parcel():
    """Create a sample parcel."""
    return Parcel(length=6, width=4, height=2, weight=32)  # 2 lbs in oz


class TestGetRates:
    """Tests for MockEasyPostClient.get_rates."""

    def test_returns_rates_sorted_by_price(self, mock_client, sample_address, sample_parcel):
        rates = mock_client.get_rates(sample_address, sample_parcel)
        assert len(rates) > 0
        prices = [r.rate for r in rates]
        assert prices == sorted(prices)

    def test_heavier_package_costs_more(self, mock_client, sample_address):
        light_parcel = Parcel(length=6, width=4, height=2, weight=16)  # 1 lb
        heavy_parcel = Parcel(length=6, width=4, height=2, weight=160)  # 10 lbs

        light_rates = mock_client.get_rates(sample_address, light_parcel)
        heavy_rates = mock_client.get_rates(sample_address, heavy_parcel)

        # Compare cheapest options
        light_cheapest = min(r.rate for r in light_rates)
        heavy_cheapest = min(r.rate for r in heavy_rates)

        assert heavy_cheapest > light_cheapest

    def test_west_coast_more_expensive(self, mock_client, sample_parcel):
        # West coast address
        west_coast = Address(
            name="Jane Doe",
            street1="456 Oak St",
            city="Los Angeles",
            state="CA",
            zip_code="90001",
        )

        # East coast address (should be cheaper - NY is from address location)
        east_coast = Address(
            name="Jane Doe",
            street1="456 Oak St",
            city="Boston",
            state="MA",
            zip_code="02101",
        )

        west_rates = mock_client.get_rates(west_coast, sample_parcel)
        east_rates = mock_client.get_rates(east_coast, sample_parcel)

        west_cheapest = min(r.rate for r in west_rates)
        east_cheapest = min(r.rate for r in east_rates)

        # West coast should cost more (distance_factor 1.5 vs 1.0)
        assert west_cheapest > east_cheapest

    def test_midwest_cost_between_coasts(self, mock_client, sample_parcel):
        west = Address(name="Test", street1="123 St", city="LA", state="CA", zip_code="90001")
        midwest = Address(name="Test", street1="123 St", city="Chicago", state="IL", zip_code="60601")
        east = Address(name="Test", street1="123 St", city="NYC", state="NY", zip_code="10001")

        west_cheapest = min(r.rate for r in mock_client.get_rates(west, sample_parcel))
        midwest_cheapest = min(r.rate for r in mock_client.get_rates(midwest, sample_parcel))
        east_cheapest = min(r.rate for r in mock_client.get_rates(east, sample_parcel))

        # Midwest (1.25 factor) should be between east (1.0) and west (1.5)
        assert east_cheapest < midwest_cheapest < west_cheapest

    def test_rates_have_required_fields(self, mock_client, sample_address, sample_parcel):
        rates = mock_client.get_rates(sample_address, sample_parcel)
        for rate in rates:
            assert rate.carrier in ["USPS", "UPS", "FedEx"]
            assert rate.service is not None and len(rate.service) > 0
            assert rate.rate > 0
            assert rate.rate_id is not None
            assert rate.rate_id.startswith("rate_")

    def test_multiple_carriers_included(self, mock_client, sample_address, sample_parcel):
        rates = mock_client.get_rates(sample_address, sample_parcel)
        carriers = {r.carrier for r in rates}
        assert "USPS" in carriers
        assert "UPS" in carriers
        assert "FedEx" in carriers


class TestValidateAddress:
    """Tests for MockEasyPostClient.validate_address."""

    def test_returns_valid_tuple(self, mock_client, sample_address):
        is_valid, corrected, message = mock_client.validate_address(sample_address)
        assert is_valid is True
        assert corrected is not None
        assert isinstance(message, str)

    def test_standardizes_to_uppercase(self, mock_client):
        address = Address(
            name="john doe",
            street1="123 main street",
            city="los angeles",
            state="ca",
            zip_code="90001",
        )
        is_valid, corrected, _ = mock_client.validate_address(address)
        assert is_valid
        assert corrected.name == "JOHN DOE"
        assert corrected.street1 == "123 MAIN STREET"
        assert corrected.city == "LOS ANGELES"
        assert corrected.state == "CA"

    def test_normalizes_zip_to_five_digits(self, mock_client):
        address = Address(
            name="Test",
            street1="123 Main St",
            city="LA",
            state="CA",
            zip_code="90001-1234",
        )
        _, corrected, _ = mock_client.validate_address(address)
        assert corrected.zip_code == "90001"

    def test_handles_empty_optional_fields(self, mock_client):
        address = Address(
            name="",
            street1="123 Main St",
            city="LA",
            state="CA",
            zip_code="90001",
        )
        is_valid, corrected, _ = mock_client.validate_address(address)
        assert is_valid
        assert corrected.street2 == ""


class TestCreateShipment:
    """Tests for MockEasyPostClient.create_shipment."""

    def test_returns_shipment_with_tracking(self, mock_client, sample_address, sample_parcel):
        shipment = mock_client.create_shipment(
            to_address=sample_address,
            parcel=sample_parcel,
            rate_id="rate_12345",
        )
        assert shipment.tracking_number is not None
        assert len(shipment.tracking_number) > 0

    def test_returns_shipment_with_label_url(self, mock_client, sample_address, sample_parcel):
        shipment = mock_client.create_shipment(
            to_address=sample_address,
            parcel=sample_parcel,
            rate_id="rate_12345",
        )
        assert shipment.label_url is not None
        assert shipment.label_url.startswith("http")

    def test_shipment_has_required_fields(self, mock_client, sample_address, sample_parcel):
        shipment = mock_client.create_shipment(
            to_address=sample_address,
            parcel=sample_parcel,
            rate_id="rate_12345",
        )
        assert shipment.id.startswith("shp_")
        assert shipment.carrier in ["USPS", "UPS", "FedEx"]
        assert shipment.service is not None
        assert shipment.rate > 0


class TestTrackingNumberFormats:
    """Tests for tracking number generation."""

    def test_tracking_number_formats(self):
        # Generate multiple tracking numbers and check formats
        tracking_numbers = [_generate_tracking() for _ in range(50)]

        for tn in tracking_numbers:
            # Should start with known carrier prefixes
            assert tn[:2] in ["1Z", "94", "78"], f"Unknown prefix: {tn[:2]}"

    def test_ups_tracking_format(self):
        # UPS tracking numbers start with 1Z
        tracking_numbers = [_generate_tracking() for _ in range(100)]
        ups_numbers = [tn for tn in tracking_numbers if tn.startswith("1Z")]

        # Should have some UPS numbers
        assert len(ups_numbers) > 0

        for tn in ups_numbers:
            # 1Z + 9 digits
            assert len(tn) == 11
            assert tn[2:].isdigit()

    def test_usps_tracking_format(self):
        # USPS numbers start with 94
        tracking_numbers = [_generate_tracking() for _ in range(100)]
        usps_numbers = [tn for tn in tracking_numbers if tn.startswith("94")]

        assert len(usps_numbers) > 0

        for tn in usps_numbers:
            # 94 + 9 digits
            assert len(tn) == 11
            assert tn[2:].isdigit()


class TestGetTracking:
    """Tests for MockEasyPostClient.get_tracking."""

    def test_returns_tracking_info(self, mock_client):
        info = mock_client.get_tracking("1Z123456789", "UPS")
        assert "status" in info
        assert "estimated_delivery" in info
        assert "events" in info

    def test_tracking_has_events(self, mock_client):
        info = mock_client.get_tracking("94123456789", "USPS")
        assert len(info["events"]) > 0
        for event in info["events"]:
            assert "status" in event
            assert "message" in event
            assert "datetime" in event
