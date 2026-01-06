"""Customer context for shipping agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from src.db.models import Customer


# Plan tier label limits
PLAN_LIMITS = {
    "free": 50,
    "starter": 500,
    "growth": 2000,
    "scale": 10000,
}


@dataclass
class CustomerContext:
    """Customer context for agent personalization and limit enforcement."""

    store_name: str
    plan_tier: str  # free, starter, growth, scale
    labels_used: int
    labels_limit: int
    customer_id: UUID | None = None

    @classmethod
    def default(cls) -> CustomerContext:
        """Create a default context for testing/mock mode."""
        return cls(
            store_name="Demo Store",
            plan_tier="starter",
            labels_used=42,
            labels_limit=PLAN_LIMITS["starter"],
        )

    @classmethod
    def from_plan(cls, store_name: str, plan_tier: str, labels_used: int = 0) -> CustomerContext:
        """Create context with limit derived from plan tier."""
        limit = PLAN_LIMITS.get(plan_tier, PLAN_LIMITS["free"])
        return cls(
            store_name=store_name,
            plan_tier=plan_tier,
            labels_used=labels_used,
            labels_limit=limit,
        )

    @classmethod
    def from_customer(cls, customer: Customer) -> CustomerContext:
        """Create context from a database Customer record."""
        return cls(
            store_name=customer.name,
            plan_tier=customer.plan_tier,
            labels_used=customer.labels_this_month,
            labels_limit=customer.labels_limit,
            customer_id=customer.id,
        )

    def labels_remaining(self) -> int:
        """Return number of labels remaining this month."""
        return max(0, self.labels_limit - self.labels_used)

    def is_limit_exceeded(self) -> bool:
        """Check if label limit has been exceeded."""
        return self.labels_used >= self.labels_limit

    def can_create_labels(self, count: int = 1) -> bool:
        """Check if the customer can create the specified number of labels."""
        return (self.labels_used + count) <= self.labels_limit

    def format_for_prompt(self) -> str:
        """Format context for injection into system prompt."""
        return f"""Current context:
- Store: {self.store_name}
- Plan: {self.plan_tier}
- Labels this month: {self.labels_used}/{self.labels_limit}"""
