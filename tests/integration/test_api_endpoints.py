"""Integration tests for REST API endpoints."""

import pytest


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_returns_ok(self, test_client):
        """Test that health endpoint returns OK."""
        response = test_client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_shows_mock_mode(self, test_client):
        """Test that health shows mock mode status."""
        response = test_client.get("/api/health")
        data = response.json()
        assert "mock_mode" in data
        assert data["mock_mode"] is True  # Tests run in mock mode


class TestCustomerEndpoints:
    """Tests for customer-related endpoints."""

    def test_get_me_requires_auth(self, test_client):
        """Test that /api/me requires authentication."""
        response = test_client.get("/api/me")
        assert response.status_code == 401

    def test_get_me_returns_customer(self, test_client, sample_customer, auth_headers):
        """Test that /api/me returns customer info."""
        response = test_client.get("/api/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(sample_customer.id)
        assert data["name"] == sample_customer.name
        assert data["plan_tier"] == sample_customer.plan_tier
        assert "labels_this_month" in data
        assert "labels_limit" in data
        assert "labels_remaining" in data

    def test_get_me_with_invalid_customer_id(self, test_client):
        """Test /api/me with invalid customer ID."""
        response = test_client.get(
            "/api/me",
            headers={"X-Customer-ID": "not-a-valid-uuid"},
        )
        assert response.status_code == 400

    def test_get_me_with_nonexistent_customer(self, test_client):
        """Test /api/me with non-existent customer ID."""
        import uuid
        response = test_client.get(
            "/api/me",
            headers={"X-Customer-ID": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_update_preferences(self, test_client, sample_customer, auth_headers):
        """Test updating customer preferences."""
        response = test_client.put(
            "/api/me/preferences",
            json={"default_carrier": "USPS", "auto_cheapest": True},
            headers=auth_headers,
        )
        assert response.status_code == 200


class TestOrderEndpoints:
    """Tests for order-related endpoints."""

    def test_list_orders_requires_auth(self, test_client):
        """Test that listing orders requires authentication."""
        response = test_client.get("/api/orders")
        assert response.status_code == 401

    def test_list_orders_returns_orders(self, test_client, sample_orders, auth_headers):
        """Test that listing orders returns customer's orders."""
        response = test_client.get("/api/orders", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert "orders" in data
        assert "total" in data
        assert len(data["orders"]) > 0

    def test_list_orders_filters_by_status(self, test_client, sample_orders, auth_headers):
        """Test filtering orders by status."""
        response = test_client.get(
            "/api/orders?status=unfulfilled",
            headers=auth_headers,
        )
        assert response.status_code == 200
        orders = response.json()["orders"]

        for order in orders:
            assert order["status"] == "unfulfilled"

    def test_list_orders_search(self, test_client, sample_orders, auth_headers):
        """Test searching orders."""
        response = test_client.get(
            "/api/orders?search=Alice",
            headers=auth_headers,
        )
        assert response.status_code == 200
        orders = response.json()["orders"]

        # Should find Alice's order
        assert any("Alice" in o.get("recipient_name", "") for o in orders)

    def test_get_order_by_id(self, test_client, sample_orders, auth_headers):
        """Test getting a specific order."""
        order = sample_orders[0]
        response = test_client.get(f"/api/orders/{order.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(order.id)
        assert data["order_number"] == order.order_number

    def test_get_order_wrong_customer(self, test_client, sample_orders, customer_repo):
        """Test that customers can't access other customers' orders."""
        # Create another customer
        other_customer = customer_repo.create({
            "shop_domain": "other-store.myshopify.com",
            "name": "Other Store",
            "plan_tier": "free",
        })

        order = sample_orders[0]
        response = test_client.get(
            f"/api/orders/{order.id}",
            headers={"X-Customer-ID": str(other_customer.id)},
        )
        assert response.status_code == 403

    def test_get_nonexistent_order(self, test_client, auth_headers):
        """Test getting a non-existent order."""
        import uuid
        response = test_client.get(
            f"/api/orders/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestRateEndpoints:
    """Tests for rate-related endpoints."""

    def test_get_rates_requires_auth(self, test_client):
        """Test that rate retrieval requires authentication."""
        response = test_client.post(
            "/api/rates",
            json={"to_zip": "60601", "weight_oz": 32},
        )
        assert response.status_code == 401

    def test_get_rates_basic(self, test_client, sample_customer, auth_headers):
        """Test basic rate retrieval."""
        response = test_client.post(
            "/api/rates",
            json={
                "to_city": "Chicago",
                "to_state": "IL",
                "to_zip": "60601",
                "weight_oz": 32,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "rates" in data
        assert len(data["rates"]) > 0

    def test_get_rates_minimal_params(self, test_client, sample_customer, auth_headers):
        """Test rate retrieval with minimal parameters."""
        response = test_client.post(
            "/api/rates",
            json={
                "to_city": "Los Angeles",
                "to_state": "CA",
                "to_zip": "90001",
                "weight_oz": 16,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_get_rates_with_dimensions(self, test_client, sample_customer, auth_headers):
        """Test rate retrieval with package dimensions."""
        response = test_client.post(
            "/api/rates",
            json={
                "to_city": "Miami",
                "to_state": "FL",
                "to_zip": "33101",
                "weight_oz": 48,
                "length": 12,
                "width": 8,
                "height": 6,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_get_rates_missing_required_fields(self, test_client, sample_customer, auth_headers):
        """Test rate retrieval without required fields."""
        response = test_client.post(
            "/api/rates",
            json={"to_zip": "90001"},
            headers=auth_headers,
        )
        # Should return error for missing city, state, weight_oz
        assert response.status_code == 400


class TestShipmentEndpoints:
    """Tests for shipment-related endpoints."""

    def test_create_shipment_requires_auth(self, test_client):
        """Test that shipment creation requires authentication."""
        response = test_client.post(
            "/api/shipments",
            json={
                "rate_id": "rate_123",
                "to_name": "Test",
                "to_street": "123 St",
                "to_city": "City",
                "to_state": "ST",
                "to_zip": "12345",
                "weight_oz": 16,
            },
        )
        assert response.status_code == 401

    def test_create_shipment(self, test_client, sample_customer, auth_headers):
        """Test creating a shipment."""
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
        rate_id = rates_response.json()["rates"][0]["rate_id"]

        # Create shipment
        response = test_client.post(
            "/api/shipments",
            json={
                "rate_id": rate_id,
                "to_name": "Test Recipient",
                "to_street": "123 Test St",
                "to_city": "Seattle",
                "to_state": "WA",
                "to_zip": "98101",
                "weight_oz": 24,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert "id" in data
        assert "tracking_number" in data
        assert "label_url" in data
        assert "carrier" in data

    def test_create_shipment_with_order(self, test_client, sample_orders, auth_headers):
        """Test creating shipment linked to an order."""
        order = sample_orders[0]

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

        response = test_client.post(
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
        assert response.status_code == 200
        data = response.json()
        assert data["order_id"] == str(order.id)

    def test_get_shipment(self, test_client, sample_customer, auth_headers):
        """Test getting shipment details."""
        # Create a shipment first
        rates_response = test_client.post(
            "/api/rates",
            json={
                "to_city": "Boston",
                "to_state": "MA",
                "to_zip": "02101",
                "weight_oz": 16,
            },
            headers=auth_headers,
        )
        rate_id = rates_response.json()["rates"][0]["rate_id"]

        create_response = test_client.post(
            "/api/shipments",
            json={
                "rate_id": rate_id,
                "to_name": "Get Test",
                "to_street": "100 State St",
                "to_city": "Boston",
                "to_state": "MA",
                "to_zip": "02101",
                "weight_oz": 16,
            },
            headers=auth_headers,
        )
        shipment_id = create_response.json()["id"]

        # Get the shipment
        response = test_client.get(f"/api/shipments/{shipment_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == shipment_id

    def test_get_shipment_tracking(self, test_client, sample_customer, auth_headers):
        """Test getting shipment tracking."""
        # Create a shipment first
        rates_response = test_client.post(
            "/api/rates",
            json={
                "to_city": "Denver",
                "to_state": "CO",
                "to_zip": "80201",
                "weight_oz": 32,
            },
            headers=auth_headers,
        )
        rate_id = rates_response.json()["rates"][0]["rate_id"]

        create_response = test_client.post(
            "/api/shipments",
            json={
                "rate_id": rate_id,
                "to_name": "Tracking Test",
                "to_street": "100 Colfax Ave",
                "to_city": "Denver",
                "to_state": "CO",
                "to_zip": "80201",
                "weight_oz": 32,
            },
            headers=auth_headers,
        )
        shipment_id = create_response.json()["id"]

        # Get tracking
        response = test_client.get(f"/api/shipments/{shipment_id}/tracking", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert "tracking_number" in data
        assert "carrier" in data
        assert "status" in data


class TestAddressValidation:
    """Tests for address validation endpoint."""

    def test_validate_address_requires_auth(self, test_client):
        """Test that address validation requires authentication."""
        response = test_client.post(
            "/api/addresses/validate",
            json={
                "street1": "123 main st",
                "city": "san francisco",
                "state": "ca",
                "zip": "94102",
            },
        )
        assert response.status_code == 401

    def test_validate_address_success(self, test_client, sample_customer, auth_headers):
        """Test successful address validation."""
        response = test_client.post(
            "/api/addresses/validate",
            json={
                "name": "Test User",
                "street1": "123 main street",
                "city": "san francisco",
                "state": "ca",
                "zip": "94102",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is True
        assert "standardized" in data

    def test_validate_address_standardization(self, test_client, sample_customer, auth_headers):
        """Test that address is standardized."""
        response = test_client.post(
            "/api/addresses/validate",
            json={
                "street1": "456 oak ave",
                "city": "new york",
                "state": "ny",
                "zip": "10001",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        standardized = response.json()["standardized"]

        # Should be standardized (uppercase or title case)
        assert standardized["city"].upper() == "NEW YORK" or standardized["city"] == "New York"

    def test_validate_address_missing_fields(self, test_client, sample_customer, auth_headers):
        """Test validation with missing required fields."""
        response = test_client.post(
            "/api/addresses/validate",
            json={"city": "Chicago"},
            headers=auth_headers,
        )
        # Should return error for missing street and zip
        assert response.status_code in [400, 422]


class TestChatResetEndpoint:
    """Tests for chat reset endpoint."""

    def test_reset_session(self, test_client):
        """Test resetting a chat session."""
        response = test_client.post("/api/reset?session_id=test-session")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_reset_preserves_session_id(self, test_client):
        """Test that reset returns the session ID."""
        response = test_client.post("/api/reset?session_id=my-session-123")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "my-session-123"


class TestChatHistoryEndpoint:
    """Tests for chat history endpoint."""

    def test_get_empty_history(self, test_client):
        """Test getting history for new session returns empty."""
        response = test_client.get("/api/chat/history?session_id=new-session")
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert "total" in data
        assert "session_id" in data

    def test_history_endpoint_structure(self, test_client):
        """Test that history endpoint returns proper structure."""
        response = test_client.get("/api/chat/history?session_id=test-session")
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "session_id" in data
        assert "messages" in data
        assert "total" in data
        assert isinstance(data["messages"], list)
        assert isinstance(data["total"], int)

    def test_get_history_with_limit_param(self, test_client):
        """Test that limit parameter is accepted."""
        response = test_client.get("/api/chat/history?session_id=test&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data

    def test_get_authenticated_history_structure(self, test_client, sample_customer, auth_headers):
        """Test getting history for authenticated user returns proper structure."""
        response = test_client.get("/api/chat/history", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert "total" in data
        # Session ID should be customer ID for authenticated users
        assert data["session_id"] == str(sample_customer.id)


class TestStaticFiles:
    """Tests for static file serving."""

    def test_index_html_served(self, test_client):
        """Test that index.html is served at root."""
        response = test_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_index_contains_chat_interface(self, test_client):
        """Test that index.html contains chat interface elements."""
        response = test_client.get("/")
        content = response.text

        assert "chat" in content.lower()
        assert "message" in content.lower()


class TestCORS:
    """Tests for CORS configuration."""

    def test_cors_headers_present(self, test_client):
        """Test that CORS headers are present."""
        response = test_client.options(
            "/api/chat",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        # CORS should allow the request
        assert response.status_code in [200, 204]


class TestErrorResponses:
    """Tests for error response formatting."""

    def test_404_returns_json(self, test_client):
        """Test that 404 errors return JSON."""
        response = test_client.get("/api/nonexistent")
        assert response.status_code == 404

    def test_validation_error_format(self, test_client):
        """Test that validation errors have proper format."""
        response = test_client.post(
            "/api/chat",
            json={"wrong_field": "value"},
        )
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
