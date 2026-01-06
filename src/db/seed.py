"""Seed script for demo data."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.db.database import get_db_session, engine
from src.db.models import Base, Customer, Order
from src.db.repository import CustomerRepository, OrderRepository
from src.db.migrations import run_migrations
from src.agent.context import PLAN_LIMITS


# Demo customer ID (fixed for consistent testing)
DEMO_CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# Sample orders matching the original MOCK_ORDERS
DEMO_ORDERS = [
    {
        "shopify_order_id": "ORD-1001",
        "order_number": "#1001",
        "recipient_name": "Alice Johnson",
        "shipping_address": {
            "street1": "456 Oak Avenue",
            "city": "Los Angeles",
            "state": "CA",
            "zip": "90001",
        },
        "line_items": [
            {"name": "Widget A", "quantity": 1},
            {"name": "Widget B", "quantity": 1},
        ],
        "weight_oz": 24,
        "days_ago": 3,
    },
    {
        "shopify_order_id": "ORD-1002",
        "order_number": "#1002",
        "recipient_name": "Bob Smith",
        "shipping_address": {
            "street1": "789 Elm Street",
            "city": "Austin",
            "state": "TX",
            "zip": "78701",
        },
        "line_items": [
            {"name": "Gadget Pro", "quantity": 1},
        ],
        "weight_oz": 8,
        "days_ago": 2,
    },
    {
        "shopify_order_id": "ORD-1003",
        "order_number": "#1003",
        "recipient_name": "Carol Williams",
        "shipping_address": {
            "street1": "321 Pine Road",
            "city": "Seattle",
            "state": "WA",
            "zip": "98101",
        },
        "line_items": [
            {"name": "Widget A", "quantity": 2},
            {"name": "Accessory Pack", "quantity": 1},
        ],
        "weight_oz": 48,
        "days_ago": 2,
    },
    {
        "shopify_order_id": "ORD-1004",
        "order_number": "#1004",
        "recipient_name": "David Brown",
        "shipping_address": {
            "street1": "654 Beach Drive",
            "city": "Miami",
            "state": "FL",
            "zip": "33101",
        },
        "line_items": [
            {"name": "Compact Widget", "quantity": 1},
        ],
        "weight_oz": 12,
        "days_ago": 1,
    },
    {
        "shopify_order_id": "ORD-1005",
        "order_number": "#1005",
        "recipient_name": "Eve Martinez",
        "shipping_address": {
            "street1": "987 Mountain View",
            "city": "Denver",
            "state": "CO",
            "zip": "80201",
        },
        "line_items": [
            {"name": "Widget Deluxe", "quantity": 2},
            {"name": "Widget Standard", "quantity": 2},
        ],
        "weight_oz": 64,
        "days_ago": 1,
    },
    {
        "shopify_order_id": "ORD-1006",
        "order_number": "#1006",
        "recipient_name": "Frank Garcia",
        "shipping_address": {
            "street1": "147 Tech Boulevard",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94102",
        },
        "line_items": [
            {"name": "Premium Widget", "quantity": 1},
            {"name": "Carrying Case", "quantity": 1},
        ],
        "weight_oz": 32,
        "days_ago": 1,
    },
    {
        "shopify_order_id": "ORD-1007",
        "order_number": "#1007",
        "recipient_name": "Grace Lee",
        "shipping_address": {
            "street1": "258 Broadway",
            "city": "New York",
            "state": "NY",
            "zip": "10001",
        },
        "line_items": [
            {"name": "Mini Widget", "quantity": 1},
        ],
        "weight_oz": 6,
        "days_ago": 0,
    },
    {
        "shopify_order_id": "ORD-1008",
        "order_number": "#1008",
        "recipient_name": "Henry Wilson",
        "shipping_address": {
            "street1": "369 Lake Shore Drive",
            "city": "Chicago",
            "state": "IL",
            "zip": "60601",
        },
        "line_items": [
            {"name": "Widget Bundle", "quantity": 1},
            {"name": "Extra Accessories", "quantity": 4},
        ],
        "weight_oz": 80,
        "days_ago": 0,
    },
]


def seed_demo_customer(db: Session) -> Customer:
    """Create the demo customer if it doesn't exist."""
    customer_repo = CustomerRepository(db)

    # Check if already exists
    existing = customer_repo.get_by_shop_domain("demo-store.myshopify.com")
    if existing:
        print(f"Demo customer already exists: {existing.name}")
        return existing

    # Create demo customer
    customer = customer_repo.create({
        "id": DEMO_CUSTOMER_ID,
        "shop_domain": "demo-store.myshopify.com",
        "name": "Demo Store",
        "email": "demo@example.com",
        "plan_tier": "starter",
        "labels_this_month": 42,
        "labels_limit": PLAN_LIMITS["starter"],
        "default_from_address": {
            "name": "Demo Store Warehouse",
            "street1": "100 Warehouse Way",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94105",
            "phone": "555-123-4567",
        },
    })

    print(f"Created demo customer: {customer.name}")
    return customer


def seed_demo_orders(db: Session, customer_id: uuid.UUID) -> list[Order]:
    """Create demo orders for the customer."""
    order_repo = OrderRepository(db)

    created_orders = []
    now = datetime.utcnow()

    for order_data in DEMO_ORDERS:
        # Check if order already exists
        existing = order_repo.get_by_shopify_id(customer_id, order_data["shopify_order_id"])
        if existing:
            print(f"Order {order_data['order_number']} already exists, skipping")
            created_orders.append(existing)
            continue

        # Calculate created_at based on days_ago
        created_at = now - timedelta(days=order_data["days_ago"])

        order = order_repo.create({
            "customer_id": customer_id,
            "shopify_order_id": order_data["shopify_order_id"],
            "order_number": order_data["order_number"],
            "recipient_name": order_data["recipient_name"],
            "shipping_address": order_data["shipping_address"],
            "line_items": order_data["line_items"],
            "weight_oz": order_data["weight_oz"],
            "status": "unfulfilled",
            "created_at": created_at,
        })

        print(f"Created order: {order.order_number} - {order.recipient_name}")
        created_orders.append(order)

    return created_orders


def seed_demo_data(db: Session) -> tuple[Customer, list[Order]]:
    """Seed all demo data."""
    customer = seed_demo_customer(db)
    orders = seed_demo_orders(db, customer.id)
    return customer, orders


def has_demo_data(db: Session) -> bool:
    """Check if demo data already exists."""
    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_shop_domain("demo-store.myshopify.com")
    return customer is not None


def get_demo_customer(db: Session) -> Customer | None:
    """Get the demo customer if it exists."""
    customer_repo = CustomerRepository(db)
    return customer_repo.get_by_shop_domain("demo-store.myshopify.com")


def main():
    """CLI entry point for seeding data."""
    print("Running migrations...")
    run_migrations()

    print("\nSeeding demo data...")
    with get_db_session() as db:
        customer, orders = seed_demo_data(db)
        # Access attributes while session is still open
        customer_name = customer.name
        customer_domain = customer.shop_domain
        customer_plan = customer.plan_tier
        customer_labels = customer.labels_this_month
        customer_limit = customer.labels_limit
        order_count = len(orders)

    print(f"\nSeeding complete!")
    print(f"  Customer: {customer_name} ({customer_domain})")
    print(f"  Orders: {order_count} unfulfilled orders")
    print(f"  Plan: {customer_plan} ({customer_labels}/{customer_limit} labels used)")


if __name__ == "__main__":
    main()
