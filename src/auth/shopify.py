"""Shopify OAuth 2.0 implementation."""

import os
import re
import hmac
import hashlib
import base64
import secrets
from urllib.parse import urlencode, parse_qs
from dataclasses import dataclass
from typing import Optional

import httpx


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
