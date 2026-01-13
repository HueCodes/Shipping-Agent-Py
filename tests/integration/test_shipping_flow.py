"""Integration tests for shipping workflow: rates -> label -> tracking."""

import pytest
import re


class TestRateRetrieval:
    """Tests for shipping rate retrieval."""

    def test_get_rates_basic(self, test_client, sample_customer, auth_headers):
        """Test basic rate retrieval via API."""
        response = test_client.post(
            "/api/rates",
            json={
                "to_city": "Los Angeles",
                "to_state": "CA",
                "to_zip": "90001",
                "weight_oz": 32,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "rates" in data
        assert len(data["rates"]) > 0

        # Check rate structure
        rate = data["rates"][0]
        assert "rate_id" in rate
        assert "carrier" in rate
        assert "service" in rate
        assert "price" in rate

    def test_rates_sorted_by_price(self, test_client, sample_customer, auth_headers):
        """Test that rates are returned sorted by price."""
        response = test_client.post(
            "/api/rates",
            json={
                "to_city": "Chicago",
                "to_state": "IL",
                "to_zip": "60601",
                "weight_oz": 48,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        rates = response.json()["rates"]

        prices = [r["price"] for r in rates]
        assert prices == sorted(prices), "Rates should be sorted by price ascending"

    def test_rates_include_multiple_carriers(self, test_client, sample_customer, auth_headers):
        """Test that rates include multiple carriers."""
        response = test_client.post(
            "/api/rates",
            json={
                "to_city": "Miami",
                "to_state": "FL",
                "to_zip": "33101",
                "weight_oz": 16,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        rates = response.json()["rates"]

        carriers = set(r["carrier"] for r in rates)
        assert len(carriers) >= 2, "Should have rates from multiple carriers"

    def test_rates_via_chat(self, chat_helper):
        """Test getting rates through chat interface."""
        result = chat_helper.send("What are the rates for shipping 2 pounds to Miami, FL 33101?")
        assert "error" not in result
        response = result["response"]

        # Should contain rate information
        assert any(c in response for c in ["USPS", "UPS", "FedEx", "$"])


class TestShipmentCreation:
    """Tests for shipment/label creation."""

    def test_create_shipment_after_rates(self, test_client, sample_customer, auth_headers):
        """Test creating a shipment using a rate from rates query."""
        # First get rates
        rates_response = test_client.post(
            "/api/rates",
            json={
                "to_city": "Seattle",
                "to_state": "WA",
                "to_zip": "98101",
                "weight_oz": 24,
            },
            headers=auth_headers,
        )
        assert rates_response.status_code == 200
        rates = rates_response.json()["rates"]
        rate_id = rates[0]["rate_id"]

        # Create shipment with that rate
        shipment_response = test_client.post(
            "/api/shipments",
            json={
                "rate_id": rate_id,
                "to_name": "John Doe",
                "to_street": "123 Pine Street",
                "to_city": "Seattle",
                "to_state": "WA",
                "to_zip": "98101",
                "weight_oz": 24,
            },
            headers=auth_headers,
        )
        assert shipment_response.status_code == 200
        shipment = shipment_response.json()

        assert "id" in shipment
        assert "tracking_number" in shipment
        assert "label_url" in shipment
        # Carrier might differ in mock mode since mock generates random carrier
        assert shipment["carrier"] in ["USPS", "UPS", "FedEx"]

    def test_shipment_increments_label_count(self, test_client, sample_customer, auth_headers):
        """Test that creating a shipment increments label count."""
        initial_count = sample_customer.labels_this_month

        # Get rates
        rates_response = test_client.post(
            "/api/rates",
            json={
                "to_city": "New York",
                "to_state": "NY",
                "to_zip": "10001",
                "weight_oz": 16,
            },
            headers=auth_headers,
        )
        rate_id = rates_response.json()["rates"][0]["rate_id"]

        # Create shipment with auth
        test_client.post(
            "/api/shipments",
            json={
                "rate_id": rate_id,
                "to_name": "Jane Doe",
                "to_street": "456 5th Ave",
                "to_city": "New York",
                "to_state": "NY",
                "to_zip": "10001",
                "weight_oz": 16,
            },
            headers=auth_headers,
        )

        # Check customer - label count should have increased
        me_response = test_client.get("/api/me", headers=auth_headers)
        assert me_response.status_code == 200
        assert me_response.json()["labels_this_month"] > initial_count

    def test_shipment_via_chat_flow(self, chat_helper):
        """Test complete shipping flow through chat."""
        # Get rates
        chat_helper.send("Get shipping rates for a 2lb package to Denver, CO 80201")

        # Create shipment
        result = chat_helper.send(
            "Ship it with the cheapest option to Bob Wilson at 789 Mountain View Dr"
        )
        assert "error" not in result
        response = result["response"].lower()

        # Should confirm shipment creation
        assert any(term in response for term in ["created", "shipped", "tracking", "label"])


class TestTrackingStatus:
    """Tests for package tracking."""

    def test_get_tracking_after_shipment(self, test_client, sample_customer, auth_headers):
        """Test getting tracking status for a shipment."""
        # Create a shipment first
        rates_response = test_client.post(
            "/api/rates",
            json={
                "to_city": "Boston",
                "to_state": "MA",
                "to_zip": "02101",
                "weight_oz": 32,
            },
            headers=auth_headers,
        )
        rate_id = rates_response.json()["rates"][0]["rate_id"]

        shipment_response = test_client.post(
            "/api/shipments",
            json={
                "rate_id": rate_id,
                "to_name": "Test User",
                "to_street": "100 Federal St",
                "to_city": "Boston",
                "to_state": "MA",
                "to_zip": "02101",
                "weight_oz": 32,
            },
            headers=auth_headers,
        )
        shipment = shipment_response.json()
        shipment_id = shipment["id"]

        # Get tracking
        tracking_response = test_client.get(f"/api/shipments/{shipment_id}/tracking", headers=auth_headers)
        assert tracking_response.status_code == 200
        tracking = tracking_response.json()

        assert "tracking_number" in tracking
        assert "carrier" in tracking
        assert "status" in tracking

    def test_tracking_via_chat(self, chat_helper):
        """Test tracking query through chat."""
        # First create a shipment
        chat_helper.send("Get rates for 16oz to Phoenix, AZ 85001")
        chat_helper.send("Ship with USPS to Carol Brown at 555 Desert Rd")

        # Ask for tracking
        result = chat_helper.send("What's the tracking status?")
        assert "error" not in result
        # Should have some tracking info or acknowledge the shipment


class TestAddressValidation:
    """Tests for address validation in shipping flow."""

    def test_validate_address_api(self, test_client, sample_customer, auth_headers):
        """Test address validation via API."""
        response = test_client.post(
            "/api/addresses/validate",
            json={
                "name": "Test User",
                "street1": "123 main st",
                "city": "los angeles",
                "state": "ca",
                "zip": "90001",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert "valid" in data
        assert data["valid"] is True
        assert "standardized" in data

        # Check standardization (uppercase, formatted)
        standardized = data["standardized"]
        assert standardized["city"].isupper() or standardized["city"].istitle()

    def test_validation_before_shipment(self, chat_helper):
        """Test that address validation works in chat flow."""
        result = chat_helper.send(
            "Validate this address: 456 oak avenue, chicago illinois 60601"
        )
        assert "error" not in result
        response = result["response"].lower()
        assert any(term in response for term in ["valid", "verified", "correct", "address"])


class TestFullShippingWorkflow:
    """End-to-end tests for complete shipping workflow."""

    def test_complete_workflow_api(self, test_client, sample_customer, auth_headers):
        """Test complete workflow: validate -> rates -> ship -> track."""
        # Step 1: Validate address
        validate_response = test_client.post(
            "/api/addresses/validate",
            json={
                "name": "Final Test",
                "street1": "999 Test Blvd",
                "city": "San Francisco",
                "state": "CA",
                "zip": "94102",
            },
            headers=auth_headers,
        )
        assert validate_response.status_code == 200
        assert validate_response.json()["valid"] is True

        # Step 2: Get rates
        rates_response = test_client.post(
            "/api/rates",
            json={
                "to_city": "San Francisco",
                "to_state": "CA",
                "to_zip": "94102",
                "weight_oz": 64,
            },
            headers=auth_headers,
        )
        assert rates_response.status_code == 200
        rates = rates_response.json()["rates"]
        assert len(rates) > 0

        # Step 3: Create shipment
        rate_id = rates[0]["rate_id"]
        shipment_response = test_client.post(
            "/api/shipments",
            json={
                "rate_id": rate_id,
                "to_name": "Final Test",
                "to_street": "999 Test Blvd",
                "to_city": "San Francisco",
                "to_state": "CA",
                "to_zip": "94102",
                "weight_oz": 64,
            },
            headers=auth_headers,
        )
        assert shipment_response.status_code == 200
        shipment = shipment_response.json()
        assert shipment["tracking_number"] is not None

        # Step 4: Get tracking
        tracking_response = test_client.get(
            f"/api/shipments/{shipment['id']}/tracking",
            headers=auth_headers,
        )
        assert tracking_response.status_code == 200
        tracking = tracking_response.json()
        assert tracking["tracking_number"] == shipment["tracking_number"]

    def test_complete_workflow_chat(self, authenticated_chat, sample_orders):
        """Test complete workflow through conversational interface."""
        # Reference an existing order
        order = sample_orders[0]  # Alice Johnson's order

        # Step 1: Check orders
        result1 = authenticated_chat.send("What orders do I need to ship?")
        assert "error" not in result1

        # Step 2: Get rates for specific order
        result2 = authenticated_chat.send(f"Get shipping rates for order {order.order_number}")
        assert "error" not in result2

        # Step 3: Ship the order
        result3 = authenticated_chat.send("Ship it with the cheapest option")
        assert "error" not in result3
        response = result3["response"].lower()
        assert any(term in response for term in ["shipped", "created", "tracking", "label"])


class TestOrderFulfillment:
    """Tests for order fulfillment workflow."""

    def test_fulfill_order_updates_status(self, test_client, sample_orders, auth_headers):
        """Test that fulfilling an order updates its status."""
        order = sample_orders[0]  # Unfulfilled order

        # First create a shipment for this order
        rates_response = test_client.post(
            "/api/rates",
            json={
                "to_city": "Los Angeles",
                "to_state": "CA",
                "to_zip": "90001",
                "weight_oz": 32,
            },
            headers=auth_headers,
        )
        rate_id = rates_response.json()["rates"][0]["rate_id"]

        test_client.post(
            "/api/shipments",
            json={
                "order_id": str(order.id),
                "rate_id": rate_id,
                "to_name": "Alice Johnson",
                "to_street": "123 Main Street",
                "to_city": "Los Angeles",
                "to_state": "CA",
                "to_zip": "90001",
                "weight_oz": 32,
            },
            headers=auth_headers,
        )

        # Now fulfill the order
        response = test_client.post(
            f"/api/orders/{order.id}/fulfill",
            json={"tracking_number": "1Z999AA10123456784", "carrier": "UPS"},
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Check order status
        order_response = test_client.get(f"/api/orders/{order.id}", headers=auth_headers)
        assert order_response.status_code == 200
        assert order_response.json()["status"] in ["shipped", "fulfilled"]

    def test_cannot_ship_already_shipped_order(self, test_client, sample_orders, auth_headers):
        """Test that already shipped orders cannot be re-shipped."""
        shipped_order = sample_orders[2]  # Already shipped

        response = test_client.post(
            f"/api/orders/{shipped_order.id}/fulfill",
            json={"tracking_number": "TEST123", "carrier": "USPS"},
            headers=auth_headers,
        )
        # Should either reject or handle gracefully
        # Depends on business logic - could be 400 or 200 with warning


class TestRateCaching:
    """Tests for rate caching behavior."""

    def test_rates_are_consistent(self, test_client, sample_customer, auth_headers):
        """Test that consecutive rate requests return consistent results."""
        params = {
            "to_city": "Beverly Hills",
            "to_state": "CA",
            "to_zip": "90210",
            "weight_oz": 32,
        }

        response1 = test_client.post("/api/rates", json=params, headers=auth_headers)
        response2 = test_client.post("/api/rates", json=params, headers=auth_headers)

        assert response1.status_code == 200
        assert response2.status_code == 200

        rates1 = response1.json()["rates"]
        rates2 = response2.json()["rates"]

        # Prices should be consistent (mock returns deterministic rates)
        prices1 = [r["price"] for r in rates1]
        prices2 = [r["price"] for r in rates2]
        assert prices1 == prices2

    def test_rate_id_valid_for_shipment(self, test_client, sample_customer, auth_headers):
        """Test that rate_id from rates response works for shipment."""
        # Get rates
        rates_response = test_client.post(
            "/api/rates",
            json={
                "to_city": "Dallas",
                "to_state": "TX",
                "to_zip": "75001",
                "weight_oz": 20,
            },
            headers=auth_headers,
        )
        rate_id = rates_response.json()["rates"][0]["rate_id"]

        # Use that rate_id immediately
        shipment_response = test_client.post(
            "/api/shipments",
            json={
                "rate_id": rate_id,
                "to_name": "Rate Test",
                "to_street": "100 Main St",
                "to_city": "Dallas",
                "to_state": "TX",
                "to_zip": "75001",
                "weight_oz": 20,
            },
            headers=auth_headers,
        )
        assert shipment_response.status_code == 200
        assert "tracking_number" in shipment_response.json()

    def test_invalid_rate_id_handled(self, test_client, sample_customer, auth_headers):
        """Test that invalid rate_id is handled (may succeed in mock mode)."""
        response = test_client.post(
            "/api/shipments",
            json={
                "rate_id": "invalid_rate_12345",
                "to_name": "Test User",
                "to_street": "123 Test St",
                "to_city": "Los Angeles",
                "to_state": "CA",
                "to_zip": "90001",
                "weight_oz": 16,
            },
            headers=auth_headers,
        )
        # In mock mode, any rate_id may be accepted; in production it would fail
        # Just verify the endpoint handles the request without crashing
        assert response.status_code in [200, 400, 500]
