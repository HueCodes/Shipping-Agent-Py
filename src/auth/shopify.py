"""Shopify OAuth 2.0 implementation and Admin API client."""

import os
import re
import hmac
import hashlib
import base64
import secrets
import logging
from urllib.parse import urlencode, parse_qs
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

import httpx


logger = logging.getLogger(__name__)


# Shopify OAuth endpoints
SHOPIFY_AUTH_URL = "https://{shop}/admin/oauth/authorize"
SHOPIFY_TOKEN_URL = "https://{shop}/admin/oauth/access_token"

# Regex for valid Shopify shop domains
SHOP_DOMAIN_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$")


@dataclass
class ShopifyConfig:
    """Shopify OAuth configuration."""

    api_key: str
    api_secret: str
    scopes: str
    app_url: str

    @classmethod
    def from_env(cls) -> "ShopifyConfig":
        """Load configuration from environment variables."""
        api_key = os.getenv("SHOPIFY_API_KEY")
        api_secret = os.getenv("SHOPIFY_API_SECRET")
        scopes = os.getenv("SHOPIFY_SCOPES", "read_orders,write_fulfillments")
        app_url = os.getenv("APP_URL", "http://localhost:8000")

        if not api_key or not api_secret:
            raise ValueError(
                "SHOPIFY_API_KEY and SHOPIFY_API_SECRET must be set"
            )

        return cls(
            api_key=api_key,
            api_secret=api_secret,
            scopes=scopes,
            app_url=app_url.rstrip("/"),
        )


@dataclass
class OAuthTokenResponse:
    """Response from Shopify token exchange."""

    access_token: str
    scope: str
    expires_in: Optional[int] = None
    associated_user_scope: Optional[str] = None
    associated_user: Optional[dict] = None


class ShopifyOAuth:
    """Shopify OAuth 2.0 client."""

    def __init__(self, config: Optional[ShopifyConfig] = None):
        """Initialize OAuth client.

        Args:
            config: Shopify configuration, or None to load from env
        """
        self.config = config or ShopifyConfig.from_env()

    @staticmethod
    def validate_shop_domain(shop: str) -> bool:
        """Validate that a shop domain is a valid Shopify domain.

        Args:
            shop: Shop domain to validate

        Returns:
            True if valid, False otherwise
        """
        if not shop:
            return False
        return bool(SHOP_DOMAIN_PATTERN.match(shop))

    @staticmethod
    def generate_nonce() -> str:
        """Generate a cryptographically secure nonce for OAuth state.

        Returns:
            64-character hex string
        """
        return secrets.token_hex(32)

    def get_authorization_url(self, shop: str, nonce: str) -> str:
        """Build the Shopify authorization URL.

        Args:
            shop: Shopify store domain (e.g., store.myshopify.com)
            nonce: State parameter for CSRF protection

        Returns:
            Full authorization URL to redirect the user to
        """
        if not self.validate_shop_domain(shop):
            raise ValueError(f"Invalid shop domain: {shop}")

        redirect_uri = f"{self.config.app_url}/auth/shopify/callback"

        params = {
            "client_id": self.config.api_key,
            "scope": self.config.scopes,
            "redirect_uri": redirect_uri,
            "state": nonce,
        }

        return SHOPIFY_AUTH_URL.format(shop=shop) + "?" + urlencode(params)

    async def exchange_code_for_token(
        self, shop: str, code: str
    ) -> OAuthTokenResponse:
        """Exchange authorization code for access token.

        Args:
            shop: Shopify store domain
            code: Authorization code from callback

        Returns:
            OAuthTokenResponse with access token and granted scopes

        Raises:
            httpx.HTTPStatusError: If token exchange fails
        """
        url = SHOPIFY_TOKEN_URL.format(shop=shop)

        payload = {
            "client_id": self.config.api_key,
            "client_secret": self.config.api_secret,
            "code": code,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        return OAuthTokenResponse(
            access_token=data["access_token"],
            scope=data.get("scope", ""),
            expires_in=data.get("expires_in"),
            associated_user_scope=data.get("associated_user_scope"),
            associated_user=data.get("associated_user"),
        )

    def verify_callback_hmac(self, query_params: dict) -> bool:
        """Verify HMAC signature on OAuth callback.

        Args:
            query_params: Dictionary of query parameters from callback

        Returns:
            True if HMAC is valid, False otherwise
        """
        return verify_hmac(query_params, self.config.api_secret)


def verify_hmac(query_params: dict, secret: str) -> bool:
    """Verify HMAC signature on Shopify request query parameters.

    Shopify signs requests with HMAC-SHA256 of the query string
    (excluding the hmac parameter itself).

    Args:
        query_params: Dictionary of query parameters
        secret: Shopify API secret

    Returns:
        True if HMAC is valid, False otherwise
    """
    if "hmac" not in query_params:
        return False

    provided_hmac = query_params["hmac"]

    # Build message from sorted params (excluding hmac)
    params = []
    for key, value in sorted(query_params.items()):
        if key == "hmac":
            continue
        # Handle list values (from parse_qs)
        if isinstance(value, list):
            value = value[0]
        params.append(f"{key}={value}")

    message = "&".join(params)

    # Compute expected HMAC
    computed = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    # Timing-safe comparison
    return hmac.compare_digest(computed, provided_hmac)


def verify_webhook_hmac(body: bytes, hmac_header: str, secret: str) -> bool:
    """Verify HMAC signature on Shopify webhook.

    Shopify signs webhook bodies with HMAC-SHA256.

    Args:
        body: Raw request body bytes
        hmac_header: X-Shopify-Hmac-Sha256 header value
        secret: Shopify API secret (or webhook secret)

    Returns:
        True if HMAC is valid, False otherwise
    """
    if not hmac_header:
        return False

    computed = base64.b64encode(
        hmac.new(
            secret.encode(),
            body,
            hashlib.sha256
        ).digest()
    ).decode()

    return hmac.compare_digest(computed, hmac_header)


def parse_shop_from_host(host: str) -> Optional[str]:
    """Parse shop domain from Shopify host parameter.

    The host parameter is base64-encoded shop domain.

    Args:
        host: Base64-encoded host from Shopify

    Returns:
        Decoded shop domain, or None if invalid
    """
    try:
        decoded = base64.b64decode(host).decode()
        # Host format is "shop-name.myshopify.com/admin"
        shop = decoded.split("/")[0]
        if ShopifyOAuth.validate_shop_domain(shop):
            return shop
        return None
    except Exception:
        return None


async def validate_access_token(shop: str, access_token: str) -> bool:
    """Test if a Shopify access token is still valid.

    Shopify offline access tokens don't expire, but can be revoked when:
    - Merchant uninstalls/reinstalls app
    - Merchant changes permissions
    - Shopify rotates tokens (rare)

    This function makes a lightweight API call to verify the token works.

    Args:
        shop: Shopify store domain (e.g., store.myshopify.com)
        access_token: The access token to validate

    Returns:
        True if token is valid and working, False otherwise
    """
    if not shop or not access_token:
        return False

    # Validate shop domain format
    if not ShopifyOAuth.validate_shop_domain(shop):
        return False

    # Use the shop.json endpoint as a lightweight validation call
    url = f"https://{shop}/admin/api/2024-01/shop.json"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                headers={
                    "X-Shopify-Access-Token": access_token,
                    "Content-Type": "application/json",
                },
            )

            # 200 = valid token
            # 401/403 = invalid or revoked token
            # Other errors = network issues, treat as unknown
            if response.status_code == 200:
                return True
            elif response.status_code in (401, 403):
                return False
            else:
                # For other errors (5xx, network issues), we can't determine
                # validity - return True to avoid false negatives
                return True
    except httpx.TimeoutException:
        # Timeout - can't determine, assume valid to avoid false negatives
        return True
    except Exception:
        # Network or other error - can't determine, assume valid
        return True


# Shopify Admin API version
SHOPIFY_API_VERSION = "2024-01"


@dataclass
class ShopifyOrder:
    """Parsed Shopify order data."""

    id: str  # Shopify order ID (numeric string)
    order_number: str  # Human-readable order number (e.g., "#1001")
    name: str  # Display name (e.g., "#1001")
    email: str | None
    fulfillment_status: str | None  # null, "fulfilled", "partial"
    financial_status: str  # "paid", "pending", etc.
    shipping_address: dict | None
    line_items: list[dict]
    total_weight: int  # Weight in grams
    created_at: str
    updated_at: str
    cancelled_at: str | None = None


@dataclass
class ShopifyFulfillment:
    """Parsed Shopify fulfillment data."""

    id: str
    order_id: str
    status: str
    tracking_number: str | None
    tracking_url: str | None
    tracking_company: str | None


class ShopifyAdminClient:
    """Shopify Admin API client for order and fulfillment operations."""

    def __init__(self, shop: str, access_token: str):
        """Initialize the Admin API client.

        Args:
            shop: Shopify store domain (e.g., store.myshopify.com)
            access_token: Shopify access token (decrypted)
        """
        self.shop = shop
        self.access_token = access_token
        self.base_url = f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}"

    def _headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    async def get_orders(
        self,
        status: str = "unfulfilled",
        limit: int = 50,
        since_id: str | None = None,
        created_at_min: datetime | None = None,
    ) -> list[ShopifyOrder]:
        """Fetch orders from Shopify.

        Args:
            status: Fulfillment status filter ("unfulfilled", "any", "fulfilled")
            limit: Maximum number of orders to return (max 250)
            since_id: Only return orders after this ID
            created_at_min: Only return orders created after this time

        Returns:
            List of ShopifyOrder objects
        """
        params = {
            "status": "any",  # Get all orders regardless of financial status
            "limit": min(limit, 250),
        }

        if status == "unfulfilled":
            params["fulfillment_status"] = "unfulfilled"
        elif status == "fulfilled":
            params["fulfillment_status"] = "shipped"

        if since_id:
            params["since_id"] = since_id
        if created_at_min:
            params["created_at_min"] = created_at_min.isoformat()

        url = f"{self.base_url}/orders.json"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers(), params=params)
            response.raise_for_status()
            data = response.json()

        orders = []
        for o in data.get("orders", []):
            orders.append(self._parse_order(o))
        return orders

    async def get_order(self, order_id: str) -> ShopifyOrder | None:
        """Fetch a single order by ID.

        Args:
            order_id: Shopify order ID

        Returns:
            ShopifyOrder object or None if not found
        """
        url = f"{self.base_url}/orders/{order_id}.json"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers())
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()

        return self._parse_order(data.get("order", {}))

    def _parse_order(self, data: dict) -> ShopifyOrder:
        """Parse Shopify order JSON into ShopifyOrder object."""
        # Calculate total weight from line items
        total_weight = 0
        line_items = []
        for item in data.get("line_items", []):
            total_weight += item.get("grams", 0) * item.get("quantity", 1)
            line_items.append({
                "id": str(item.get("id")),
                "title": item.get("title"),
                "quantity": item.get("quantity", 1),
                "price": item.get("price"),
                "sku": item.get("sku"),
                "grams": item.get("grams", 0),
                "variant_title": item.get("variant_title"),
            })

        # Parse shipping address
        shipping_address = None
        if data.get("shipping_address"):
            addr = data["shipping_address"]
            shipping_address = {
                "name": addr.get("name"),
                "street1": addr.get("address1"),
                "street2": addr.get("address2"),
                "city": addr.get("city"),
                "state": addr.get("province_code"),
                "zip": addr.get("zip"),
                "country": addr.get("country_code", "US"),
                "phone": addr.get("phone"),
            }

        return ShopifyOrder(
            id=str(data.get("id")),
            order_number=data.get("order_number", ""),
            name=data.get("name", ""),
            email=data.get("email"),
            fulfillment_status=data.get("fulfillment_status"),
            financial_status=data.get("financial_status", ""),
            shipping_address=shipping_address,
            line_items=line_items,
            total_weight=total_weight,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            cancelled_at=data.get("cancelled_at"),
        )

    async def create_fulfillment(
        self,
        order_id: str,
        tracking_number: str,
        tracking_company: str,
        tracking_url: str | None = None,
        line_item_ids: list[str] | None = None,
        notify_customer: bool = True,
    ) -> ShopifyFulfillment:
        """Create a fulfillment for an order in Shopify.

        This marks the order (or specific line items) as shipped and sends
        tracking info to the customer.

        Args:
            order_id: Shopify order ID
            tracking_number: Carrier tracking number
            tracking_company: Carrier name (e.g., "USPS", "UPS", "FedEx")
            tracking_url: Optional tracking URL
            line_item_ids: Specific line items to fulfill (None = all)
            notify_customer: Whether to send shipment notification email

        Returns:
            ShopifyFulfillment object

        Raises:
            httpx.HTTPStatusError: If the API call fails
        """
        # First, get the fulfillment order for this order
        fulfillment_orders = await self._get_fulfillment_orders(order_id)
        if not fulfillment_orders:
            raise ValueError(f"No fulfillment orders found for order {order_id}")

        # Get the first open fulfillment order
        fulfillment_order = None
        for fo in fulfillment_orders:
            if fo.get("status") == "open":
                fulfillment_order = fo
                break

        if not fulfillment_order:
            raise ValueError(f"No open fulfillment orders for order {order_id}")

        fulfillment_order_id = fulfillment_order["id"]

        # Build line items payload
        line_items_payload = []
        for item in fulfillment_order.get("line_items", []):
            if line_item_ids is None or str(item.get("line_item_id")) in line_item_ids:
                line_items_payload.append({
                    "id": item["id"],
                    "quantity": item["quantity"],
                })

        # Create fulfillment using the new fulfillment API
        url = f"{self.base_url}/fulfillments.json"
        payload = {
            "fulfillment": {
                "line_items_by_fulfillment_order": [
                    {
                        "fulfillment_order_id": fulfillment_order_id,
                        "fulfillment_order_line_items": line_items_payload,
                    }
                ],
                "tracking_info": {
                    "number": tracking_number,
                    "company": tracking_company,
                },
                "notify_customer": notify_customer,
            }
        }

        if tracking_url:
            payload["fulfillment"]["tracking_info"]["url"] = tracking_url

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=self._headers(), json=payload)
            response.raise_for_status()
            data = response.json()

        fulfillment = data.get("fulfillment", {})
        return ShopifyFulfillment(
            id=str(fulfillment.get("id")),
            order_id=order_id,
            status=fulfillment.get("status", ""),
            tracking_number=tracking_number,
            tracking_url=tracking_url,
            tracking_company=tracking_company,
        )

    async def _get_fulfillment_orders(self, order_id: str) -> list[dict]:
        """Get fulfillment orders for a Shopify order.

        Args:
            order_id: Shopify order ID

        Returns:
            List of fulfillment order objects
        """
        url = f"{self.base_url}/orders/{order_id}/fulfillment_orders.json"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            data = response.json()

        return data.get("fulfillment_orders", [])

    async def register_webhooks(self, app_url: str) -> list[dict]:
        """Register webhooks for order events.

        Args:
            app_url: Base URL of the app (e.g., https://myapp.com)

        Returns:
            List of created webhook objects
        """
        webhooks_to_register = [
            {"topic": "orders/create", "address": f"{app_url}/webhooks/shopify/orders"},
            {"topic": "orders/updated", "address": f"{app_url}/webhooks/shopify/orders"},
            {"topic": "orders/cancelled", "address": f"{app_url}/webhooks/shopify/orders"},
        ]

        created = []
        url = f"{self.base_url}/webhooks.json"

        async with httpx.AsyncClient(timeout=30.0) as client:
            for webhook in webhooks_to_register:
                payload = {
                    "webhook": {
                        "topic": webhook["topic"],
                        "address": webhook["address"],
                        "format": "json",
                    }
                }
                try:
                    response = await client.post(url, headers=self._headers(), json=payload)
                    if response.status_code == 201:
                        created.append(response.json().get("webhook", {}))
                        logger.info("Registered webhook: %s", webhook["topic"])
                    elif response.status_code == 422:
                        # Webhook already exists
                        logger.info("Webhook already exists: %s", webhook["topic"])
                    else:
                        logger.warning(
                            "Failed to register webhook %s: %s",
                            webhook["topic"],
                            response.text,
                        )
                except Exception as e:
                    logger.error("Error registering webhook %s: %s", webhook["topic"], e)

        return created

    async def list_webhooks(self) -> list[dict]:
        """List all registered webhooks.

        Returns:
            List of webhook objects
        """
        url = f"{self.base_url}/webhooks.json"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            data = response.json()

        return data.get("webhooks", [])
