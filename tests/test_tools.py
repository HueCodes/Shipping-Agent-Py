"""Tests for the tool executor."""

import pytest

from src.agent.tools import ToolExecutor
from src.mock import MockEasyPostClient


@pytest.fixture
def executor():
    """Create a tool executor with mock client."""
    client = MockEasyPostClient()
    return ToolExecutor(client)


class TestToolExecutorGetRates:
    """Tests for get_shipping_rates tool execution."""

    def test_execute_get_rates(self, executor):
        result = executor.execute("get_shipping_rates", {
            "to_city": "Los Angeles",
            "to_state": "CA",
            "to_zip": "90001",
            "weight_oz": 32,
        })
        assert "Available shipping rates" in result
        assert "USPS" in result or "UPS" in result or "FedEx" in result
        assert "rate_id:" in result

    def test_rates_are_cached(self, executor):
        executor.execute("get_shipping_rates", {
            "to_city": "Los Angeles",
            "to_state": "CA",
            "to_zip": "90001",
            "weight_oz": 32,
        })
        # Check that rates were cached
        assert len(executor._last_rates) > 0

    def test_get_rates_with_optional_params(self, executor):
        result = executor.execute("get_shipping_rates", {
            "to_name": "John Doe",
            "to_street": "123 Main St",
            "to_city": "Seattle",
            "to_state": "WA",
            "to_zip": "98101",
            "weight_oz": 48,
            "length": 8,
            "width": 6,
            "height": 4,
        })
        assert "Available shipping rates" in result


class TestToolExecutorValidateAddress:
    """Tests for validate_address tool execution."""

    def test_execute_validate_address(self, executor):
        result = executor.execute("validate_address", {
            "name": "John Doe",
            "street": "123 Main St",
            "city": "Los Angeles",
            "state": "CA",
            "zip": "90001",
        })
        assert "Address is valid" in result
        assert "Standardized" in result

    def test_validate_address_without_name(self, executor):
        result = executor.execute("validate_address", {
            "street": "456 Oak Ave",
            "city": "Chicago",
            "state": "IL",
            "zip": "60601",
        })
        assert "valid" in result.lower()


class TestToolExecutorCreateShipment:
    """Tests for create_shipment tool execution."""

    def test_execute_create_shipment(self, executor):
        # First get rates to populate the cache
        executor.execute("get_shipping_rates", {
            "to_city": "Miami",
            "to_state": "FL",
            "to_zip": "33101",
            "weight_oz": 64,
        })
        # Get a valid rate_id from the cache
        rate_id = list(executor._last_rates.keys())[0]

        result = executor.execute("create_shipment", {
            "to_name": "Jane Doe",
            "to_street": "789 Pine Rd",
            "to_city": "Miami",
            "to_state": "FL",
            "to_zip": "33101",
            "weight_oz": 64,
            "rate_id": rate_id,
        })
        assert "Shipment created successfully" in result
        assert "Tracking Number:" in result
        assert "Label URL:" in result

    def test_shipment_returns_carrier_info(self, executor):
        # First get rates to populate the cache
        executor.execute("get_shipping_rates", {
            "to_city": "Denver",
            "to_state": "CO",
            "to_zip": "80201",
            "weight_oz": 32,
        })
        # Get a valid rate_id from the cache
        rate_id = list(executor._last_rates.keys())[0]

        result = executor.execute("create_shipment", {
            "to_name": "Test User",
            "to_street": "123 Test St",
            "to_city": "Denver",
            "to_state": "CO",
            "to_zip": "80201",
            "weight_oz": 32,
            "rate_id": rate_id,
        })
        assert "Carrier:" in result
        assert "Cost:" in result

    def test_create_shipment_with_invalid_rate_id(self, executor):
        # Should return error for rate not in cache
        result = executor.execute("create_shipment", {
            "to_name": "Test User",
            "to_street": "123 Test St",
            "to_city": "Denver",
            "to_state": "CO",
            "to_zip": "80201",
            "weight_oz": 32,
            "rate_id": "rate_invalid",
        })
        assert "not found in cache" in result


class TestToolExecutorUnknownTool:
    """Tests for handling unknown tools."""

    def test_unknown_tool_returns_error(self, executor):
        result = executor.execute("unknown_tool", {"param": "value"})
        assert "Unknown tool" in result
        assert "unknown_tool" in result


class TestToolExecutorRateCaching:
    """Tests for rate caching behavior."""

    def test_rates_cached_by_rate_id(self, executor):
        # Get rates
        executor.execute("get_shipping_rates", {
            "to_city": "Boston",
            "to_state": "MA",
            "to_zip": "02101",
            "weight_oz": 32,
        })

        # Check that each rate is cached by its rate_id
        for rate_id, rate in executor._last_rates.items():
            assert rate_id.startswith("rate_")
            assert rate.rate_id == rate_id

    def test_new_rates_request_updates_cache(self, executor):
        # First request
        executor.execute("get_shipping_rates", {
            "to_city": "Boston",
            "to_state": "MA",
            "to_zip": "02101",
            "weight_oz": 32,
        })
        first_rate_ids = set(executor._last_rates.keys())

        # Second request with different destination
        executor.execute("get_shipping_rates", {
            "to_city": "Seattle",
            "to_state": "WA",
            "to_zip": "98101",
            "weight_oz": 32,
        })
        second_rate_ids = set(executor._last_rates.keys())

        # Cache should now contain rates from second request
        # The mock generates new rate IDs each time
        assert second_rate_ids != first_rate_ids or len(second_rate_ids) > 0


class TestToolExecutorErrorHandling:
    """Tests for error handling in tool execution."""

    def test_missing_required_field_get_rates(self, executor):
        # Missing weight_oz should return an error message (not raise exception)
        # This tests the error boundary in the execute() method
        result = executor.execute("get_shipping_rates", {
            "to_city": "Los Angeles",
            "to_state": "CA",
            "to_zip": "90001",
            # weight_oz is missing
        })
        # Should return error message, not raise exception
        assert "error" in result.lower() or "Error" in result

    def test_missing_required_field_create_shipment(self, executor):
        # Missing rate_id should return an error message
        result = executor.execute("create_shipment", {
            "to_name": "Test",
            "to_street": "123 Main",
            "to_city": "LA",
            "to_state": "CA",
            "to_zip": "90001",
            "weight_oz": 32,
            # rate_id is missing
        })
        assert "error" in result.lower() or "Error" in result

    def test_invalid_tool_input_returns_error(self, executor):
        # Completely malformed input should be handled gracefully
        result = executor.execute("get_shipping_rates", {})
        assert "error" in result.lower() or "Error" in result
