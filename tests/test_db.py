"""Tests for database layer."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Base, Customer, Order, Shipment, Conversation, TrackingEvent
from src.db.repository import (
    CustomerRepository,
    OrderRepository,
    ShipmentRepository,
    ConversationRepository,
)


@pytest.fixture
def db_engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    """Create database session for testing."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def customer_repo(db_session):
    """Create customer repository."""
    return CustomerRepository(db_session)


@pytest.fixture
def order_repo(db_session):
    """Create order repository."""
    return OrderRepository(db_session)


@pytest.fixture
def shipment_repo(db_session):
    """Create shipment repository."""
    return ShipmentRepository(db_session)


@pytest.fixture
def conversation_repo(db_session):
    """Create conversation repository."""
    return ConversationRepository(db_session)


@pytest.fixture
def sample_customer(customer_repo):
    """Create a sample customer for testing."""
    return customer_repo.create({
        "shop_domain": "test-store.myshopify.com",
        "name": "Test Store",
        "email": "test@example.com",
        "plan_tier": "starter",
        "labels_this_month": 10,
        "labels_limit": 500,
    })


@pytest.fixture
def sample_order(order_repo, sample_customer):
    """Create a sample order for testing."""
    return order_repo.create({
        "customer_id": sample_customer.id,
        "shopify_order_id": "ORDER-123",
        "order_number": "#1001",
        "recipient_name": "John Doe",
        "shipping_address": {
            "street1": "123 Main St",
            "city": "Los Angeles",
            "state": "CA",
            "zip": "90001",
        },
        "line_items": [
            {"name": "Widget", "quantity": 2},
        ],
        "weight_oz": 24,
        "status": "unfulfilled",
    })


class TestCustomerRepository:
    """Tests for CustomerRepository."""

    def test_create_customer(self, customer_repo):
        """Test creating a new customer."""
        customer = customer_repo.create({
            "shop_domain": "new-store.myshopify.com",
            "name": "New Store",
            "plan_tier": "free",
        })

        assert customer.id is not None
        assert customer.shop_domain == "new-store.myshopify.com"
        assert customer.name == "New Store"
        assert customer.plan_tier == "free"
        assert customer.labels_this_month == 0

    def test_get_by_id(self, customer_repo, sample_customer):
        """Test getting customer by ID."""
        found = customer_repo.get_by_id(sample_customer.id)
        assert found is not None
        assert found.id == sample_customer.id
        assert found.name == sample_customer.name

    def test_get_by_id_not_found(self, customer_repo):
        """Test getting non-existent customer."""
        found = customer_repo.get_by_id(uuid.uuid4())
        assert found is None

    def test_get_by_shop_domain(self, customer_repo, sample_customer):
        """Test getting customer by shop domain."""
        found = customer_repo.get_by_shop_domain("test-store.myshopify.com")
        assert found is not None
        assert found.id == sample_customer.id

    def test_update_label_count(self, customer_repo, sample_customer):
        """Test updating label count."""
        customer_repo.update_label_count(sample_customer.id, 50)

        found = customer_repo.get_by_id(sample_customer.id)
        assert found.labels_this_month == 50

    def test_increment_label_count(self, customer_repo, sample_customer):
        """Test incrementing label count."""
        initial_count = sample_customer.labels_this_month
        customer_repo.increment_label_count(sample_customer.id, 5)

        found = customer_repo.get_by_id(sample_customer.id)
        assert found.labels_this_month == initial_count + 5


class TestOrderRepository:
    """Tests for OrderRepository."""

    def test_create_order(self, order_repo, sample_customer):
        """Test creating a new order."""
        order = order_repo.create({
            "customer_id": sample_customer.id,
            "shopify_order_id": "ORDER-456",
            "order_number": "#1002",
            "recipient_name": "Jane Smith",
            "weight_oz": 16,
        })

        assert order.id is not None
        assert order.shopify_order_id == "ORDER-456"
        assert order.status == "unfulfilled"

    def test_get_by_id(self, order_repo, sample_order):
        """Test getting order by ID."""
        found = order_repo.get_by_id(sample_order.id)
        assert found is not None
        assert found.recipient_name == "John Doe"

    def test_get_by_shopify_id(self, order_repo, sample_customer, sample_order):
        """Test getting order by Shopify order ID."""
        found = order_repo.get_by_shopify_id(sample_customer.id, "ORDER-123")
        assert found is not None
        assert found.id == sample_order.id

    def test_list_unfulfilled(self, order_repo, sample_customer):
        """Test listing unfulfilled orders."""
        # Create multiple orders
        order_repo.create({
            "customer_id": sample_customer.id,
            "shopify_order_id": "ORDER-001",
            "order_number": "#1",
            "recipient_name": "Alice",
            "status": "unfulfilled",
        })
        order_repo.create({
            "customer_id": sample_customer.id,
            "shopify_order_id": "ORDER-002",
            "order_number": "#2",
            "recipient_name": "Bob",
            "status": "shipped",
        })
        order_repo.create({
            "customer_id": sample_customer.id,
            "shopify_order_id": "ORDER-003",
            "order_number": "#3",
            "recipient_name": "Charlie",
            "status": "unfulfilled",
        })

        unfulfilled = order_repo.list_unfulfilled(sample_customer.id)
        assert len(unfulfilled) == 2
        names = [o.recipient_name for o in unfulfilled]
        assert "Alice" in names
        assert "Charlie" in names
        assert "Bob" not in names

    def test_list_unfulfilled_with_search(self, order_repo, sample_customer):
        """Test searching unfulfilled orders."""
        order_repo.create({
            "customer_id": sample_customer.id,
            "shopify_order_id": "ORDER-A",
            "order_number": "#100",
            "recipient_name": "Alice Johnson",
            "status": "unfulfilled",
        })
        order_repo.create({
            "customer_id": sample_customer.id,
            "shopify_order_id": "ORDER-B",
            "order_number": "#101",
            "recipient_name": "Bob Smith",
            "status": "unfulfilled",
        })

        # Search by name
        results = order_repo.list_unfulfilled(sample_customer.id, search="alice")
        assert len(results) == 1
        assert results[0].recipient_name == "Alice Johnson"

        # Search by order number
        results = order_repo.list_unfulfilled(sample_customer.id, search="101")
        assert len(results) == 1
        assert results[0].recipient_name == "Bob Smith"

    def test_update_status(self, order_repo, sample_order):
        """Test updating order status."""
        order_repo.update_status(sample_order.id, "shipped")

        found = order_repo.get_by_id(sample_order.id)
        assert found.status == "shipped"

    def test_list_unfulfilled_with_limit(self, order_repo, sample_customer):
        """Test limiting unfulfilled orders."""
        for i in range(5):
            order_repo.create({
                "customer_id": sample_customer.id,
                "shopify_order_id": f"ORDER-{i}",
                "order_number": f"#{i}",
                "recipient_name": f"Customer {i}",
                "status": "unfulfilled",
            })

        results = order_repo.list_unfulfilled(sample_customer.id, limit=3)
        assert len(results) == 3


class TestShipmentRepository:
    """Tests for ShipmentRepository."""

    def test_create_shipment(self, shipment_repo, sample_customer, sample_order):
        """Test creating a shipment."""
        shipment = shipment_repo.create({
            "customer_id": sample_customer.id,
            "order_id": sample_order.id,
            "carrier": "USPS",
            "service": "Priority",
            "tracking_number": "9400111899223385748672",
            "rate_amount": 8.50,
            "label_url": "https://example.com/label.pdf",
        })

        assert shipment.id is not None
        assert shipment.tracking_number == "9400111899223385748672"
        assert shipment.carrier == "USPS"
        assert shipment.status == "created"

    def test_get_by_order_id(self, shipment_repo, sample_customer, sample_order):
        """Test getting shipment by order ID."""
        shipment_repo.create({
            "customer_id": sample_customer.id,
            "order_id": sample_order.id,
            "carrier": "UPS",
            "service": "Ground",
            "tracking_number": "1Z999AA10123456784",
        })

        found = shipment_repo.get_by_order_id(sample_order.id)
        assert found is not None
        assert found.carrier == "UPS"

    def test_get_by_tracking_number(self, shipment_repo, sample_customer):
        """Test getting shipment by tracking number."""
        tracking = "1Z999AA10123456784"
        shipment_repo.create({
            "customer_id": sample_customer.id,
            "carrier": "UPS",
            "service": "Ground",
            "tracking_number": tracking,
        })

        found = shipment_repo.get_by_tracking_number(tracking)
        assert found is not None
        assert found.tracking_number == tracking

    def test_list_by_customer(self, shipment_repo, sample_customer):
        """Test listing shipments for a customer."""
        for i in range(3):
            shipment_repo.create({
                "customer_id": sample_customer.id,
                "carrier": "USPS",
                "service": "Priority",
                "tracking_number": f"940011189922338574867{i}",
            })

        shipments = shipment_repo.list_by_customer(sample_customer.id)
        assert len(shipments) == 3


class TestConversationRepository:
    """Tests for ConversationRepository."""

    def test_get_or_create_new(self, conversation_repo, sample_customer):
        """Test creating a new conversation."""
        conversation = conversation_repo.get_or_create(sample_customer.id)

        assert conversation.id is not None
        assert conversation.customer_id == sample_customer.id
        assert conversation.messages == []

    def test_get_or_create_existing(self, conversation_repo, sample_customer):
        """Test getting existing conversation."""
        # Create first
        conv1 = conversation_repo.get_or_create(sample_customer.id)

        # Get again - should be same
        conv2 = conversation_repo.get_or_create(sample_customer.id)

        assert conv1.id == conv2.id

    def test_append_message(self, conversation_repo, sample_customer):
        """Test appending messages to conversation."""
        conversation = conversation_repo.get_or_create(sample_customer.id)

        conversation_repo.append_message(conversation.id, {
            "role": "user",
            "content": "Hello",
        })
        conversation_repo.append_message(conversation.id, {
            "role": "assistant",
            "content": "Hi there!",
        })

        messages = conversation_repo.get_messages(conversation.id)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_get_messages_with_limit(self, conversation_repo, sample_customer):
        """Test getting limited messages."""
        conversation = conversation_repo.get_or_create(sample_customer.id)

        for i in range(10):
            conversation_repo.append_message(conversation.id, {
                "role": "user",
                "content": f"Message {i}",
            })

        messages = conversation_repo.get_messages(conversation.id, limit=3)
        assert len(messages) == 3
        # Should get last 3 messages
        assert "Message 7" in messages[0]["content"]

    def test_clear_messages(self, conversation_repo, sample_customer):
        """Test clearing conversation messages."""
        conversation = conversation_repo.get_or_create(sample_customer.id)

        conversation_repo.append_message(conversation.id, {
            "role": "user",
            "content": "Hello",
        })

        conversation_repo.clear_messages(conversation.id)

        messages = conversation_repo.get_messages(conversation.id)
        assert len(messages) == 0

    def test_set_messages(self, conversation_repo, sample_customer):
        """Test replacing all messages."""
        conversation = conversation_repo.get_or_create(sample_customer.id)

        # Add initial messages
        conversation_repo.append_message(conversation.id, {"role": "user", "content": "Old"})

        # Replace with new messages
        new_messages = [
            {"role": "user", "content": "New 1"},
            {"role": "assistant", "content": "New 2"},
        ]
        conversation_repo.set_messages(conversation.id, new_messages)

        messages = conversation_repo.get_messages(conversation.id)
        assert len(messages) == 2
        assert messages[0]["content"] == "New 1"


class TestShipmentOrderIntegration:
    """Integration tests for shipment-order interactions."""

    def test_shipment_updates_order_status(self, order_repo, shipment_repo, sample_customer, sample_order):
        """Test that creating a shipment can update order status."""
        assert sample_order.status == "unfulfilled"

        # Create shipment
        shipment = shipment_repo.create({
            "customer_id": sample_customer.id,
            "order_id": sample_order.id,
            "carrier": "USPS",
            "service": "Priority",
            "tracking_number": "9400111899223385748672",
        })

        # Manually update order status (as the tool would)
        order_repo.update_status(sample_order.id, "shipped")

        # Verify
        order = order_repo.get_by_id(sample_order.id)
        assert order.status == "shipped"

        # Verify shipment is linked
        found_shipment = shipment_repo.get_by_order_id(sample_order.id)
        assert found_shipment.id == shipment.id

    def test_shipment_increments_label_count(self, customer_repo, shipment_repo, sample_customer):
        """Test that creating a shipment increments label count."""
        initial_count = sample_customer.labels_this_month

        # Create shipment
        shipment_repo.create({
            "customer_id": sample_customer.id,
            "carrier": "USPS",
            "service": "Priority",
            "tracking_number": "9400111899223385748672",
        })

        # Increment label count (as the tool would)
        customer_repo.increment_label_count(sample_customer.id)

        # Verify
        customer = customer_repo.get_by_id(sample_customer.id)
        assert customer.labels_this_month == initial_count + 1
