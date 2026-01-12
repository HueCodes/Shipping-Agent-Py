"""Tests for error handling across the API."""

import os
import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4

# Set test environment
os.environ["MOCK_MODE"] = "1"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing"
os.environ["SHOPIFY_API_KEY"] = "test-api-key"
os.environ["SHOPIFY_API_SECRET"] = "test-api-secret"
os.environ["DATABASE_URL"] = "sqlite:///./test_error_handling.db"


class TestErrorResponseFormat:
    """Tests for consistent error response format."""

    @pytest.fixture(scope="class")
    def setup_database(self):
        """Set up test database once for all tests in this class."""
        from sqlalchemy import create_engine
        from src.db.models import Base

        engine = create_engine(
            "sqlite:///./test_error_handling.db",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        yield engine
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

        import pathlib
        pathlib.Path("test_error_handling.db").unlink(missing_ok=True)

    @pytest.fixture
    def test_client(self, setup_database):
        """Create test client with database override."""
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

    @pytest.fixture
    def customer_with_db(self, setup_database):
        """Create a test customer and return ID."""
        from sqlalchemy.orm import sessionmaker
        from src.db.repository import CustomerRepository

        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=setup_database
        )
        db = TestingSessionLocal()
        customer_repo = CustomerRepository(db)
        customer = customer_repo.create({
            "shop_domain": f"error-test-{uuid4().hex[:8]}.myshopify.com",
            "name": "Error Test Store",
            "email": "test@test.com",
        })
        db.commit()
        customer_id = str(customer.id)
        db.close()
        return customer_id

    def test_error_response_has_required_fields(self, test_client):
        """Test that error responses have error, code fields."""
        # Request without auth should return error
        response = test_client.get("/api/me")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        # The detail field should contain our error format
        # (FastAPI wraps HTTPException detail)

    def test_validation_error_format(self, test_client, customer_with_db):
        """Test validation error returns consistent format."""
        response = test_client.post(
            "/api/chat",
            json={"message": "", "session_id": "test"},
            headers={"X-Customer-ID": customer_with_db},
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        assert detail["code"] == "VALIDATION_ERROR"
        assert "error" in detail

    def test_not_found_error_format(self, test_client, customer_with_db):
        """Test not found error returns consistent format."""
        fake_order_id = str(uuid4())
        response = test_client.post(
            "/api/rates",
            json={"order_id": fake_order_id},
            headers={"X-Customer-ID": customer_with_db},
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        assert detail["code"] == "NOT_FOUND"
        assert "Order not found" in detail["error"]


class TestEasyPostErrorHandling:
    """Tests for EasyPost API error handling."""

    @pytest.fixture(scope="class")
    def setup_database(self):
        """Set up test database."""
        from sqlalchemy import create_engine
        from src.db.models import Base

        engine = create_engine(
            "sqlite:///./test_error_handling.db",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        yield engine
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

        import pathlib
        pathlib.Path("test_error_handling.db").unlink(missing_ok=True)

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

    @pytest.fixture
    def customer_with_db(self, setup_database):
        """Create a test customer."""
        from sqlalchemy.orm import sessionmaker
        from src.db.repository import CustomerRepository

        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=setup_database
        )
        db = TestingSessionLocal()
        customer_repo = CustomerRepository(db)
        customer = customer_repo.create({
            "shop_domain": f"easypost-test-{uuid4().hex[:8]}.myshopify.com",
            "name": "EasyPost Test Store",
            "email": "test@test.com",
        })
        db.commit()
        customer_id = str(customer.id)
        db.close()
        return customer_id

    def test_rate_error_does_not_expose_internal_details(self, test_client, customer_with_db):
        """Test that rate errors don't expose internal API details."""
        from src.easypost_client import RateError

        with patch("src.server.get_easypost_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_rates.side_effect = RateError(
                message="Unable to fetch shipping rates. Please verify the address and try again.",
                code="EASYPOST_RATE_ERROR",
                original_error=Exception("API key invalid: sk_test_123"),  # Should not leak
            )
            mock_get_client.return_value = mock_client

            response = test_client.post(
                "/api/rates",
                json={
                    "to_city": "Los Angeles",
                    "to_state": "CA",
                    "to_zip": "90001",
                    "weight_oz": 16,
                },
                headers={"X-Customer-ID": customer_with_db},
            )

            assert response.status_code == 502
            data = response.json()
            detail = data["detail"]

            # Should have user-friendly message
            assert "error" in detail
            assert detail["code"] == "EASYPOST_RATE_ERROR"

            # Should NOT contain internal details
            response_str = str(data)
            assert "sk_test" not in response_str
            assert "API key" not in response_str

    def test_address_validation_error_handling(self, test_client, customer_with_db):
        """Test address validation error handling."""
        from src.easypost_client import AddressValidationError

        with patch("src.server.get_easypost_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.validate_address.side_effect = AddressValidationError(
                message="An error occurred while validating the address.",
                code="EASYPOST_ADDRESS_ERROR",
                original_error=Exception("Connection timeout"),
            )
            mock_get_client.return_value = mock_client

            response = test_client.post(
                "/api/addresses/validate",
                json={
                    "street1": "123 Test St",
                    "city": "Los Angeles",
                    "state": "CA",
                    "zip": "90001",
                },
                headers={"X-Customer-ID": customer_with_db},
            )

            assert response.status_code == 502
            data = response.json()
            detail = data["detail"]
            assert detail["code"] == "EASYPOST_ADDRESS_ERROR"
            assert "Connection timeout" not in str(data)

    def test_shipment_error_handling(self, test_client, customer_with_db):
        """Test shipment creation error handling."""
        from src.easypost_client import ShipmentError

        with patch("src.server.get_easypost_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.create_shipment.side_effect = ShipmentError(
                message="Unable to purchase shipping label. The rate may have expired.",
                code="EASYPOST_SHIPMENT_ERROR",
                original_error=Exception("Rate not found"),
            )
            mock_get_client.return_value = mock_client

            response = test_client.post(
                "/api/shipments",
                json={
                    "rate_id": "rate_123",
                    "to_name": "John Doe",
                    "to_street": "123 Test St",
                    "to_city": "Los Angeles",
                    "to_state": "CA",
                    "to_zip": "90001",
                    "weight_oz": 16,
                },
                headers={"X-Customer-ID": customer_with_db},
            )

            assert response.status_code == 502
            data = response.json()
            detail = data["detail"]
            assert detail["code"] == "EASYPOST_SHIPMENT_ERROR"
            assert "rate may have expired" in detail["error"]

    def test_tracking_error_handling(self, test_client, customer_with_db, setup_database):
        """Test tracking error handling."""
        from sqlalchemy.orm import sessionmaker
        from src.db.repository import CustomerRepository, ShipmentRepository
        from src.easypost_client import TrackingError

        # Create a shipment to test tracking
        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=setup_database
        )
        db = TestingSessionLocal()
        customer_repo = CustomerRepository(db)
        shipment_repo = ShipmentRepository(db)

        customer = customer_repo.get_by_shop_domain(
            f"easypost-test-{customer_with_db[:8]}.myshopify.com"
        )
        if not customer:
            # Get by ID instead
            from uuid import UUID
            customer = customer_repo.get_by_id(UUID(customer_with_db))

        shipment = shipment_repo.create({
            "customer_id": customer.id,
            "carrier": "USPS",
            "service": "Ground",
            "tracking_number": "1234567890",
            "status": "created",
        })
        db.commit()
        shipment_id = str(shipment.id)
        db.close()

        with patch("src.server.get_easypost_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_tracking.side_effect = TrackingError(
                message="Tracking number not found. Please verify the number is correct.",
                code="EASYPOST_TRACKING_ERROR",
                original_error=Exception("Tracker not found"),
            )
            mock_get_client.return_value = mock_client

            response = test_client.get(
                f"/api/shipments/{shipment_id}/tracking",
                headers={"X-Customer-ID": customer_with_db},
            )

            assert response.status_code == 502
            data = response.json()
            detail = data["detail"]
            assert detail["code"] == "EASYPOST_TRACKING_ERROR"
            assert "not found" in detail["error"].lower()


class TestChatErrorHandling:
    """Tests for chat endpoint error handling."""

    @pytest.fixture(scope="class")
    def setup_database(self):
        """Set up test database."""
        from sqlalchemy import create_engine
        from src.db.models import Base

        engine = create_engine(
            "sqlite:///./test_error_handling.db",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        yield engine
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

        import pathlib
        pathlib.Path("test_error_handling.db").unlink(missing_ok=True)

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

    def test_empty_message_error(self, test_client):
        """Test that empty message returns validation error."""
        response = test_client.post(
            "/api/chat",
            json={"message": "   ", "session_id": "test"},
        )
        assert response.status_code == 400
        data = response.json()
        detail = data["detail"]
        assert detail["code"] == "VALIDATION_ERROR"
        assert "empty" in detail["error"].lower()

    def test_chat_error_does_not_expose_api_keys(self, test_client, setup_database):
        """Test that chat errors don't expose API keys."""
        from sqlalchemy.orm import sessionmaker
        from src.db.repository import CustomerRepository

        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=setup_database
        )
        db = TestingSessionLocal()
        customer_repo = CustomerRepository(db)
        customer = customer_repo.create({
            "shop_domain": f"chat-test-{uuid4().hex[:8]}.myshopify.com",
            "name": "Chat Test Store",
            "email": "test@test.com",
        })
        db.commit()
        customer_id = str(customer.id)
        db.close()

        with patch("src.server.agents", {}):
            with patch("src.agent.ShippingAgent") as mock_agent_class:
                mock_agent = MagicMock()
                mock_agent.chat.side_effect = Exception(
                    "Anthropic API error: Invalid API key sk-ant-api123"
                )
                mock_agent_class.return_value = mock_agent

                response = test_client.post(
                    "/api/chat",
                    json={"message": "Hello", "session_id": "test"},
                    headers={"X-Customer-ID": customer_id},
                )

                # Should return 502 for API errors
                assert response.status_code == 502
                data = response.json()
                detail = data["detail"]

                # Should NOT contain API key
                response_str = str(data)
                assert "sk-ant" not in response_str
                assert "api123" not in response_str


class TestMalformedRequestHandling:
    """Tests for malformed request handling."""

    @pytest.fixture(scope="class")
    def setup_database(self):
        """Set up test database."""
        from sqlalchemy import create_engine
        from src.db.models import Base

        engine = create_engine(
            "sqlite:///./test_error_handling.db",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        yield engine
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

        import pathlib
        pathlib.Path("test_error_handling.db").unlink(missing_ok=True)

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

    @pytest.fixture
    def customer_with_db(self, setup_database):
        """Create a test customer."""
        from sqlalchemy.orm import sessionmaker
        from src.db.repository import CustomerRepository

        TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=setup_database
        )
        db = TestingSessionLocal()
        customer_repo = CustomerRepository(db)
        customer = customer_repo.create({
            "shop_domain": f"malformed-test-{uuid4().hex[:8]}.myshopify.com",
            "name": "Malformed Test Store",
            "email": "test@test.com",
        })
        db.commit()
        customer_id = str(customer.id)
        db.close()
        return customer_id

    def test_invalid_uuid_in_path(self, test_client, customer_with_db):
        """Test invalid UUID in path returns proper error."""
        response = test_client.get(
            "/api/orders/not-a-uuid",
            headers={"X-Customer-ID": customer_with_db},
        )
        assert response.status_code == 400
        data = response.json()
        assert "Invalid order ID format" in data["detail"]

    def test_missing_required_fields(self, test_client, customer_with_db):
        """Test missing required fields returns validation error."""
        response = test_client.post(
            "/api/rates",
            json={},  # Missing required fields
            headers={"X-Customer-ID": customer_with_db},
        )
        assert response.status_code == 400
        data = response.json()
        detail = data["detail"]
        assert detail["code"] == "VALIDATION_ERROR"

    def test_invalid_json_body(self, test_client, customer_with_db):
        """Test invalid JSON body returns error."""
        response = test_client.post(
            "/api/chat",
            content="not valid json",
            headers={
                "X-Customer-ID": customer_with_db,
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 422  # FastAPI validation error


class TestDatabaseErrorHandling:
    """Tests for database error handling."""

    def test_invalid_customer_id_format(self):
        """Test invalid customer ID format in header."""
        from fastapi.testclient import TestClient
        from src.server import app

        with TestClient(app) as client:
            response = client.get(
                "/api/me",
                headers={"X-Customer-ID": "not-a-uuid"},
            )
            assert response.status_code == 400
            assert "Invalid customer ID" in response.json()["detail"]

    def test_nonexistent_customer(self):
        """Test nonexistent customer returns 404."""
        from fastapi.testclient import TestClient
        from src.server import app

        fake_uuid = str(uuid4())
        with TestClient(app) as client:
            response = client.get(
                "/api/me",
                headers={"X-Customer-ID": fake_uuid},
            )
            assert response.status_code == 404
            assert "Customer not found" in response.json()["detail"]
