"""Tests for authentication module."""

import os
import pytest
import hmac
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock, MagicMock

# Set test environment
os.environ["SECRET_KEY"] = "test-secret-key-for-testing"
os.environ["SHOPIFY_API_KEY"] = "test-api-key"
os.environ["SHOPIFY_API_SECRET"] = "test-api-secret"
os.environ["APP_URL"] = "https://test.example.com"


class TestCrypto:
    """Tests for token encryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypted tokens can be decrypted."""
        from src.auth.crypto import encrypt_token, decrypt_token

        original = "shpat_test_token_12345"
        encrypted = encrypt_token(original)

        # Encrypted should be different from original
        assert encrypted != original
        assert len(encrypted) > len(original)

        # Decrypt should return original
        decrypted = decrypt_token(encrypted)
        assert decrypted == original

    def test_encrypt_empty_string(self):
        """Test encrypting empty string returns empty."""
        from src.auth.crypto import encrypt_token

        assert encrypt_token("") == ""
        assert encrypt_token(None) == ""

    def test_decrypt_empty_string(self):
        """Test decrypting empty string returns None."""
        from src.auth.crypto import decrypt_token

        assert decrypt_token("") is None
        assert decrypt_token(None) is None

    def test_decrypt_invalid_token(self):
        """Test decrypting invalid token returns None."""
        from src.auth.crypto import decrypt_token

        assert decrypt_token("invalid-not-encrypted") is None
        assert decrypt_token("abc123") is None

    def test_generate_encryption_key(self):
        """Test encryption key generation."""
        from src.auth.crypto import generate_encryption_key

        key = generate_encryption_key()
        assert len(key) == 44  # Fernet keys are 44 chars base64
        assert key.endswith("=")  # Base64 padding


class TestJWT:
    """Tests for JWT session tokens."""

    def test_create_and_verify_token(self):
        """Test creating and verifying a token."""
        from src.auth.jwt import create_session_token, verify_session_token

        customer_id = "12345678-1234-1234-1234-123456789abc"
        shop_domain = "test-store.myshopify.com"

        token = create_session_token(customer_id, shop_domain)
        assert token is not None
        assert len(token) > 50

        session = verify_session_token(token)
        assert session is not None
        assert session.customer_id == customer_id
        assert session.shop_domain == shop_domain

    def test_token_expiration(self):
        """Test that tokens have correct expiration."""
        from src.auth.jwt import create_session_token, verify_session_token

        token = create_session_token("test-id", "test.myshopify.com", expiration_hours=1)
        session = verify_session_token(token)

        assert session is not None
        # Expiration should be ~1 hour from now
        time_diff = session.exp - datetime.now(timezone.utc)
        assert timedelta(minutes=55) < time_diff < timedelta(hours=1, minutes=5)

    def test_verify_invalid_token(self):
        """Test that invalid tokens return None."""
        from src.auth.jwt import verify_session_token

        assert verify_session_token("invalid-token") is None
        assert verify_session_token("") is None
        assert verify_session_token("eyJ.invalid.token") is None

    def test_verify_expired_token(self):
        """Test that expired tokens return None."""
        from src.auth.jwt import create_session_token, verify_session_token
        import jwt

        # Create a token that's already expired
        payload = {
            "sub": "test-id",
            "shop": "test.myshopify.com",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = jwt.encode(payload, "test-secret-key-for-testing", algorithm="HS256")

        assert verify_session_token(expired_token) is None

    def test_refresh_token(self):
        """Test refreshing a token."""
        import time
        from src.auth.jwt import create_session_token, refresh_session_token, verify_session_token

        original = create_session_token("test-id", "test.myshopify.com")

        # Wait a moment so timestamps differ
        time.sleep(0.01)

        refreshed = refresh_session_token(original)

        assert refreshed is not None
        # Tokens might be same if within same second - just verify it works
        session = verify_session_token(refreshed)
        assert session is not None
        assert session.customer_id == "test-id"


class TestShopifyOAuth:
    """Tests for Shopify OAuth client."""

    def test_validate_shop_domain(self):
        """Test shop domain validation."""
        from src.auth.shopify import ShopifyOAuth

        # Valid domains
        assert ShopifyOAuth.validate_shop_domain("test-store.myshopify.com") is True
        assert ShopifyOAuth.validate_shop_domain("my-shop.myshopify.com") is True
        assert ShopifyOAuth.validate_shop_domain("store123.myshopify.com") is True

        # Invalid domains
        assert ShopifyOAuth.validate_shop_domain("") is False
        assert ShopifyOAuth.validate_shop_domain(None) is False
        assert ShopifyOAuth.validate_shop_domain("test.com") is False
        assert ShopifyOAuth.validate_shop_domain("myshopify.com") is False
        assert ShopifyOAuth.validate_shop_domain("-invalid.myshopify.com") is False
        assert ShopifyOAuth.validate_shop_domain("test.otherdomain.com") is False

    def test_generate_nonce(self):
        """Test nonce generation."""
        from src.auth.shopify import ShopifyOAuth

        nonce1 = ShopifyOAuth.generate_nonce()
        nonce2 = ShopifyOAuth.generate_nonce()

        # Should be 64 hex characters
        assert len(nonce1) == 64
        assert all(c in "0123456789abcdef" for c in nonce1)

        # Each should be unique
        assert nonce1 != nonce2

    def test_get_authorization_url(self):
        """Test building authorization URL."""
        from src.auth.shopify import ShopifyOAuth

        oauth = ShopifyOAuth()
        nonce = "test-nonce-12345"

        url = oauth.get_authorization_url("test-store.myshopify.com", nonce)

        assert "test-store.myshopify.com" in url
        assert "/admin/oauth/authorize" in url
        assert "client_id=test-api-key" in url
        assert "state=test-nonce-12345" in url
        assert "redirect_uri=" in url
        assert "scope=" in url

    def test_authorization_url_invalid_shop(self):
        """Test that invalid shop domain raises error."""
        from src.auth.shopify import ShopifyOAuth

        oauth = ShopifyOAuth()

        with pytest.raises(ValueError, match="Invalid shop domain"):
            oauth.get_authorization_url("invalid-domain.com", "nonce")

    def test_verify_hmac(self):
        """Test HMAC verification."""
        from src.auth.shopify import verify_hmac

        secret = "test-secret"

        # Build test params and compute valid HMAC
        params = {
            "code": "abc123",
            "shop": "test.myshopify.com",
            "state": "nonce123",
            "timestamp": "1234567890",
        }

        # Compute HMAC like Shopify does
        message = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        valid_hmac = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

        params["hmac"] = valid_hmac

        assert verify_hmac(params, secret) is True

        # Invalid HMAC
        params["hmac"] = "invalid-hmac"
        assert verify_hmac(params, secret) is False

        # Missing HMAC
        del params["hmac"]
        assert verify_hmac(params, secret) is False

    def test_verify_webhook_hmac(self):
        """Test webhook HMAC verification."""
        from src.auth.shopify import verify_webhook_hmac

        secret = "webhook-secret"
        body = b'{"shop_id": 123, "domain": "test.myshopify.com"}'

        # Compute valid HMAC
        valid_hmac = base64.b64encode(
            hmac.new(secret.encode(), body, hashlib.sha256).digest()
        ).decode()

        assert verify_webhook_hmac(body, valid_hmac, secret) is True
        assert verify_webhook_hmac(body, "invalid", secret) is False
        assert verify_webhook_hmac(body, "", secret) is False

    @pytest.mark.asyncio
    async def test_exchange_code_for_token(self):
        """Test token exchange with mocked HTTP."""
        from src.auth.shopify import ShopifyOAuth
        from unittest.mock import MagicMock

        oauth = ShopifyOAuth()

        # Mock the httpx response - use MagicMock for sync json()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "shpat_test_token",
            "scope": "read_orders,write_fulfillments",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await oauth.exchange_code_for_token("test.myshopify.com", "auth-code")

            assert result.access_token == "shpat_test_token"
            assert result.scope == "read_orders,write_fulfillments"


class TestShopifyConfig:
    """Tests for Shopify configuration."""

    def test_config_from_env(self):
        """Test loading config from environment."""
        from src.auth.shopify import ShopifyConfig

        config = ShopifyConfig.from_env()

        assert config.api_key == "test-api-key"
        assert config.api_secret == "test-api-secret"
        assert config.app_url == "https://test.example.com"

    def test_config_missing_key(self):
        """Test that missing keys raise error."""
        from src.auth.shopify import ShopifyConfig

        # Temporarily remove API key
        original = os.environ.pop("SHOPIFY_API_KEY")
        try:
            with pytest.raises(ValueError, match="SHOPIFY_API_KEY"):
                ShopifyConfig.from_env()
        finally:
            os.environ["SHOPIFY_API_KEY"] = original


class TestIntegrationAuth:
    """Integration tests for auth endpoints."""

    @pytest.fixture(scope="class")
    def setup_database(self):
        """Set up test database once for all tests in this class."""
        os.environ["MOCK_MODE"] = "1"
        os.environ["DATABASE_URL"] = "sqlite:///./test_auth.db"

        from sqlalchemy import create_engine
        from src.db.models import Base

        engine = create_engine(
            "sqlite:///./test_auth.db",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        yield engine
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

        import pathlib
        pathlib.Path("test_auth.db").unlink(missing_ok=True)

    @pytest.fixture
    def test_client(self, setup_database):
        """Create test client."""
        from sqlalchemy.orm import sessionmaker
        from fastapi.testclient import TestClient

        from src.server import app, get_db

        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=setup_database
        )

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            yield client

        app.dependency_overrides.clear()

    def test_oauth_start_invalid_shop(self, test_client):
        """Test OAuth start with invalid shop domain."""
        response = test_client.get("/auth/shopify?shop=invalid.com", follow_redirects=False)
        assert response.status_code == 400
        assert "Invalid shop domain" in response.json()["detail"]

    def test_oauth_start_valid_shop(self, test_client):
        """Test OAuth start redirects to Shopify."""
        response = test_client.get(
            "/auth/shopify?shop=test-store.myshopify.com",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "myshopify.com" in response.headers["location"]
        assert "oauth/authorize" in response.headers["location"]

    def test_jwt_auth_header(self, test_client, setup_database):
        """Test that JWT auth header works."""
        from sqlalchemy.orm import sessionmaker
        from src.auth.jwt import create_session_token
        from src.db.repository import CustomerRepository

        # Create a customer using the test database
        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=setup_database
        )
        db = TestingSessionLocal()
        customer_repo = CustomerRepository(db)
        customer = customer_repo.create({
            "shop_domain": "jwt-test.myshopify.com",
            "name": "JWT Test Store",
            "email": "test@test.com",
        })
        db.commit()

        # Store values before closing session
        customer_id = str(customer.id)
        shop_domain = customer.shop_domain
        db.close()

        # Create JWT token
        token = create_session_token(customer_id, shop_domain)

        # Test endpoint with JWT
        response = test_client.get(
            "/api/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["shop_domain"] == "jwt-test.myshopify.com"

    def test_invalid_jwt_rejected(self, test_client):
        """Test that invalid JWT is rejected."""
        response = test_client.get(
            "/api/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    def test_backward_compatible_header_auth(self, test_client, setup_database):
        """Test that X-Customer-ID still works."""
        from sqlalchemy.orm import sessionmaker
        from src.db.repository import CustomerRepository

        # Create a customer using the test database
        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=setup_database
        )
        db = TestingSessionLocal()
        customer_repo = CustomerRepository(db)
        customer = customer_repo.create({
            "shop_domain": "header-test.myshopify.com",
            "name": "Header Test Store",
            "email": "test@test.com",
        })
        db.commit()

        # Store ID before closing session
        customer_id = str(customer.id)
        db.close()

        # Test with X-Customer-ID header
        response = test_client.get(
            "/api/me",
            headers={"X-Customer-ID": customer_id},
        )
        assert response.status_code == 200
        assert response.json()["shop_domain"] == "header-test.myshopify.com"


class TestTokenValidation:
    """Tests for Shopify token validation."""

    @pytest.fixture(scope="class")
    def setup_database(self):
        """Set up test database once for all tests in this class."""
        os.environ["MOCK_MODE"] = "1"
        os.environ["DATABASE_URL"] = "sqlite:///./test_token_validation.db"

        from sqlalchemy import create_engine
        from src.db.models import Base

        engine = create_engine(
            "sqlite:///./test_token_validation.db",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        yield engine
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

        import pathlib
        pathlib.Path("test_token_validation.db").unlink(missing_ok=True)

    @pytest.fixture
    def test_client(self, setup_database):
        """Create test client."""
        from sqlalchemy.orm import sessionmaker
        from fastapi.testclient import TestClient
        from src.server import app, get_db

        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=setup_database
        )

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            yield client

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_validate_access_token_valid(self):
        """Test validate_access_token with valid token."""
        from src.auth.shopify import validate_access_token

        # Mock httpx response for valid token
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await validate_access_token(
                "test-store.myshopify.com",
                "shpat_valid_token"
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_access_token_invalid(self):
        """Test validate_access_token with invalid/revoked token."""
        from src.auth.shopify import validate_access_token

        # Mock httpx response for invalid token
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401  # Unauthorized

            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await validate_access_token(
                "test-store.myshopify.com",
                "shpat_invalid_token"
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_validate_access_token_empty_inputs(self):
        """Test validate_access_token with empty inputs."""
        from src.auth.shopify import validate_access_token

        assert await validate_access_token("", "token") is False
        assert await validate_access_token("shop.myshopify.com", "") is False
        assert await validate_access_token(None, "token") is False
        assert await validate_access_token("shop.myshopify.com", None) is False

    @pytest.mark.asyncio
    async def test_validate_access_token_invalid_domain(self):
        """Test validate_access_token with invalid shop domain."""
        from src.auth.shopify import validate_access_token

        # Invalid domain format should return False without making request
        result = await validate_access_token("not-a-shopify-domain.com", "token")
        assert result is False

    def test_invalid_token_blocks_api_access(self, test_client, setup_database):
        """Test that customers with invalid tokens are blocked."""
        from sqlalchemy.orm import sessionmaker
        from src.db.repository import CustomerRepository

        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=setup_database
        )
        db = TestingSessionLocal()
        customer_repo = CustomerRepository(db)

        # Create customer with invalid token flag
        customer = customer_repo.create({
            "shop_domain": "invalid-token-test.myshopify.com",
            "name": "Invalid Token Store",
            "email": "test@test.com",
            "token_invalid": 1,  # Mark as invalid
        })
        db.commit()
        customer_id = str(customer.id)
        db.close()

        # Try to access API - should be blocked
        response = test_client.get(
            "/api/me",
            headers={"X-Customer-ID": customer_id},
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        assert detail["code"] == "SHOPIFY_TOKEN_INVALID"
        assert "reconnect" in detail["error"].lower()

    def test_reconnect_flow_clears_invalid_flag(self, test_client, setup_database):
        """Test that OAuth callback clears the invalid token flag."""
        from sqlalchemy.orm import sessionmaker
        from src.db.repository import CustomerRepository

        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=setup_database
        )
        db = TestingSessionLocal()
        customer_repo = CustomerRepository(db)

        # Create customer with invalid token flag
        customer = customer_repo.create({
            "shop_domain": "reconnect-test.myshopify.com",
            "name": "Reconnect Test Store",
            "email": "test@test.com",
            "token_invalid": 1,
            "shopify_nonce": "test-nonce-123",  # Set nonce for OAuth callback
        })
        db.commit()
        customer_id = str(customer.id)
        db.close()

        # Mark token valid (simulating successful OAuth callback)
        db = TestingSessionLocal()
        customer_repo = CustomerRepository(db)
        customer_repo.mark_token_valid(customer.id)
        db.close()

        # Now should be able to access API
        response = test_client.get(
            "/api/me",
            headers={"X-Customer-ID": customer_id},
        )
        assert response.status_code == 200

    def test_reconnect_endpoint_redirects(self, test_client, setup_database):
        """Test that reconnect endpoint redirects to Shopify OAuth."""
        from sqlalchemy.orm import sessionmaker
        from src.db.repository import CustomerRepository

        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=setup_database
        )
        db = TestingSessionLocal()
        customer_repo = CustomerRepository(db)

        # Create customer (even with invalid token, reconnect should work)
        customer = customer_repo.create({
            "shop_domain": "reconnect-redirect.myshopify.com",
            "name": "Reconnect Redirect Store",
            "email": "test@test.com",
            "token_invalid": 1,
        })
        db.commit()
        customer_id = str(customer.id)
        db.close()

        # Hit reconnect endpoint
        response = test_client.get(
            "/api/shopify/reconnect",
            headers={"X-Customer-ID": customer_id},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "myshopify.com" in response.headers["location"]
        assert "oauth/authorize" in response.headers["location"]

    def test_repository_mark_token_invalid(self, setup_database):
        """Test CustomerRepository.mark_token_invalid method."""
        from sqlalchemy.orm import sessionmaker
        from src.db.repository import CustomerRepository

        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=setup_database
        )
        db = TestingSessionLocal()
        customer_repo = CustomerRepository(db)

        # Create customer
        customer = customer_repo.create({
            "shop_domain": "mark-invalid-test.myshopify.com",
            "name": "Mark Invalid Test",
            "email": "test@test.com",
        })
        db.commit()

        # Initially should be valid (0)
        assert customer.token_invalid == 0

        # Mark as invalid
        customer_repo.mark_token_invalid(customer.id)

        # Refresh and check
        db.refresh(customer)
        assert customer.token_invalid == 1
        db.close()

    def test_repository_mark_token_valid(self, setup_database):
        """Test CustomerRepository.mark_token_valid method."""
        from sqlalchemy.orm import sessionmaker
        from src.db.repository import CustomerRepository

        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=setup_database
        )
        db = TestingSessionLocal()
        customer_repo = CustomerRepository(db)

        # Create customer with invalid token
        customer = customer_repo.create({
            "shop_domain": "mark-valid-test.myshopify.com",
            "name": "Mark Valid Test",
            "email": "test@test.com",
            "token_invalid": 1,
        })
        db.commit()

        # Mark as valid
        customer_repo.mark_token_valid(customer.id)

        # Refresh and check
        db.refresh(customer)
        assert customer.token_invalid == 0
        assert customer.token_validated_at is not None
        db.close()
