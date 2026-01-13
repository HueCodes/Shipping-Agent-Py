"""Tests for Pydantic schema validation."""

import pytest
from pydantic import ValidationError

from src.api.schemas import (
    ChatRequest,
    AddressModel,
    CreateShipmentRequest,
    RateRequest,
    ValidateAddressRequest,
    LineItemModel,
    US_STATES,
    MAX_WEIGHT_OZ,
    MAX_DIMENSION_IN,
)


class TestChatRequestValidation:
    """Tests for ChatRequest validation."""

    def test_valid_message(self):
        """Valid message should pass."""
        req = ChatRequest(message="Hello", session_id="test")
        assert req.message == "Hello"
        assert req.session_id == "test"

    def test_message_whitespace_stripped(self):
        """Whitespace should be stripped from message."""
        req = ChatRequest(message="  Hello world  ")
        assert req.message == "Hello world"

    def test_empty_message_rejected(self):
        """Empty message should be rejected."""
        with pytest.raises(ValidationError) as exc:
            ChatRequest(message="")
        assert "empty" in str(exc.value).lower()

    def test_whitespace_only_message_rejected(self):
        """Whitespace-only message should be rejected."""
        with pytest.raises(ValidationError) as exc:
            ChatRequest(message="   ")
        assert "empty" in str(exc.value).lower()

    def test_message_too_long_rejected(self):
        """Message exceeding max length should be rejected."""
        with pytest.raises(ValidationError) as exc:
            ChatRequest(message="x" * 10001)
        assert "10000" in str(exc.value) or "max" in str(exc.value).lower()

    def test_default_session_id(self):
        """Default session_id should be 'default'."""
        req = ChatRequest(message="Hello")
        assert req.session_id == "default"


class TestAddressModelValidation:
    """Tests for AddressModel validation."""

    def test_valid_address(self):
        """Valid US address should pass."""
        addr = AddressModel(
            street1="123 Main St",
            city="Los Angeles",
            state="CA",
            zip="90001",
        )
        assert addr.state == "CA"
        assert addr.country == "US"

    def test_state_normalized_to_uppercase(self):
        """State code should be normalized to uppercase."""
        addr = AddressModel(
            street1="123 Main St",
            city="Los Angeles",
            state="ca",
            zip="90001",
        )
        assert addr.state == "CA"

    def test_invalid_state_rejected(self):
        """Invalid state code should be rejected."""
        with pytest.raises(ValidationError) as exc:
            AddressModel(
                street1="123 Main St",
                city="Los Angeles",
                state="XX",
                zip="90001",
            )
        assert "Invalid state code" in str(exc.value)

    def test_all_us_states_valid(self):
        """All US states and territories should be valid."""
        for state in US_STATES:
            addr = AddressModel(
                street1="123 Main St",
                city="Test City",
                state=state,
                zip="12345",
            )
            assert addr.state == state

    def test_valid_zip_5_digit(self):
        """5-digit ZIP code should be valid."""
        addr = AddressModel(
            street1="123 Main St",
            city="Los Angeles",
            state="CA",
            zip="90001",
        )
        assert addr.zip == "90001"

    def test_valid_zip_9_digit(self):
        """ZIP+4 format should be valid."""
        addr = AddressModel(
            street1="123 Main St",
            city="Los Angeles",
            state="CA",
            zip="90001-1234",
        )
        assert addr.zip == "90001-1234"

    def test_invalid_zip_rejected(self):
        """Invalid ZIP format should be rejected."""
        invalid_zips = ["1234", "123456", "9001A", "90001-12", "ABCDE"]
        for zip_code in invalid_zips:
            with pytest.raises(ValidationError) as exc:
                AddressModel(
                    street1="123 Main St",
                    city="Los Angeles",
                    state="CA",
                    zip=zip_code,
                )
            assert "ZIP" in str(exc.value) or "zip" in str(exc.value).lower()

    def test_zip_whitespace_stripped(self):
        """Whitespace should be stripped from ZIP."""
        addr = AddressModel(
            street1="123 Main St",
            city="Los Angeles",
            state="CA",
            zip="  90001  ",
        )
        assert addr.zip == "90001"

    def test_street_whitespace_stripped(self):
        """Whitespace should be stripped from street."""
        addr = AddressModel(
            street1="  123 Main St  ",
            city="Los Angeles",
            state="CA",
            zip="90001",
        )
        assert addr.street1 == "123 Main St"

    def test_supported_countries(self):
        """Supported countries should be valid."""
        for country in ["US", "CA", "MX"]:
            addr = AddressModel(
                street1="123 Main St",
                city="Los Angeles",
                state="CA",
                zip="90001",
                country=country,
            )
            assert addr.country == country

    def test_unsupported_country_rejected(self):
        """Unsupported country should be rejected."""
        with pytest.raises(ValidationError) as exc:
            AddressModel(
                street1="123 Main St",
                city="London",
                state="CA",
                zip="90001",
                country="UK",
            )
        assert "Unsupported country" in str(exc.value)


class TestCreateShipmentRequestValidation:
    """Tests for CreateShipmentRequest validation."""

    def test_valid_shipment_request(self):
        """Valid shipment request should pass."""
        req = CreateShipmentRequest(
            rate_id="rate_123",
            to_name="John Doe",
            to_street="123 Main St",
            to_city="Los Angeles",
            to_state="CA",
            to_zip="90001",
            weight_oz=16,
        )
        assert req.weight_oz == 16
        assert req.to_state == "CA"

    def test_weight_must_be_positive(self):
        """Weight must be greater than 0."""
        with pytest.raises(ValidationError) as exc:
            CreateShipmentRequest(
                rate_id="rate_123",
                to_name="John Doe",
                to_street="123 Main St",
                to_city="Los Angeles",
                to_state="CA",
                to_zip="90001",
                weight_oz=0,
            )
        assert "greater than" in str(exc.value).lower()

    def test_weight_max_limit(self):
        """Weight must not exceed max limit."""
        with pytest.raises(ValidationError) as exc:
            CreateShipmentRequest(
                rate_id="rate_123",
                to_name="John Doe",
                to_street="123 Main St",
                to_city="Los Angeles",
                to_state="CA",
                to_zip="90001",
                weight_oz=MAX_WEIGHT_OZ + 1,
            )
        assert "less than or equal" in str(exc.value).lower()

    def test_dimensions_must_be_positive(self):
        """Dimensions must be greater than 0."""
        with pytest.raises(ValidationError) as exc:
            CreateShipmentRequest(
                rate_id="rate_123",
                to_name="John Doe",
                to_street="123 Main St",
                to_city="Los Angeles",
                to_state="CA",
                to_zip="90001",
                weight_oz=16,
                length=0,
            )
        assert "greater than" in str(exc.value).lower()

    def test_dimensions_max_limit(self):
        """Dimensions must not exceed max limit."""
        with pytest.raises(ValidationError) as exc:
            CreateShipmentRequest(
                rate_id="rate_123",
                to_name="John Doe",
                to_street="123 Main St",
                to_city="Los Angeles",
                to_state="CA",
                to_zip="90001",
                weight_oz=16,
                length=MAX_DIMENSION_IN + 1,
            )
        assert "less than or equal" in str(exc.value).lower()

    def test_default_dimensions(self):
        """Default dimensions should be set."""
        req = CreateShipmentRequest(
            rate_id="rate_123",
            to_name="John Doe",
            to_street="123 Main St",
            to_city="Los Angeles",
            to_state="CA",
            to_zip="90001",
            weight_oz=16,
        )
        assert req.length == 6.0
        assert req.width == 4.0
        assert req.height == 2.0

    def test_name_whitespace_stripped(self):
        """Name should have whitespace stripped."""
        req = CreateShipmentRequest(
            rate_id="rate_123",
            to_name="  John Doe  ",
            to_street="123 Main St",
            to_city="Los Angeles",
            to_state="CA",
            to_zip="90001",
            weight_oz=16,
        )
        assert req.to_name == "John Doe"


class TestRateRequestValidation:
    """Tests for RateRequest validation."""

    def test_valid_with_order_id(self):
        """Rate request with order_id should pass."""
        req = RateRequest(order_id="order-123")
        assert req.order_id == "order-123"

    def test_valid_with_address_fields(self):
        """Rate request with address fields should pass."""
        req = RateRequest(
            to_city="Los Angeles",
            to_state="CA",
            to_zip="90001",
            weight_oz=16,
        )
        assert req.to_city == "Los Angeles"
        assert req.to_state == "CA"

    def test_optional_fields_can_be_none(self):
        """Optional fields can be None."""
        req = RateRequest()
        assert req.order_id is None
        assert req.to_city is None
        assert req.to_state is None


class TestLineItemModelValidation:
    """Tests for LineItemModel validation."""

    def test_valid_line_item(self):
        """Valid line item should pass."""
        item = LineItemModel(name="Widget", quantity=2, price=9.99)
        assert item.name == "Widget"
        assert item.quantity == 2
        assert item.price == 9.99

    def test_quantity_must_be_positive(self):
        """Quantity must be at least 1."""
        with pytest.raises(ValidationError) as exc:
            LineItemModel(name="Widget", quantity=0)
        assert "greater than or equal" in str(exc.value).lower()

    def test_quantity_max_limit(self):
        """Quantity must not exceed max."""
        with pytest.raises(ValidationError) as exc:
            LineItemModel(name="Widget", quantity=10001)
        assert "less than or equal" in str(exc.value).lower()

    def test_price_must_be_non_negative(self):
        """Price must be >= 0."""
        with pytest.raises(ValidationError) as exc:
            LineItemModel(name="Widget", quantity=1, price=-1)
        assert "greater than or equal" in str(exc.value).lower()

    def test_price_optional(self):
        """Price is optional."""
        item = LineItemModel(name="Widget", quantity=1)
        assert item.price is None


class TestValidateAddressRequestValidation:
    """Tests for ValidateAddressRequest validation."""

    def test_valid_address_request(self):
        """Valid address validation request should pass."""
        req = ValidateAddressRequest(
            name="John Doe",
            street1="123 Main St",
            city="Los Angeles",
            state="CA",
            zip="90001",
        )
        assert req.name == "John Doe"
        assert req.country == "US"

    def test_name_optional(self):
        """Name is optional."""
        req = ValidateAddressRequest(
            street1="123 Main St",
            city="Los Angeles",
            state="CA",
            zip="90001",
        )
        assert req.name is None

    def test_street2_optional(self):
        """Street2 is optional."""
        req = ValidateAddressRequest(
            street1="123 Main St",
            city="Los Angeles",
            state="CA",
            zip="90001",
        )
        assert req.street2 is None


class TestMaxWeightAndDimensionConstants:
    """Tests for validation constants."""

    def test_max_weight_is_70_pounds(self):
        """Max weight should be 70 lbs = 1120 oz."""
        assert MAX_WEIGHT_OZ == 1120.0

    def test_max_dimension_is_108_inches(self):
        """Max dimension should be 108 inches."""
        assert MAX_DIMENSION_IN == 108.0
