"""Add token validation fields to customers table.

Revision ID: 003
Revises: 002
Create Date: 2026-01-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add token validation columns to customers table
    op.add_column("customers", sa.Column("token_validated_at", sa.DateTime))
    op.add_column(
        "customers",
        sa.Column("token_invalid", sa.Integer, server_default="0", nullable=False),
    )

    # Index for quickly finding customers with invalid tokens
    op.create_index("ix_customers_token_invalid", "customers", ["token_invalid"])


def downgrade() -> None:
    op.drop_index("ix_customers_token_invalid", "customers")
    op.drop_column("customers", "token_invalid")
    op.drop_column("customers", "token_validated_at")
