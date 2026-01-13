"""Shared fixtures for integration tests."""

import os

# Set environment BEFORE any imports from src
os.environ["MOCK_MODE"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///./test_integration.db"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from src.db.models import Base, Customer, Order
from src.db.repository import CustomerRepository, OrderRepository, ConversationRepository


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Set up test database once for the entire test session."""
    # Create the test database
    engine = create_engine(
        "sqlite:///./test_integration.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    # Cleanup after all tests
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    # Remove the test database file
    import pathlib
    pathlib.Path("test_integration.db").unlink(missing_ok=True)


@pytest.fixture(scope="function")
def db_engine(setup_test_database):
    """Get the test database engine."""
    return setup_test_database


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create database session for testing."""
    from src.db.models import Customer, Order, Shipment, Conversation, TrackingEvent

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()

    # Clean up any existing data before each test
    session.query(TrackingEvent).delete()
    session.query(Shipment).delete()
    session.query(Order).delete()
    session.query(Conversation).delete()
    session.query(Customer).delete()
    session.commit()

    yield session

    # Clean up data after each test
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def test_client(db_session):
    """Create FastAPI TestClient with test database."""
    # Import here to ensure DATABASE_URL is set
    from src.server import app
    from src.api.deps import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def customer_repo(db_session):
    """Create customer repository."""
    return CustomerRepository(db_session)


@pytest.fixture
def order_repo(db_session):
    """Create order repository."""
    return OrderRepository(db_session)


@pytest.fixture
def conversation_repo(db_session):
    """Create conversation repository."""
    return ConversationRepository(db_session)


@pytest.fixture
def sample_customer(customer_repo) -> Customer:
    """Create a sample customer for testing."""
    return customer_repo.create({
        "shop_domain": "integration-test.myshopify.com",
        "name": "Integration Test Store",
        "email": "test@integration.com",
        "plan_tier": "starter",
        "labels_this_month": 5,
        "labels_limit": 250,
    })


@pytest.fixture
def sample_orders(order_repo, sample_customer) -> list[Order]:
    """Create sample orders for testing."""
    orders = []

    # Order 1: Ready to ship
    orders.append(order_repo.create({
        "customer_id": sample_customer.id,
        "shopify_order_id": "SHOP-1001",
        "order_number": "#1001",
        "recipient_name": "Alice Johnson",
        "shipping_address": {
            "street1": "123 Main Street",
            "city": "Los Angeles",
            "state": "CA",
            "zip": "90001",
            "country": "US",
        },
        "line_items": [
            {"name": "Blue Widget", "quantity": 2, "price": 29.99},
            {"name": "Red Gadget", "quantity": 1, "price": 49.99},
        ],
        "weight_oz": 32,
        "status": "unfulfilled",
    }))

    # Order 2: Another unfulfilled order
    orders.append(order_repo.create({
        "customer_id": sample_customer.id,
        "shopify_order_id": "SHOP-1002",
        "order_number": "#1002",
        "recipient_name": "Bob Smith",
        "shipping_address": {
            "street1": "456 Oak Avenue",
            "city": "Chicago",
            "state": "IL",
            "zip": "60601",
            "country": "US",
        },
        "line_items": [
            {"name": "Green Thing", "quantity": 3, "price": 19.99},
        ],
        "weight_oz": 16,
        "status": "unfulfilled",
    }))

    # Order 3: Already shipped
    orders.append(order_repo.create({
        "customer_id": sample_customer.id,
        "shopify_order_id": "SHOP-1003",
        "order_number": "#1003",
        "recipient_name": "Carol White",
        "shipping_address": {
            "street1": "789 Pine Road",
            "city": "Miami",
            "state": "FL",
            "zip": "33101",
            "country": "US",
        },
        "line_items": [
            {"name": "Yellow Item", "quantity": 1, "price": 99.99},
        ],
        "weight_oz": 48,
        "status": "shipped",
    }))

    return orders


@pytest.fixture
def auth_headers(sample_customer) -> dict:
    """Create authentication headers with customer ID."""
    return {"X-Customer-ID": str(sample_customer.id)}


class ChatHelper:
    """Helper class for chat interactions in tests."""

    def __init__(self, client: TestClient, session_id: str = "test-session"):
        self.client = client
        self.session_id = session_id
        self.headers = {}

    def with_auth(self, customer_id: str) -> "ChatHelper":
        """Set authentication header."""
        self.headers["X-Customer-ID"] = customer_id
        return self

    def send(self, message: str) -> dict:
        """Send a chat message and return the response."""
        response = self.client.post(
            "/api/chat",
            json={"message": message, "session_id": self.session_id},
            headers=self.headers,
        )
        return response.json() if response.status_code == 200 else {"error": response.json()}

    def reset(self) -> None:
        """Reset the chat session."""
        self.client.post(
            f"/api/reset?session_id={self.session_id}",
            headers=self.headers,
        )


@pytest.fixture
def chat_helper(test_client) -> ChatHelper:
    """Create a chat helper for testing conversations."""
    return ChatHelper(test_client)


@pytest.fixture
def authenticated_chat(test_client, sample_customer) -> ChatHelper:
    """Create an authenticated chat helper."""
    helper = ChatHelper(test_client, session_id=f"test-{sample_customer.id}")
    helper.with_auth(str(sample_customer.id))
    return helper
