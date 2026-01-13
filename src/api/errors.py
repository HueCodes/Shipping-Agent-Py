"""Error handling utilities for API endpoints."""

import logging

from fastapi import HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    """Consistent error response format for all API errors."""

    error: str  # User-friendly message
    code: str  # Machine-readable error code
    detail: str | None = None  # Optional technical detail


class ErrorCode:
    """Machine-readable error codes."""

    # General errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    ACCESS_DENIED = "ACCESS_DENIED"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    # Auth errors
    AUTH_REQUIRED = "AUTH_REQUIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    SHOPIFY_TOKEN_INVALID = "SHOPIFY_TOKEN_INVALID"

    # EasyPost errors
    EASYPOST_RATE_ERROR = "EASYPOST_RATE_ERROR"
    EASYPOST_SHIPMENT_ERROR = "EASYPOST_SHIPMENT_ERROR"
    EASYPOST_TRACKING_ERROR = "EASYPOST_TRACKING_ERROR"
    EASYPOST_ADDRESS_ERROR = "EASYPOST_ADDRESS_ERROR"

    # Claude API errors
    CLAUDE_API_ERROR = "CLAUDE_API_ERROR"
    CLAUDE_TIMEOUT = "CLAUDE_TIMEOUT"

    # Shopify errors
    SHOPIFY_API_ERROR = "SHOPIFY_API_ERROR"

    # Database errors
    DATABASE_ERROR = "DATABASE_ERROR"


def create_error_response(
    status_code: int,
    error: str,
    code: str,
    detail: str | None = None,
    customer_id: str | None = None,
    endpoint: str | None = None,
    exc: Exception | None = None,
) -> HTTPException:
    """Create a consistent error response with logging."""
    log_context = {
        "error_code": code,
        "customer_id": customer_id,
        "endpoint": endpoint,
    }

    if exc:
        logger.exception(
            "API error: %s (code=%s, customer=%s, endpoint=%s)",
            error,
            code,
            customer_id,
            endpoint,
            extra=log_context,
        )
    else:
        logger.warning(
            "API error: %s (code=%s, customer=%s, endpoint=%s)",
            error,
            code,
            customer_id,
            endpoint,
            extra=log_context,
        )

    return HTTPException(
        status_code=status_code,
        detail=ErrorResponse(error=error, code=code, detail=detail).model_dump(),
    )
