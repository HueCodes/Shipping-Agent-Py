"""Tests for Shopify order sync functionality."""

import json
import hmac
import hashlib
import base64
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.server import app


# Sample Shopify order webhook payload
SAMPLE_ORDER_PAYLOAD = {
    "id": 5678901234,
    "order_number": "1001",
    "name": "#1001",
    "email": "customer@example.com",
    "fulfillment_status": None,
    "financial_status": "paid",
    "created_at": "2026-01-12T10:00:00Z",
    "updated_at": "2026-01-12T10:00:00Z",
    "cancelled_at": None,
    "shipping_address": {
        "name": "John Smith",
        "address1": "123 Main St",
        "address2": "Apt 4B",
        "city": "New York",
        "province_code": "NY",
        "zip": "10001",
        "country_code": "US",
        "phone": "555-1234",
    },
    "line_items": [
        {
            "id": 11111,
            "title": "Test Product",
            "quantity": 2,
            "price": "19.99",
            "sku": "TEST-001",
            "grams": 500,
            "variant_title": "Large",
        },
        {
            "id": 22222,
            "title": "Another Product",
            "quantity": 1,
            "price": "29.99",
            "sku": "TEST-002",
            "grams": 250,
            "variant_title": None,
        },
    ],
}


def generate_webhook_hmac(payload: dict, secret: str) -> str:
    """Generate HMAC signature for webhook payload."""
    body = json.dumps(payload).encode()
    computed = base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()
    return computed


class TestShopifyOrderWebhook:
    """Tests for Shopify order webhook handler."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        with patch("src.api.deps.get_db") as mock_get_db:
            mock_session = MagicMock()
            mock_get_db.return_value = iter([mock_session])
            yield mock_session

    def test_webhook_requires_hmac_signature(self, client):
        """Webhook should reject requests without valid HMAC."""
        response = client.post(
            "/webhooks/shopify/orders",
            json=SAMPLE_ORDER_PAYLOAD,
            headers={
                "X-Shopify-Shop-Domain": "test-store.myshopify.com",
                "X-Shopify-Topic": "orders/create",
            },
        )
        assert response.status_code == 401
        assert "Invalid webhook signature" in response.json()["detail"]

    @patch("src.api.webhooks.verify_webhook_hmac")
    def test_webhook_requires_shop_domain(self, mock_verify, client):
        """Webhook should reject requests without shop domain."""
        mock_verify.return_value = True

        response = client.post(
            "/webhooks/shopify/orders",
            json=SAMPLE_ORDER_PAYLOAD,
            headers={
                "X-Shopify-Hmac-Sha256": "valid-hmac",
                "X-Shopify-Topic": "orders/create",
                # Missing X-Shopify-Shop-Domain header
            },
        )
        assert response.status_code == 400
        assert "Missing shop domain" in response.json()["detail"]

    @patch("src.api.deps.get_db")
    @patch("src.api.webhooks.verify_webhook_hmac")
    def test_webhook_creates_new_order(self, mock_verify, mock_get_db, client):
        """Webhook should create new order in database."""
        mock_verify.return_value = True

        # Mock database session and repositories
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        mock_customer = MagicMock()
        mock_customer.id = "customer-123"

        with patch("src.api.webhooks.CustomerRepository") as MockCustomerRepo:
            with patch("src.api.webhooks.OrderRepository") as MockOrderRepo:
                mock_customer_repo = MagicMock()
                mock_customer_repo.get_by_shop_domain.return_value = mock_customer
                MockCustomerRepo.return_value = mock_customer_repo

                mock_order_repo = MagicMock()
                mock_order_repo.get_by_shopify_id.return_value = None  # Order doesn't exist
                MockOrderRepo.return_value = mock_order_repo

                response = client.post(
                    "/webhooks/shopify/orders",
                    json=SAMPLE_ORDER_PAYLOAD,
                    headers={
                        "X-Shopify-Shop-Domain": "test-store.myshopify.com",
                        "X-Shopify-Topic": "orders/create",
                        "X-Shopify-Hmac-Sha256": "valid-hmac",
                    },
                )

                assert response.status_code == 200
                assert response.json()["status"] == "ok"
                mock_order_repo.create.assert_called_once()

    @patch("src.api.deps.get_db")
    @patch("src.api.webhooks.verify_webhook_hmac")
    def test_webhook_updates_existing_order(self, mock_verify, mock_get_db, client):
        """Webhook should update existing order on orders/updated."""
        mock_verify.return_value = True

        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        mock_customer = MagicMock()
        mock_customer.id = "customer-123"

        mock_existing_order = MagicMock()
        mock_existing_order.id = "order-456"

        with patch("src.api.webhooks.CustomerRepository") as MockCustomerRepo:
            with patch("src.api.webhooks.OrderRepository") as MockOrderRepo:
                mock_customer_repo = MagicMock()
                mock_customer_repo.get_by_shop_domain.return_value = mock_customer
                MockCustomerRepo.return_value = mock_customer_repo

                mock_order_repo = MagicMock()
                mock_order_repo.get_by_shopify_id.return_value = mock_existing_order
                MockOrderRepo.return_value = mock_order_repo

                response = client.post(
                    "/webhooks/shopify/orders",
                    json=SAMPLE_ORDER_PAYLOAD,
                    headers={
                        "X-Shopify-Shop-Domain": "test-store.myshopify.com",
                        "X-Shopify-Topic": "orders/updated",
                        "X-Shopify-Hmac-Sha256": "valid-hmac",
                    },
                )

                assert response.status_code == 200
                # Should not create new order
                mock_order_repo.create.assert_not_called()

    @patch("src.api.deps.get_db")
    @patch("src.api.webhooks.verify_webhook_hmac")
    def test_webhook_cancels_order(self, mock_verify, mock_get_db, client):
        """Webhook should mark order as cancelled on orders/cancelled."""
        mock_verify.return_value = True

        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        mock_customer = MagicMock()
        mock_customer.id = "customer-123"

        mock_existing_order = MagicMock()
        mock_existing_order.id = "order-456"

        with patch("src.api.webhooks.CustomerRepository") as MockCustomerRepo:
            with patch("src.api.webhooks.OrderRepository") as MockOrderRepo:
                mock_customer_repo = MagicMock()
                mock_customer_repo.get_by_shop_domain.return_value = mock_customer
                MockCustomerRepo.return_value = mock_customer_repo

                mock_order_repo = MagicMock()
                mock_order_repo.get_by_shopify_id.return_value = mock_existing_order
                MockOrderRepo.return_value = mock_order_repo

                cancelled_payload = {**SAMPLE_ORDER_PAYLOAD, "cancelled_at": "2026-01-12T12:00:00Z"}
                response = client.post(
                    "/webhooks/shopify/orders",
                    json=cancelled_payload,
                    headers={
                        "X-Shopify-Shop-Domain": "test-store.myshopify.com",
                        "X-Shopify-Topic": "orders/cancelled",
                        "X-Shopify-Hmac-Sha256": "valid-hmac",
                    },
                )

                assert response.status_code == 200
                mock_order_repo.update_status.assert_called_once_with(
                    mock_existing_order.id, "cancelled"
                )

    @patch("src.api.deps.get_db")
    @patch("src.api.webhooks.verify_webhook_hmac")
    def test_webhook_handles_unknown_shop(self, mock_verify, mock_get_db, client):
        """Webhook should return OK for unknown shop to prevent retries."""
        mock_verify.return_value = True

        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        with patch("src.api.webhooks.CustomerRepository") as MockCustomerRepo:
            mock_customer_repo = MagicMock()
            mock_customer_repo.get_by_shop_domain.return_value = None
            MockCustomerRepo.return_value = mock_customer_repo

            response = client.post(
                "/webhooks/shopify/orders",
                json=SAMPLE_ORDER_PAYLOAD,
                headers={
                    "X-Shopify-Shop-Domain": "unknown-store.myshopify.com",
                    "X-Shopify-Topic": "orders/create",
                    "X-Shopify-Hmac-Sha256": "valid-hmac",
                },
            )

            assert response.status_code == 200
            assert response.json()["message"] == "Shop not found"


class TestParseShopifyOrderWebhook:
    """Tests for parse_shopify_order_webhook helper function."""

    def test_parse_order_extracts_shipping_address(self):
        """Parser should extract and normalize shipping address."""
        from src.api.webhooks import parse_shopify_order_webhook
        from uuid import uuid4

        customer_id = uuid4()
        result = parse_shopify_order_webhook(SAMPLE_ORDER_PAYLOAD, customer_id)

        assert result["shipping_address"] == {
            "name": "John Smith",
            "street1": "123 Main St",
            "street2": "Apt 4B",
            "city": "New York",
            "state": "NY",
            "zip": "10001",
            "country": "US",
            "phone": "555-1234",
        }

    def test_parse_order_calculates_weight(self):
        """Parser should calculate total weight in ounces."""
        from src.api.webhooks import parse_shopify_order_webhook
        from uuid import uuid4

        customer_id = uuid4()
        result = parse_shopify_order_webhook(SAMPLE_ORDER_PAYLOAD, customer_id)

        # 500g * 2 + 250g * 1 = 1250g = ~44.1 oz
        expected_weight_oz = 1250 / 28.3495
        assert abs(result["weight_oz"] - expected_weight_oz) < 0.01

    def test_parse_order_extracts_line_items(self):
        """Parser should extract line items."""
        from src.api.webhooks import parse_shopify_order_webhook
        from uuid import uuid4

        customer_id = uuid4()
        result = parse_shopify_order_webhook(SAMPLE_ORDER_PAYLOAD, customer_id)

        assert len(result["line_items"]) == 2
        assert result["line_items"][0]["title"] == "Test Product"
        assert result["line_items"][0]["quantity"] == 2

    def test_parse_order_determines_status(self):
        """Parser should determine order status from fulfillment_status."""
        from src.api.webhooks import parse_shopify_order_webhook
        from uuid import uuid4

        customer_id = uuid4()

        # Unfulfilled (null)
        result = parse_shopify_order_webhook(SAMPLE_ORDER_PAYLOAD, customer_id)
        assert result["status"] == "unfulfilled"

        # Fulfilled
        fulfilled_payload = {**SAMPLE_ORDER_PAYLOAD, "fulfillment_status": "fulfilled"}
        result = parse_shopify_order_webhook(fulfilled_payload, customer_id)
        assert result["status"] == "fulfilled"

        # Partial
        partial_payload = {**SAMPLE_ORDER_PAYLOAD, "fulfillment_status": "partial"}
        result = parse_shopify_order_webhook(partial_payload, customer_id)
        assert result["status"] == "partial"


class TestShopifyAdminClient:
    """Tests for ShopifyAdminClient."""

    @pytest.mark.asyncio
    async def test_get_orders_returns_parsed_orders(self):
        """get_orders should return list of ShopifyOrder objects."""
        from src.auth.shopify import ShopifyAdminClient, ShopifyOrder

        client = ShopifyAdminClient("test.myshopify.com", "test-token")

        mock_response = {
            "orders": [SAMPLE_ORDER_PAYLOAD]
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )
            MockClient.return_value.__aenter__.return_value = mock_instance

            orders = await client.get_orders()

            assert len(orders) == 1
            assert isinstance(orders[0], ShopifyOrder)
            assert orders[0].id == str(SAMPLE_ORDER_PAYLOAD["id"])
            assert orders[0].order_number == SAMPLE_ORDER_PAYLOAD["order_number"]

    @pytest.mark.asyncio
    async def test_get_order_returns_single_order(self):
        """get_order should return a single ShopifyOrder."""
        from src.auth.shopify import ShopifyAdminClient

        client = ShopifyAdminClient("test.myshopify.com", "test-token")

        mock_response = {"order": SAMPLE_ORDER_PAYLOAD}

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )
            MockClient.return_value.__aenter__.return_value = mock_instance

            order = await client.get_order("5678901234")

            assert order is not None
            assert order.id == str(SAMPLE_ORDER_PAYLOAD["id"])

    @pytest.mark.asyncio
    async def test_get_order_returns_none_for_404(self):
        """get_order should return None for non-existent order."""
        from src.auth.shopify import ShopifyAdminClient

        client = ShopifyAdminClient("test.myshopify.com", "test-token")

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = MagicMock(status_code=404)
            MockClient.return_value.__aenter__.return_value = mock_instance

            order = await client.get_order("nonexistent")

            assert order is None

    @pytest.mark.asyncio
    async def test_create_fulfillment_sends_tracking_info(self):
        """create_fulfillment should send tracking info to Shopify."""
        from src.auth.shopify import ShopifyAdminClient

        client = ShopifyAdminClient("test.myshopify.com", "test-token")

        # Mock fulfillment orders response
        fulfillment_orders_response = {
            "fulfillment_orders": [
                {
                    "id": 123456,
                    "status": "open",
                    "line_items": [
                        {"id": 1, "line_item_id": 11111, "quantity": 2},
                        {"id": 2, "line_item_id": 22222, "quantity": 1},
                    ],
                }
            ]
        }

        # Mock fulfillment creation response
        fulfillment_response = {
            "fulfillment": {
                "id": 999999,
                "status": "success",
            }
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()

            # First call: get fulfillment orders
            # Second call: create fulfillment
            mock_instance.get.return_value = MagicMock(
                status_code=200,
                json=lambda: fulfillment_orders_response,
                raise_for_status=lambda: None,
            )
            mock_instance.post.return_value = MagicMock(
                status_code=200,
                json=lambda: fulfillment_response,
                raise_for_status=lambda: None,
            )
            MockClient.return_value.__aenter__.return_value = mock_instance

            result = await client.create_fulfillment(
                order_id="5678901234",
                tracking_number="9400111899223033005115",
                tracking_company="USPS",
            )

            assert result.id == "999999"
            assert result.tracking_number == "9400111899223033005115"
            mock_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_webhooks_creates_webhooks(self):
        """register_webhooks should register order webhooks."""
        from src.auth.shopify import ShopifyAdminClient

        client = ShopifyAdminClient("test.myshopify.com", "test-token")

        webhook_response = {
            "webhook": {
                "id": 12345,
                "topic": "orders/create",
            }
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = MagicMock(
                status_code=201,
                json=lambda: webhook_response,
            )
            MockClient.return_value.__aenter__.return_value = mock_instance

            result = await client.register_webhooks("https://myapp.com")

            # Should attempt to register 3 webhooks
            assert mock_instance.post.call_count == 3


class TestOrderSyncEndpoint:
    """Tests for /api/orders/sync endpoint."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_sync_requires_authentication(self, client):
        """Sync endpoint should require authentication."""
        response = client.post("/api/orders/sync")
        assert response.status_code == 401


class TestFulfillmentWriteback:
    """Tests for Shopify fulfillment write-back on shipment creation."""

    @pytest.mark.asyncio
    async def test_create_shopify_fulfillment_success(self):
        """_create_shopify_fulfillment should create fulfillment in Shopify."""
        from src.api.shipping import _create_shopify_fulfillment

        mock_customer = MagicMock()
        mock_customer.id = "customer-123"
        mock_customer.shop_domain = "test-store.myshopify.com"
        mock_customer.shopify_access_token = "encrypted-token"

        with patch("src.api.shipping.decrypt_token") as mock_decrypt:
            mock_decrypt.return_value = "decrypted-token"

            with patch("src.api.shipping.ShopifyAdminClient") as MockClient:
                mock_instance = MagicMock()
                mock_instance.create_fulfillment = AsyncMock(
                    return_value=MagicMock(id="fulfillment-123")
                )
                MockClient.return_value = mock_instance

                result = await _create_shopify_fulfillment(
                    customer=mock_customer,
                    shopify_order_id="5678901234",
                    tracking_number="9400111899223033005115",
                    carrier="USPS",
                )

                assert result is True
                mock_instance.create_fulfillment.assert_called_once_with(
                    order_id="5678901234",
                    tracking_number="9400111899223033005115",
                    tracking_company="USPS",
                    notify_customer=True,
                )

    @pytest.mark.asyncio
    async def test_create_shopify_fulfillment_skips_without_token(self):
        """_create_shopify_fulfillment should skip if no token."""
        from src.api.shipping import _create_shopify_fulfillment

        mock_customer = MagicMock()
        mock_customer.id = "customer-123"
        mock_customer.shopify_access_token = None

        result = await _create_shopify_fulfillment(
            customer=mock_customer,
            shopify_order_id="5678901234",
            tracking_number="9400111899223033005115",
            carrier="USPS",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_create_shopify_fulfillment_handles_api_error(self):
        """_create_shopify_fulfillment should handle API errors gracefully."""
        from src.api.shipping import _create_shopify_fulfillment

        mock_customer = MagicMock()
        mock_customer.id = "customer-123"
        mock_customer.shop_domain = "test-store.myshopify.com"
        mock_customer.shopify_access_token = "encrypted-token"

        with patch("src.api.shipping.decrypt_token") as mock_decrypt:
            mock_decrypt.return_value = "decrypted-token"

            with patch("src.api.shipping.ShopifyAdminClient") as MockClient:
                mock_instance = MagicMock()
                mock_instance.create_fulfillment = AsyncMock(
                    side_effect=Exception("API Error")
                )
                MockClient.return_value = mock_instance

                result = await _create_shopify_fulfillment(
                    customer=mock_customer,
                    shopify_order_id="5678901234",
                    tracking_number="9400111899223033005115",
                    carrier="USPS",
                )

                # Should return False but not raise
                assert result is False

    @pytest.mark.asyncio
    async def test_create_shopify_fulfillment_maps_carrier_names(self):
        """_create_shopify_fulfillment should map carrier names correctly."""
        from src.api.shipping import _create_shopify_fulfillment

        mock_customer = MagicMock()
        mock_customer.id = "customer-123"
        mock_customer.shop_domain = "test-store.myshopify.com"
        mock_customer.shopify_access_token = "encrypted-token"

        with patch("src.api.shipping.decrypt_token") as mock_decrypt:
            mock_decrypt.return_value = "decrypted-token"

            with patch("src.api.shipping.ShopifyAdminClient") as MockClient:
                mock_instance = MagicMock()
                mock_instance.create_fulfillment = AsyncMock(
                    return_value=MagicMock(id="fulfillment-123")
                )
                MockClient.return_value = mock_instance

                # Test DHL mapping
                await _create_shopify_fulfillment(
                    customer=mock_customer,
                    shopify_order_id="5678901234",
                    tracking_number="123456",
                    carrier="DHL",
                )

                mock_instance.create_fulfillment.assert_called_with(
                    order_id="5678901234",
                    tracking_number="123456",
                    tracking_company="DHL Express",
                    notify_customer=True,
                )
