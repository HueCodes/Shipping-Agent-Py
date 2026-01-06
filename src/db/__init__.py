"""Database layer for shipping agent."""

from src.db.database import get_db, get_db_session, engine, SessionLocal, create_tables
from src.db.models import Base, Customer, Order, Shipment, Conversation, TrackingEvent
from src.db.repository import (
    CustomerRepository,
    OrderRepository,
    ShipmentRepository,
    ConversationRepository,
)
from src.db.migrations import run_migrations, get_current_revision

__all__ = [
    # Database
    "get_db",
    "get_db_session",
    "engine",
    "SessionLocal",
    "create_tables",
    # Models
    "Base",
    "Customer",
    "Order",
    "Shipment",
    "Conversation",
    "TrackingEvent",
    # Repositories
    "CustomerRepository",
    "OrderRepository",
    "ShipmentRepository",
    "ConversationRepository",
    # Migrations
    "run_migrations",
    "get_current_revision",
]
