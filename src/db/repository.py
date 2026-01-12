"""Repository classes for data access."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.db.models import Customer, Order, Shipment, Conversation, TrackingEvent


class CustomerRepository:
    """Repository for customer data access."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, id: UUID) -> Customer | None:
        """Get customer by ID."""
        return self.db.query(Customer).filter(Customer.id == id).first()

    def get_by_shop_domain(self, domain: str) -> Customer | None:
        """Get customer by Shopify shop domain."""
        return self.db.query(Customer).filter(Customer.shop_domain == domain).first()

    def create(self, data: dict[str, Any]) -> Customer:
        """Create a new customer."""
        customer = Customer(**data)
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def update(self, id: UUID, data: dict[str, Any]) -> Customer | None:
        """Update customer fields."""
        customer = self.get_by_id(id)
        if customer:
            for key, value in data.items():
                setattr(customer, key, value)
            customer.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(customer)
        return customer

    def update_label_count(self, id: UUID, count: int) -> None:
        """Update labels_this_month count."""
        customer = self.get_by_id(id)
        if customer:
            customer.labels_this_month = count
            customer.updated_at = datetime.utcnow()
            self.db.commit()

    def increment_label_count(self, id: UUID, increment: int = 1) -> None:
        """Increment labels_this_month count."""
        customer = self.get_by_id(id)
        if customer:
            customer.labels_this_month += increment
            customer.updated_at = datetime.utcnow()
            self.db.commit()

    def list_all(self, limit: int = 100) -> list[Customer]:
        """List all customers."""
        return self.db.query(Customer).limit(limit).all()

    def mark_token_invalid(self, id: UUID) -> None:
        """Mark a customer's Shopify token as invalid."""
        customer = self.get_by_id(id)
        if customer:
            customer.token_invalid = 1
            customer.updated_at = datetime.utcnow()
            self.db.commit()

    def mark_token_valid(self, id: UUID) -> None:
        """Mark a customer's Shopify token as valid and update validated timestamp."""
        customer = self.get_by_id(id)
        if customer:
            customer.token_invalid = 0
            customer.token_validated_at = datetime.utcnow()
            customer.updated_at = datetime.utcnow()
            self.db.commit()

    def update_token_validated_at(self, id: UUID) -> None:
        """Update the token_validated_at timestamp."""
        customer = self.get_by_id(id)
        if customer:
            customer.token_validated_at = datetime.utcnow()
            customer.updated_at = datetime.utcnow()
            self.db.commit()


class OrderRepository:
    """Repository for order data access."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, id: UUID) -> Order | None:
        """Get order by ID."""
        return self.db.query(Order).filter(Order.id == id).first()

    def get_by_shopify_id(self, customer_id: UUID, shopify_order_id: str) -> Order | None:
        """Get order by Shopify order ID for a specific customer."""
        return (
            self.db.query(Order)
            .filter(Order.customer_id == customer_id, Order.shopify_order_id == shopify_order_id)
            .first()
        )

    def list_unfulfilled(
        self,
        customer_id: UUID,
        limit: int = 20,
        search: str | None = None,
    ) -> list[Order]:
        """List unfulfilled orders for a customer."""
        query = self.db.query(Order).filter(
            Order.customer_id == customer_id,
            Order.status == "unfulfilled",
        )

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Order.recipient_name.ilike(search_term),
                    Order.order_number.ilike(search_term),
                    Order.shopify_order_id.ilike(search_term),
                )
            )

        return query.order_by(Order.created_at.desc()).limit(limit).all()

    def list_by_customer(
        self,
        customer_id: UUID,
        limit: int = 50,
        status: str | None = None,
    ) -> list[Order]:
        """List orders for a customer with optional status filter."""
        query = self.db.query(Order).filter(Order.customer_id == customer_id)

        if status:
            query = query.filter(Order.status == status)

        return query.order_by(Order.created_at.desc()).limit(limit).all()

    def create(self, data: dict[str, Any]) -> Order:
        """Create a new order."""
        order = Order(**data)
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def update_status(self, id: UUID, status: str) -> Order | None:
        """Update order status."""
        order = self.get_by_id(id)
        if order:
            order.status = status
            order.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(order)
        return order

    def get_by_ids(self, ids: list[UUID]) -> list[Order]:
        """Get multiple orders by their IDs."""
        return self.db.query(Order).filter(Order.id.in_(ids)).all()


class ShipmentRepository:
    """Repository for shipment data access."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, id: UUID) -> Shipment | None:
        """Get shipment by ID."""
        return self.db.query(Shipment).filter(Shipment.id == id).first()

    def get_by_order_id(self, order_id: UUID) -> Shipment | None:
        """Get shipment by order ID."""
        return self.db.query(Shipment).filter(Shipment.order_id == order_id).first()

    def get_by_tracking_number(self, tracking_number: str) -> Shipment | None:
        """Get shipment by tracking number."""
        return self.db.query(Shipment).filter(Shipment.tracking_number == tracking_number).first()

    def list_by_customer(self, customer_id: UUID, limit: int = 50) -> list[Shipment]:
        """List shipments for a customer."""
        return (
            self.db.query(Shipment)
            .filter(Shipment.customer_id == customer_id)
            .order_by(Shipment.created_at.desc())
            .limit(limit)
            .all()
        )

    def create(self, data: dict[str, Any]) -> Shipment:
        """Create a new shipment."""
        shipment = Shipment(**data)
        self.db.add(shipment)
        self.db.commit()
        self.db.refresh(shipment)
        return shipment

    def update_status(self, id: UUID, status: str) -> Shipment | None:
        """Update shipment status."""
        shipment = self.get_by_id(id)
        if shipment:
            shipment.status = status
            self.db.commit()
            self.db.refresh(shipment)
        return shipment

    def add_tracking_event(
        self,
        shipment_id: UUID,
        status: str,
        description: str | None = None,
        location: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> TrackingEvent:
        """Add a tracking event to a shipment."""
        event = TrackingEvent(
            shipment_id=shipment_id,
            status=status,
            description=description,
            location=location,
            occurred_at=occurred_at or datetime.utcnow(),
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event


class ConversationRepository:
    """Repository for conversation data access."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, id: UUID) -> Conversation | None:
        """Get conversation by ID."""
        return self.db.query(Conversation).filter(Conversation.id == id).first()

    def get_by_customer_id(self, customer_id: UUID) -> Conversation | None:
        """Get conversation for a customer."""
        return self.db.query(Conversation).filter(Conversation.customer_id == customer_id).first()

    def get_or_create(self, customer_id: UUID) -> Conversation:
        """Get existing conversation or create a new one."""
        conversation = self.get_by_customer_id(customer_id)
        if not conversation:
            conversation = Conversation(customer_id=customer_id, messages=[])
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)
        return conversation

    def append_message(self, id: UUID, message: dict[str, Any]) -> None:
        """Append a message to the conversation."""
        conversation = self.get_by_id(id)
        if conversation:
            messages = list(conversation.messages) if conversation.messages else []
            messages.append(message)
            conversation.messages = messages
            conversation.updated_at = datetime.utcnow()
            self.db.commit()

    def get_messages(self, id: UUID, limit: int | None = None) -> list[dict]:
        """Get messages from a conversation."""
        conversation = self.get_by_id(id)
        if not conversation or not conversation.messages:
            return []

        messages = conversation.messages
        if limit:
            return messages[-limit:]
        return messages

    def clear_messages(self, id: UUID) -> None:
        """Clear all messages in a conversation."""
        conversation = self.get_by_id(id)
        if conversation:
            conversation.messages = []
            conversation.updated_at = datetime.utcnow()
            self.db.commit()

    def set_messages(self, id: UUID, messages: list[dict]) -> None:
        """Replace all messages in a conversation."""
        conversation = self.get_by_id(id)
        if conversation:
            conversation.messages = messages
            conversation.updated_at = datetime.utcnow()
            self.db.commit()
