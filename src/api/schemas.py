"""Pydantic schemas for API requests and responses."""

import re
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator


# Constants for validation
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR", "VI", "GU", "AS", "MP",  # Territories
}

ZIP_PATTERN = re.compile(r"^\d{5}(-\d{4})?$")
COUNTRY_CODES = {"US", "CA", "MX"}  # Supported countries

# Max weight: 70 lbs = 1120 oz (common carrier limit)
MAX_WEIGHT_OZ = 1120.0
MAX_DIMENSION_IN = 108.0  # Common carrier max dimension


def strip_str(v: str | None) -> str | None:
    """Strip whitespace from string."""
    if v is None:
        return None
    return v.strip()


def normalize_state(v: str | None) -> str | None:
    """Normalize state code to uppercase."""
    if v is None:
        return None
    return v.strip().upper()


# Chat models
class ChatRequest(BaseModel):
    """Chat request body."""

    message: str = Field(..., min_length=1, max_length=10000)
    session_id: str = Field(default="default", min_length=1, max_length=100)

    @field_validator("message", mode="before")
    @classmethod
    def strip_message(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Message cannot be empty")
        return v


class ChatResponse(BaseModel):
    """Chat response body."""

    response: str
    session_id: str


class ChatMessage(BaseModel):
    """A single chat message."""

    role: str = Field(..., pattern=r"^(user|assistant|system)$")
    content: str
    timestamp: str | None = None


class ChatHistoryResponse(BaseModel):
    """Chat history response."""

    session_id: str
    messages: list[ChatMessage]
    total: int = Field(..., ge=0)


# Address models
class AddressModel(BaseModel):
    """Shipping address for requests."""

    street1: str = Field(..., min_length=1, max_length=200)
    street2: str | None = Field(default=None, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=2, max_length=2)
    zip: str = Field(..., min_length=5, max_length=10)
    country: str = Field(default="US", min_length=2, max_length=2)

    @field_validator("street1", "street2", "city", mode="before")
    @classmethod
    def strip_strings(cls, v: str | None) -> str | None:
        return strip_str(v)

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state_code(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in US_STATES:
            raise ValueError(f"Invalid state code: {v}")
        return v

    @field_validator("zip", mode="before")
    @classmethod
    def validate_zip(cls, v: str) -> str:
        v = v.strip()
        if not ZIP_PATTERN.match(v):
            raise ValueError("ZIP code must be 5 digits or 5+4 format (e.g., 90210 or 90210-1234)")
        return v

    @field_validator("country", mode="before")
    @classmethod
    def normalize_country(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in COUNTRY_CODES:
            raise ValueError(f"Unsupported country: {v}. Supported: {', '.join(sorted(COUNTRY_CODES))}")
        return v


class LineItemModel(BaseModel):
    """Order line item."""

    name: str = Field(..., min_length=1, max_length=500)
    quantity: int = Field(..., ge=1, le=10000)
    price: float | None = Field(default=None, ge=0)


# Order models
class OrderResponse(BaseModel):
    """Order details response."""

    id: str
    shopify_order_id: str
    order_number: str | None
    recipient_name: str | None
    shipping_address: dict | None
    line_items: list[dict] | None
    weight_oz: float | None
    status: str
    created_at: str | None


class OrderListResponse(BaseModel):
    """List of orders response."""

    orders: list[OrderResponse]
    total: int = Field(..., ge=0)


class OrderSyncResponse(BaseModel):
    """Response from order sync operation."""

    synced: int = Field(..., ge=0)
    created: int = Field(..., ge=0)
    updated: int = Field(..., ge=0)
    errors: list[str] = Field(default_factory=list)


# Shipment models
class CreateShipmentRequest(BaseModel):
    """Create shipment request."""

    order_id: str | None = Field(default=None, max_length=100)
    rate_id: str = Field(..., min_length=1, max_length=100)
    to_name: str = Field(..., min_length=1, max_length=100)
    to_street: str = Field(..., min_length=1, max_length=200)
    to_city: str = Field(..., min_length=1, max_length=100)
    to_state: str = Field(..., min_length=2, max_length=2)
    to_zip: str = Field(..., min_length=5, max_length=10)
    weight_oz: float = Field(..., gt=0, le=MAX_WEIGHT_OZ)
    length: float = Field(default=6.0, gt=0, le=MAX_DIMENSION_IN)
    width: float = Field(default=4.0, gt=0, le=MAX_DIMENSION_IN)
    height: float = Field(default=2.0, gt=0, le=MAX_DIMENSION_IN)

    @field_validator("to_name", "to_street", "to_city", mode="before")
    @classmethod
    def strip_strings(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("to_state", mode="before")
    @classmethod
    def normalize_state_code(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in US_STATES:
            raise ValueError(f"Invalid state code: {v}")
        return v

    @field_validator("to_zip", mode="before")
    @classmethod
    def validate_zip(cls, v: str) -> str:
        v = v.strip()
        if not ZIP_PATTERN.match(v):
            raise ValueError("ZIP code must be 5 digits or 5+4 format")
        return v


class ShipmentResponse(BaseModel):
    """Shipment details response."""

    id: str
    order_id: str | None
    tracking_number: str | None
    carrier: str
    service: str
    rate_amount: float | None
    label_url: str | None
    status: str
    estimated_delivery: str | None
    created_at: str | None


# Rate models
class RateRequest(BaseModel):
    """Get rates request - either order_id OR address fields required."""

    order_id: str | None = Field(default=None, max_length=100)
    to_city: str | None = Field(default=None, min_length=1, max_length=100)
    to_state: str | None = Field(default=None, min_length=2, max_length=2)
    to_zip: str | None = Field(default=None, min_length=5, max_length=10)
    weight_oz: float | None = Field(default=None, gt=0, le=MAX_WEIGHT_OZ)
    length: float = Field(default=6.0, gt=0, le=MAX_DIMENSION_IN)
    width: float = Field(default=4.0, gt=0, le=MAX_DIMENSION_IN)
    height: float = Field(default=2.0, gt=0, le=MAX_DIMENSION_IN)

    @field_validator("to_city", mode="before")
    @classmethod
    def strip_city(cls, v: str | None) -> str | None:
        return strip_str(v)

    @field_validator("to_state", mode="before")
    @classmethod
    def normalize_state_code(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().upper()
        if v and v not in US_STATES:
            raise ValueError(f"Invalid state code: {v}")
        return v

    @field_validator("to_zip", mode="before")
    @classmethod
    def validate_zip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if v and not ZIP_PATTERN.match(v):
            raise ValueError("ZIP code must be 5 digits or 5+4 format")
        return v


class RateResponse(BaseModel):
    """Shipping rate."""

    rate_id: str
    carrier: str
    service: str
    price: float = Field(..., ge=0)
    delivery_days: int | None = Field(default=None, ge=0)


class RatesResponse(BaseModel):
    """List of shipping rates."""

    rates: list[RateResponse]


# Tracking models
class TrackingEventResponse(BaseModel):
    """Tracking event."""

    status: str
    description: str | None
    location: dict | None
    occurred_at: str


class TrackingResponse(BaseModel):
    """Tracking status response."""

    tracking_number: str
    carrier: str
    status: str
    estimated_delivery: str | None
    events: list[TrackingEventResponse]


# Address validation models
class ValidateAddressRequest(BaseModel):
    """Address validation request."""

    name: str | None = Field(default=None, max_length=100)
    street1: str = Field(..., min_length=1, max_length=200)
    street2: str | None = Field(default=None, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=2, max_length=2)
    zip: str = Field(..., min_length=5, max_length=10)
    country: str = Field(default="US", min_length=2, max_length=2)

    @field_validator("name", "street1", "street2", "city", mode="before")
    @classmethod
    def strip_strings(cls, v: str | None) -> str | None:
        return strip_str(v)

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state_code(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in US_STATES:
            raise ValueError(f"Invalid state code: {v}")
        return v

    @field_validator("zip", mode="before")
    @classmethod
    def validate_zip(cls, v: str) -> str:
        v = v.strip()
        if not ZIP_PATTERN.match(v):
            raise ValueError("ZIP code must be 5 digits or 5+4 format")
        return v

    @field_validator("country", mode="before")
    @classmethod
    def normalize_country(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in COUNTRY_CODES:
            raise ValueError(f"Unsupported country: {v}")
        return v


class StandardizedAddress(BaseModel):
    """Standardized address from validation."""

    name: str | None
    street1: str
    street2: str | None
    city: str
    state: str
    zip: str
    country: str


class ValidateAddressResponse(BaseModel):
    """Address validation response."""

    valid: bool
    standardized: StandardizedAddress | None = None
    message: str | None = None


# Customer models
class CustomerResponse(BaseModel):
    """Customer info response."""

    id: str
    name: str
    shop_domain: str
    plan_tier: str
    labels_this_month: int = Field(..., ge=0)
    labels_limit: int = Field(..., ge=0)
    labels_remaining: int = Field(..., ge=0)


class UpdatePreferencesRequest(BaseModel):
    """Update customer preferences."""

    default_carrier: str | None = Field(default=None, max_length=50)
    auto_cheapest: bool | None = None

    @field_validator("default_carrier", mode="before")
    @classmethod
    def strip_carrier(cls, v: str | None) -> str | None:
        return strip_str(v)


# OAuth models
class OAuthStatusResponse(BaseModel):
    """OAuth connection status."""

    connected: bool
    shop_domain: str | None = None
    installed_at: str | None = None
    scopes: list[str] | None = None


class SessionTokenResponse(BaseModel):
    """Session token response after OAuth."""

    token: str
    expires_in: int = Field(..., gt=0)
    customer_id: str
    shop_domain: str
