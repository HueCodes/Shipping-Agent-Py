"""Initial schema with all tables.

Revision ID: 001
Revises:
Create Date: 2025-01-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create customers table
    op.create_table(
        "customers",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("shop_domain", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("plan_tier", sa.String(50), default="free"),
        sa.Column("labels_this_month", sa.Integer, default=0),
        sa.Column("labels_limit", sa.Integer, default=50),
        sa.Column("easypost_api_key", sa.Text),
        sa.Column("default_from_address", sa.JSON),
        sa.Column("shopify_access_token", sa.Text),
        sa.Column("created_at", sa.DateTime, default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create orders table
    op.create_table(
        "orders",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("customer_id", sa.CHAR(32), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shopify_order_id", sa.String(100), nullable=False),
        sa.Column("order_number", sa.String(100)),
        sa.Column("recipient_name", sa.String(255)),
        sa.Column("status", sa.String(50), default="unfulfilled"),
        sa.Column("shipping_address", sa.JSON),
        sa.Column("line_items", sa.JSON),
        sa.Column("weight_oz", sa.Float),
        sa.Column("created_at", sa.DateTime, default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("customer_id", "shopify_order_id", name="uq_customer_order"),
    )

    # Create shipments table
    op.create_table(
        "shipments",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("customer_id", sa.CHAR(32), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.CHAR(32), sa.ForeignKey("orders.id", ondelete="SET NULL")),
        sa.Column("easypost_shipment_id", sa.String(255)),
        sa.Column("carrier", sa.String(100), nullable=False),
        sa.Column("service", sa.String(100), nullable=False),
        sa.Column("tracking_number", sa.String(255)),
        sa.Column("label_url", sa.Text),
        sa.Column("rate_amount", sa.Float),
        sa.Column("status", sa.String(50), default="created"),
        sa.Column("estimated_delivery", sa.DateTime),
        sa.Column("created_at", sa.DateTime, default=sa.func.now()),
    )

    # Create conversations table
    op.create_table(
        "conversations",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("customer_id", sa.CHAR(32), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("messages", sa.JSON, default=list),
        sa.Column("created_at", sa.DateTime, default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create tracking_events table
    op.create_table(
        "tracking_events",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("shipment_id", sa.CHAR(32), sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(100), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("location", sa.JSON),
        sa.Column("occurred_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, default=sa.func.now()),
    )

    # Create indexes for common queries
    op.create_index("ix_orders_customer_status", "orders", ["customer_id", "status"])
    op.create_index("ix_shipments_tracking", "shipments", ["tracking_number"])
    op.create_index("ix_shipments_order", "shipments", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_shipments_order", "shipments")
    op.drop_index("ix_shipments_tracking", "shipments")
    op.drop_index("ix_orders_customer_status", "orders")
    op.drop_table("tracking_events")
    op.drop_table("conversations")
    op.drop_table("shipments")
    op.drop_table("orders")
    op.drop_table("customers")
