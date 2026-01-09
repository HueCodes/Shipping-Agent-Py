"""Add Shopify OAuth fields to customers table.

Revision ID: 002
Revises: 001
Create Date: 2026-01-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Shopify OAuth columns to customers table
    op.add_column("customers", sa.Column("shopify_nonce", sa.String(64)))
    op.add_column("customers", sa.Column("shopify_scope", sa.Text))
    op.add_column("customers", sa.Column("installed_at", sa.DateTime))
    op.add_column("customers", sa.Column("uninstalled_at", sa.DateTime))

    # Index for looking up customers by nonce during OAuth callback
    op.create_index("ix_customers_shopify_nonce", "customers", ["shopify_nonce"])


def downgrade() -> None:
    op.drop_index("ix_customers_shopify_nonce", "customers")
    op.drop_column("customers", "uninstalled_at")
    op.drop_column("customers", "installed_at")
    op.drop_column("customers", "shopify_scope")
    op.drop_column("customers", "shopify_nonce")
