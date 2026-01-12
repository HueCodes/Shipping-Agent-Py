"""SQLAlchemy models for shipping agent."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import JSON


class UUID(TypeDecorator):
    """Platform-independent UUID type.

    Uses PostgreSQL's UUID type when available, otherwise stores as CHAR(32).
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return value
        else:
            if isinstance(value, uuid.UUID):
                return value.hex
            else:
                return uuid.UUID(value).hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Customer(Base):
    """Customer (Shopify store) model."""

    __tablename__ = "customers"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    shop_domain = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    plan_tier = Column(String(50), default="free")
    labels_this_month = Column(Integer, default=0)
    labels_limit = Column(Integer, default=50)
    easypost_api_key = Column(Text)
    default_from_address = Column(JSON)

    # Shopify OAuth fields
    shopify_access_token = Column(Text)  # Encrypted access token
    shopify_nonce = Column(String(64))  # CSRF protection for OAuth flow
    shopify_scope = Column(Text)  # Granted OAuth scopes
    installed_at = Column(DateTime)  # When app was installed
    uninstalled_at = Column(DateTime)  # When app was uninstalled (soft delete)

    # Token validation fields
    token_validated_at = Column(DateTime)  # Last time token was verified with Shopify
    token_invalid = Column(Integer, default=0)  # Flag for invalid/revoked tokens (0=valid, 1=invalid)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan")
    shipments = relationship("Shipment", back_populates="customer", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Customer {self.name} ({self.shop_domain})>"


class Order(Base):
    """Order model (synced from Shopify)."""

    __tablename__ = "orders"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    shopify_order_id = Column(String(100), nullable=False)
    order_number = Column(String(100))
    recipient_name = Column(String(255))
    status = Column(String(50), default="unfulfilled")
    shipping_address = Column(JSON)
    line_items = Column(JSON)
    weight_oz = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint on customer_id + shopify_order_id
    __table_args__ = (
        UniqueConstraint("customer_id", "shopify_order_id", name="uq_customer_order"),
    )

    # Relationships
    customer = relationship("Customer", back_populates="orders")
    shipment = relationship("Shipment", back_populates="order", uselist=False)

    def __repr__(self) -> str:
        return f"<Order {self.order_number} - {self.recipient_name}>"


class Shipment(Base):
    """Shipment model."""

    __tablename__ = "shipments"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(UUID(), ForeignKey("orders.id", ondelete="SET NULL"))
    easypost_shipment_id = Column(String(255))
    carrier = Column(String(100), nullable=False)
    service = Column(String(100), nullable=False)
    tracking_number = Column(String(255))
    label_url = Column(Text)
    rate_amount = Column(Float)
    status = Column(String(50), default="created")
    estimated_delivery = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    customer = relationship("Customer", back_populates="shipments")
    order = relationship("Order", back_populates="shipment")
    tracking_events = relationship("TrackingEvent", back_populates="shipment", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Shipment {self.tracking_number} - {self.carrier}>"


class Conversation(Base):
    """Conversation model (agent chat history)."""

    __tablename__ = "conversations"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, unique=True)
    messages = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer = relationship("Customer", back_populates="conversations")

    def __repr__(self) -> str:
        msg_count = len(self.messages) if self.messages else 0
        return f"<Conversation {self.id} - {msg_count} messages>"


class TrackingEvent(Base):
    """Tracking event model."""

    __tablename__ = "tracking_events"

    id = Column(UUID(), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(UUID(), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(100), nullable=False)
    description = Column(Text)
    location = Column(JSON)
    occurred_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    shipment = relationship("Shipment", back_populates="tracking_events")

    def __repr__(self) -> str:
        return f"<TrackingEvent {self.status} at {self.occurred_at}>"
