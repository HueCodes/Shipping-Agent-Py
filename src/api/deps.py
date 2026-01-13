"""Shared dependencies for API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from src.api.errors import create_error_response, ErrorCode
from src.db.database import SessionLocal
from src.db.repository import CustomerRepository
from src.auth.jwt import verify_session_token
from src.agent.agent import is_mock_mode


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_customer(
    x_customer_id: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    """Get current customer from JWT token or X-Customer-ID header.

    Supports two authentication methods:
    1. Authorization: Bearer <jwt_token> (preferred for OAuth flow)
    2. X-Customer-ID: <uuid> (backward compatibility)

    Also checks for invalid Shopify tokens and prompts re-authentication.
    """
    customer_repo = CustomerRepository(db)
    customer_id = None

    # Try JWT authentication first
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]  # Remove "Bearer " prefix
        session = verify_session_token(token)

        if session:
            try:
                customer_id = UUID(session.customer_id)
            except ValueError:
                raise HTTPException(status_code=401, detail="Invalid session token")
        else:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Fall back to X-Customer-ID header
    elif x_customer_id:
        try:
            customer_id = UUID(x_customer_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid customer ID format")

    else:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Use Authorization header or X-Customer-ID.",
        )

    customer = customer_repo.get_by_id(customer_id)

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Check if customer has been uninstalled
    if customer.uninstalled_at:
        raise HTTPException(status_code=403, detail="App has been uninstalled for this shop")

    # Check if Shopify token has been marked as invalid
    if getattr(customer, "token_invalid", 0) == 1:
        raise create_error_response(
            status_code=401,
            error="Your Shopify connection has expired. Please reconnect your store.",
            code=ErrorCode.SHOPIFY_TOKEN_INVALID,
            customer_id=str(customer_id),
            endpoint="auth",
            detail="Use /api/shopify/reconnect to re-authenticate",
        )

    return customer


def get_optional_customer(
    x_customer_id: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    """Get current customer if authentication provided, otherwise None."""
    customer_repo = CustomerRepository(db)
    customer_id = None

    # Try JWT authentication first
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        session = verify_session_token(token)
        if session:
            try:
                customer_id = UUID(session.customer_id)
            except ValueError:
                return None
        else:
            return None

    # Fall back to X-Customer-ID header
    elif x_customer_id:
        try:
            customer_id = UUID(x_customer_id)
        except ValueError:
            return None

    if not customer_id:
        return None

    customer = customer_repo.get_by_id(customer_id)

    # Return None if uninstalled
    if customer and customer.uninstalled_at:
        return None

    return customer


def get_easypost_client():
    """Get EasyPost client (mock or real based on environment)."""
    if is_mock_mode():
        from src.mock import MockEasyPostClient

        return MockEasyPostClient()
    else:
        from src.easypost_client import EasyPostClient

        return EasyPostClient()
