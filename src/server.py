"""FastAPI server for the shipping agent."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
import json
import asyncio
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

load_dotenv()

logger = logging.getLogger(__name__)

# Store agent instances per customer (in-memory cache)
agents: dict[str, "ShippingAgent"] = {}


# ============================================================================
# Pydantic Models
# ============================================================================

# Chat models
# ============================================================================
# Error Response Schema
# ============================================================================

class ErrorResponse(BaseModel):
    """Consistent error response format for all API errors."""
    error: str  # User-friendly message
    code: str   # Machine-readable error code (e.g., "EASYPOST_RATE_ERROR")
    detail: str | None = None  # Optional technical detail for debugging


# Error codes
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
    """Create a consistent error response with logging.

    Args:
        status_code: HTTP status code
        error: User-friendly error message
        code: Machine-readable error code
        detail: Optional technical detail (safe for user)
        customer_id: Customer ID for logging context
        endpoint: Endpoint name for logging context
        exc: Original exception for server-side logging

    Returns:
        HTTPException with consistent error format
    """
    # Log the error with context (full traceback for server logs only)
    log_context = {
        "error_code": code,
        "customer_id": customer_id,
        "endpoint": endpoint,
    }

    if exc:
        logger.exception(
            "API error: %s (code=%s, customer=%s, endpoint=%s)",
            error, code, customer_id, endpoint,
            extra=log_context,
        )
    else:
        logger.warning(
            "API error: %s (code=%s, customer=%s, endpoint=%s)",
            error, code, customer_id, endpoint,
            extra=log_context,
        )

    return HTTPException(
        status_code=status_code,
        detail=ErrorResponse(error=error, code=code, detail=detail).model_dump(),
    )


class ChatRequest(BaseModel):
    """Chat request body."""
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    """Chat response body."""
    response: str
    session_id: str


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str | None = None


class ChatHistoryResponse(BaseModel):
    """Chat history response."""
    session_id: str
    messages: list[ChatMessage]
    total: int


# Order models
class AddressModel(BaseModel):
    """Shipping address."""
    street1: str
    street2: str | None = None
    city: str
    state: str
    zip: str
    country: str = "US"


class LineItemModel(BaseModel):
    """Order line item."""
    name: str
    quantity: int
    price: float | None = None


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
    total: int


# Shipment models
class CreateShipmentRequest(BaseModel):
    """Create shipment request."""
    order_id: str | None = None
    rate_id: str
    to_name: str
    to_street: str
    to_city: str
    to_state: str
    to_zip: str
    weight_oz: float
    length: float = 6
    width: float = 4
    height: float = 2


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


class RateRequest(BaseModel):
    """Get rates request."""
    order_id: str | None = None
    to_city: str | None = None
    to_state: str | None = None
    to_zip: str | None = None
    weight_oz: float | None = None
    length: float = 6
    width: float = 4
    height: float = 2


class RateResponse(BaseModel):
    """Shipping rate."""
    rate_id: str
    carrier: str
    service: str
    price: float
    delivery_days: int | None


class RatesResponse(BaseModel):
    """List of shipping rates."""
    rates: list[RateResponse]


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
    name: str | None = None
    street1: str
    street2: str | None = None
    city: str
    state: str
    zip: str
    country: str = "US"


class StandardizedAddress(BaseModel):
    """Standardized address."""
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
    labels_this_month: int
    labels_limit: int
    labels_remaining: int


class UpdatePreferencesRequest(BaseModel):
    """Update customer preferences."""
    default_carrier: str | None = None
    auto_cheapest: bool | None = None


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
    expires_in: int
    customer_id: str
    shop_domain: str


# ============================================================================
# Dependencies
# ============================================================================

def get_db():
    """Get database session."""
    from src.db.database import SessionLocal
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
    from src.db.repository import CustomerRepository

    customer_repo = CustomerRepository(db)
    customer_id = None

    # Try JWT authentication first
    if authorization and authorization.startswith("Bearer "):
        from src.auth.jwt import verify_session_token

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
    """Get current customer if authentication provided, otherwise None.

    Supports JWT token or X-Customer-ID header.
    """
    from src.db.repository import CustomerRepository

    customer_repo = CustomerRepository(db)
    customer_id = None

    # Try JWT authentication first
    if authorization and authorization.startswith("Bearer "):
        from src.auth.jwt import verify_session_token

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
    from src.agent.agent import is_mock_mode

    if is_mock_mode():
        from src.mock import MockEasyPostClient
        return MockEasyPostClient()
    else:
        from src.easypost_client import EasyPostClient
        return EasyPostClient()


# ============================================================================
# Lifespan & App Setup
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup/shutdown."""
    from src.agent.agent import is_mock_mode
    from src.db.migrations import run_migrations
    from src.db.seed import seed_demo_data, has_demo_data
    from src.db.database import get_db_session

    # Run migrations on startup
    logger.info("Running database migrations...")
    try:
        run_migrations()
        logger.info("Migrations complete")
    except Exception as e:
        logger.error("Migration failed: %s", e)
        # Continue anyway - tables might already exist

    # Seed demo data in mock mode if database is empty
    if is_mock_mode():
        with get_db_session() as db:
            if not has_demo_data(db):
                logger.info("Seeding demo data...")
                seed_demo_data(db)
                logger.info("Demo data seeded")

    mode = "MOCK" if is_mock_mode() else "LIVE"
    print(f"\n  Shipping Agent Server ({mode} MODE)")
    print(f"  http://localhost:8000\n")

    yield

    agents.clear()


app = FastAPI(
    title="Shipping Agent",
    description="AI-powered shipping assistant",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Chat API
# ============================================================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    customer=Depends(get_optional_customer),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Send a message to the shipping agent."""
    from src.agent import ShippingAgent
    from src.agent.context import CustomerContext

    if not request.message.strip():
        raise create_error_response(
            status_code=400,
            error="Message cannot be empty",
            code=ErrorCode.VALIDATION_ERROR,
            endpoint="/api/chat",
        )

    customer_id_str = str(customer.id) if customer else None

    try:
        # Create agent with customer context if available
        cache_key = str(customer.id) if customer else request.session_id

        if cache_key not in agents:
            if customer:
                context = CustomerContext.from_customer(customer)
                agents[cache_key] = ShippingAgent(context=context, db=db)
            else:
                agents[cache_key] = ShippingAgent()

        agent = agents[cache_key]
        response = agent.chat(request.message)
        return ChatResponse(response=response, session_id=cache_key)
    except TimeoutError as e:
        raise create_error_response(
            status_code=504,
            error="The AI assistant is taking too long to respond. Please try again.",
            code=ErrorCode.CLAUDE_TIMEOUT,
            customer_id=customer_id_str,
            endpoint="/api/chat",
            exc=e,
        )
    except Exception as e:
        # Check if it's a Claude API error
        error_str = str(e).lower()
        if "anthropic" in error_str or "claude" in error_str or "api" in error_str:
            raise create_error_response(
                status_code=502,
                error="Unable to connect to the AI assistant. Please try again later.",
                code=ErrorCode.CLAUDE_API_ERROR,
                customer_id=customer_id_str,
                endpoint="/api/chat",
                exc=e,
            )
        raise create_error_response(
            status_code=500,
            error="An error occurred while processing your message. Please try again.",
            code=ErrorCode.INTERNAL_ERROR,
            customer_id=customer_id_str,
            endpoint="/api/chat",
            exc=e,
        )


@app.post("/api/reset")
async def reset(
    session_id: str = "default",
    customer=Depends(get_optional_customer),
) -> dict:
    """Reset conversation history for a session."""
    cache_key = str(customer.id) if customer else session_id
    if cache_key in agents:
        agents[cache_key].reset()
    return {"status": "ok", "session_id": cache_key}


@app.get("/api/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str = "default",
    limit: int = 50,
    customer=Depends(get_optional_customer),
    db: Session = Depends(get_db),
) -> ChatHistoryResponse:
    """Get conversation history for a session."""
    from src.db.repository import ConversationRepository

    cache_key = str(customer.id) if customer else session_id

    # Try to get from in-memory agent first
    if cache_key in agents:
        agent = agents[cache_key]
        messages = agent.messages[-limit:] if limit else agent.messages
    else:
        # Fall back to database
        if customer:
            conversation_repo = ConversationRepository(db)
            conversation = conversation_repo.get_or_create(customer.id)
            messages = conversation_repo.get_messages(conversation.id, limit=limit)
        else:
            messages = []

    # Convert messages to response format
    chat_messages = []
    for msg in messages:
        content = msg.get("content", "")
        # Handle content that might be a list (tool results)
        if isinstance(content, list):
            # Extract text from content blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        text_parts.append(f"[Tool result: {block.get('content', '')}]")
            content = "\n".join(text_parts)

        chat_messages.append(ChatMessage(
            role=msg.get("role", "unknown"),
            content=content,
            timestamp=msg.get("timestamp"),
        ))

    return ChatHistoryResponse(
        session_id=cache_key,
        messages=chat_messages,
        total=len(chat_messages),
    )


@app.websocket("/api/chat/stream")
async def chat_stream(websocket: WebSocket):
    """WebSocket endpoint for streaming chat responses."""
    from src.agent import ShippingAgent
    from src.agent.context import CustomerContext
    from src.db.database import get_db_session
    from src.db.repository import CustomerRepository

    await websocket.accept()

    session_id = None
    customer = None
    agent = None

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            user_message = message_data.get("message", "")
            session_id = message_data.get("session_id", "default")
            customer_id = message_data.get("customer_id")

            if not user_message.strip():
                await websocket.send_json({
                    "type": "error",
                    "message": "Message cannot be empty",
                })
                continue

            # Get or create agent
            with get_db_session() as db:
                cache_key = customer_id or session_id

                # Load customer if provided
                if customer_id:
                    try:
                        cid = UUID(customer_id)
                        customer_repo = CustomerRepository(db)
                        customer = customer_repo.get_by_id(cid)
                    except (ValueError, Exception):
                        customer = None

                if cache_key not in agents:
                    if customer:
                        context = CustomerContext.from_customer(customer)
                        agents[cache_key] = ShippingAgent(context=context, db=db)
                    else:
                        agents[cache_key] = ShippingAgent()

                agent = agents[cache_key]

                # Send thinking event
                await websocket.send_json({
                    "type": "status",
                    "status": "thinking",
                    "message": "Processing your request...",
                })

                # Process in mock mode (streaming simulation)
                if agent.mock_mode:
                    # Simulate thinking delay
                    await asyncio.sleep(0.3)

                    # Send tool execution event if it looks like a tool call
                    lower_msg = user_message.lower()
                    if any(term in lower_msg for term in ["rate", "ship", "track", "valid"]):
                        tool_name = "get_shipping_rates"
                        if "valid" in lower_msg:
                            tool_name = "validate_address"
                        elif "ship" in lower_msg:
                            tool_name = "create_shipment"
                        elif "track" in lower_msg:
                            tool_name = "get_tracking_status"

                        await websocket.send_json({
                            "type": "tool_start",
                            "tool": tool_name,
                            "message": f"Executing {tool_name}...",
                        })
                        await asyncio.sleep(0.2)
                        await websocket.send_json({
                            "type": "tool_complete",
                            "tool": tool_name,
                            "message": f"{tool_name} completed",
                        })

                    # Get the response
                    response = agent.chat(user_message)

                    # Stream response in chunks (typewriter effect)
                    await websocket.send_json({
                        "type": "status",
                        "status": "responding",
                        "message": "Generating response...",
                    })

                    # Send response in chunks for typewriter effect
                    chunk_size = 20
                    for i in range(0, len(response), chunk_size):
                        chunk = response[i:i + chunk_size]
                        await websocket.send_json({
                            "type": "chunk",
                            "content": chunk,
                        })
                        await asyncio.sleep(0.02)  # Small delay between chunks

                    # Send completion event
                    await websocket.send_json({
                        "type": "complete",
                        "session_id": cache_key,
                    })
                else:
                    # Real mode: use true streaming with Claude API
                    await websocket.send_json({
                        "type": "status",
                        "status": "responding",
                        "message": "Generating response...",
                    })

                    async for event in agent.chat_stream(user_message):
                        event_type = event.get("type")

                        if event_type == "text":
                            await websocket.send_json({
                                "type": "chunk",
                                "content": event.get("content", ""),
                            })
                        elif event_type == "tool_start":
                            await websocket.send_json({
                                "type": "tool_start",
                                "tool": event.get("tool", ""),
                                "message": f"Executing {event.get('tool', '')}...",
                            })
                        elif event_type == "tool_complete":
                            await websocket.send_json({
                                "type": "tool_complete",
                                "tool": event.get("tool", ""),
                                "message": f"{event.get('tool', '')} completed",
                            })
                        elif event_type == "error":
                            await websocket.send_json({
                                "type": "error",
                                "message": event.get("content", "Unknown error"),
                            })
                        elif event_type == "complete":
                            await websocket.send_json({
                                "type": "complete",
                                "session_id": cache_key,
                            })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session: %s", session_id)
    except json.JSONDecodeError:
        await websocket.send_json({
            "type": "error",
            "code": ErrorCode.VALIDATION_ERROR,
            "message": "Invalid JSON format",
        })
    except Exception as e:
        logger.exception("WebSocket error for session %s: %s", session_id, e)
        try:
            # Send user-friendly error, not raw exception
            await websocket.send_json({
                "type": "error",
                "code": ErrorCode.INTERNAL_ERROR,
                "message": "An error occurred while processing your request. Please try again.",
            })
        except Exception:
            pass


# ============================================================================
# Orders API
# ============================================================================

@app.get("/api/orders", response_model=OrderListResponse)
async def list_orders(
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
    limit: int = 50,
    status: str | None = None,
    search: str | None = None,
) -> OrderListResponse:
    """List orders for the current customer."""
    from src.db.repository import OrderRepository

    order_repo = OrderRepository(db)

    if status == "unfulfilled":
        orders = order_repo.list_unfulfilled(customer.id, limit=limit, search=search)
    else:
        orders = order_repo.list_by_customer(customer.id, limit=limit, status=status)

    order_responses = [
        OrderResponse(
            id=str(o.id),
            shopify_order_id=o.shopify_order_id,
            order_number=o.order_number,
            recipient_name=o.recipient_name,
            shipping_address=o.shipping_address,
            line_items=o.line_items,
            weight_oz=o.weight_oz,
            status=o.status,
            created_at=o.created_at.isoformat() if o.created_at else None,
        )
        for o in orders
    ]

    return OrderListResponse(orders=order_responses, total=len(order_responses))


@app.get("/api/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> OrderResponse:
    """Get order details."""
    from src.db.repository import OrderRepository

    try:
        oid = UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order ID format")

    order_repo = OrderRepository(db)
    order = order_repo.get_by_id(oid)

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Verify order belongs to customer
    if order.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return OrderResponse(
        id=str(order.id),
        shopify_order_id=order.shopify_order_id,
        order_number=order.order_number,
        recipient_name=order.recipient_name,
        shipping_address=order.shipping_address,
        line_items=order.line_items,
        weight_oz=order.weight_oz,
        status=order.status,
        created_at=order.created_at.isoformat() if order.created_at else None,
    )


@app.post("/api/orders/{order_id}/fulfill")
async def fulfill_order(
    order_id: str,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> dict:
    """Mark order as fulfilled (shipped)."""
    from src.db.repository import OrderRepository, ShipmentRepository

    try:
        oid = UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order ID format")

    order_repo = OrderRepository(db)
    shipment_repo = ShipmentRepository(db)

    order = order_repo.get_by_id(oid)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if shipment exists
    shipment = shipment_repo.get_by_order_id(oid)
    if not shipment:
        raise HTTPException(
            status_code=400,
            detail="Cannot fulfill order without a shipment. Create a shipment first.",
        )

    order_repo.update_status(oid, "fulfilled")

    return {
        "status": "ok",
        "order_id": order_id,
        "order_status": "fulfilled",
        "tracking_number": shipment.tracking_number,
    }


# ============================================================================
# Shipping API
# ============================================================================

@app.post("/api/rates", response_model=RatesResponse)
async def get_rates(
    request: RateRequest,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> RatesResponse:
    """Get shipping rates for an order or address."""
    from src.db.repository import OrderRepository
    from src.easypost_client import Address, Parcel, RateError

    customer_id_str = str(customer.id)
    client = get_easypost_client()

    # Get address from order or request
    if request.order_id:
        try:
            oid = UUID(request.order_id)
        except ValueError:
            raise create_error_response(
                status_code=400,
                error="Invalid order ID format",
                code=ErrorCode.VALIDATION_ERROR,
                customer_id=customer_id_str,
                endpoint="/api/rates",
            )

        order_repo = OrderRepository(db)
        order = order_repo.get_by_id(oid)

        if not order or order.customer_id != customer.id:
            raise create_error_response(
                status_code=404,
                error="Order not found",
                code=ErrorCode.NOT_FOUND,
                customer_id=customer_id_str,
                endpoint="/api/rates",
            )

        addr = order.shipping_address or {}
        to_address = Address(
            name=order.recipient_name or "Recipient",
            street1=addr.get("street1", ""),
            city=addr.get("city", ""),
            state=addr.get("state", ""),
            zip_code=addr.get("zip", ""),
        )
        weight_oz = order.weight_oz or 16
    else:
        if not all([request.to_city, request.to_state, request.to_zip, request.weight_oz]):
            raise create_error_response(
                status_code=400,
                error="Either order_id or (to_city, to_state, to_zip, weight_oz) required",
                code=ErrorCode.VALIDATION_ERROR,
                customer_id=customer_id_str,
                endpoint="/api/rates",
            )

        to_address = Address(
            name="Recipient",
            street1="",
            city=request.to_city,
            state=request.to_state,
            zip_code=request.to_zip,
        )
        weight_oz = request.weight_oz

    parcel = Parcel(
        length=request.length,
        width=request.width,
        height=request.height,
        weight=weight_oz,
    )

    try:
        rates = client.get_rates(to_address, parcel)
    except RateError as e:
        raise create_error_response(
            status_code=502,
            error=e.message,
            code=ErrorCode.EASYPOST_RATE_ERROR,
            customer_id=customer_id_str,
            endpoint="/api/rates",
            exc=e,
        )
    except Exception as e:
        raise create_error_response(
            status_code=500,
            error="Unable to fetch shipping rates. Please try again.",
            code=ErrorCode.EASYPOST_RATE_ERROR,
            customer_id=customer_id_str,
            endpoint="/api/rates",
            exc=e,
        )

    return RatesResponse(
        rates=[
            RateResponse(
                rate_id=r.rate_id,
                carrier=r.carrier,
                service=r.service,
                price=r.rate,
                delivery_days=r.delivery_days,
            )
            for r in rates
        ]
    )


@app.post("/api/addresses/validate", response_model=ValidateAddressResponse)
async def validate_address(
    request: ValidateAddressRequest,
    customer=Depends(get_current_customer),
) -> ValidateAddressResponse:
    """Validate and standardize a shipping address."""
    from src.easypost_client import Address, AddressValidationError

    customer_id_str = str(customer.id)
    client = get_easypost_client()

    address = Address(
        name=request.name or "Recipient",
        street1=request.street1,
        street2=request.street2,
        city=request.city,
        state=request.state,
        zip_code=request.zip,
        country=request.country,
    )

    try:
        is_valid, standardized, message = client.validate_address(address)
    except AddressValidationError as e:
        raise create_error_response(
            status_code=502,
            error=e.message,
            code=ErrorCode.EASYPOST_ADDRESS_ERROR,
            customer_id=customer_id_str,
            endpoint="/api/addresses/validate",
            exc=e,
        )
    except Exception as e:
        raise create_error_response(
            status_code=500,
            error="Unable to validate address. Please try again.",
            code=ErrorCode.EASYPOST_ADDRESS_ERROR,
            customer_id=customer_id_str,
            endpoint="/api/addresses/validate",
            exc=e,
        )

    if is_valid and standardized:
        return ValidateAddressResponse(
            valid=True,
            standardized=StandardizedAddress(
                name=standardized.name,
                street1=standardized.street1,
                street2=standardized.street2,
                city=standardized.city,
                state=standardized.state,
                zip=standardized.zip_code,
                country=standardized.country or "US",
            ),
            message=message,
        )
    else:
        return ValidateAddressResponse(
            valid=False,
            standardized=None,
            message=message or "Address validation failed",
        )


@app.post("/api/shipments", response_model=ShipmentResponse)
async def create_shipment(
    request: CreateShipmentRequest,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    """Create a shipment and purchase a label."""
    from src.db.repository import OrderRepository, ShipmentRepository, CustomerRepository
    from src.easypost_client import Address, Parcel, ShipmentError

    customer_id_str = str(customer.id)
    client = get_easypost_client()
    order_repo = OrderRepository(db)
    shipment_repo = ShipmentRepository(db)
    customer_repo = CustomerRepository(db)

    # Validate order if provided
    order_id = None
    if request.order_id:
        try:
            order_id = UUID(request.order_id)
        except ValueError:
            raise create_error_response(
                status_code=400,
                error="Invalid order ID format",
                code=ErrorCode.VALIDATION_ERROR,
                customer_id=customer_id_str,
                endpoint="/api/shipments",
            )

        order = order_repo.get_by_id(order_id)
        if not order or order.customer_id != customer.id:
            raise create_error_response(
                status_code=404,
                error="Order not found",
                code=ErrorCode.NOT_FOUND,
                customer_id=customer_id_str,
                endpoint="/api/shipments",
            )

    # Check label limit
    if customer.labels_this_month >= customer.labels_limit:
        raise create_error_response(
            status_code=403,
            error=f"Label limit reached ({customer.labels_limit}/month). Upgrade your plan.",
            code=ErrorCode.ACCESS_DENIED,
            customer_id=customer_id_str,
            endpoint="/api/shipments",
        )

    to_address = Address(
        name=request.to_name,
        street1=request.to_street,
        city=request.to_city,
        state=request.to_state,
        zip_code=request.to_zip,
    )
    parcel = Parcel(
        length=request.length,
        width=request.width,
        height=request.height,
        weight=request.weight_oz,
    )

    try:
        shipment = client.create_shipment(to_address, parcel, request.rate_id)
    except ShipmentError as e:
        raise create_error_response(
            status_code=502,
            error=e.message,
            code=ErrorCode.EASYPOST_SHIPMENT_ERROR,
            customer_id=customer_id_str,
            endpoint="/api/shipments",
            exc=e,
        )
    except Exception as e:
        raise create_error_response(
            status_code=500,
            error="Unable to create shipment. Please try again.",
            code=ErrorCode.EASYPOST_SHIPMENT_ERROR,
            customer_id=customer_id_str,
            endpoint="/api/shipments",
            exc=e,
        )

    # Save to database
    db_shipment = shipment_repo.create({
        "customer_id": customer.id,
        "order_id": order_id,
        "easypost_shipment_id": shipment.id,
        "carrier": shipment.carrier,
        "service": shipment.service,
        "tracking_number": shipment.tracking_number,
        "label_url": shipment.label_url,
        "rate_amount": shipment.rate,
        "status": "created",
    })

    # Update order status if linked
    if order_id:
        order_repo.update_status(order_id, "shipped")

    # Increment label count
    customer_repo.increment_label_count(customer.id)

    return ShipmentResponse(
        id=str(db_shipment.id),
        order_id=str(order_id) if order_id else None,
        tracking_number=db_shipment.tracking_number,
        carrier=db_shipment.carrier,
        service=db_shipment.service,
        rate_amount=db_shipment.rate_amount,
        label_url=db_shipment.label_url,
        status=db_shipment.status,
        estimated_delivery=db_shipment.estimated_delivery.isoformat() if db_shipment.estimated_delivery else None,
        created_at=db_shipment.created_at.isoformat() if db_shipment.created_at else None,
    )


@app.get("/api/shipments/{shipment_id}", response_model=ShipmentResponse)
async def get_shipment(
    shipment_id: str,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    """Get shipment details."""
    from src.db.repository import ShipmentRepository

    try:
        sid = UUID(shipment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shipment ID format")

    shipment_repo = ShipmentRepository(db)
    shipment = shipment_repo.get_by_id(sid)

    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    if shipment.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return ShipmentResponse(
        id=str(shipment.id),
        order_id=str(shipment.order_id) if shipment.order_id else None,
        tracking_number=shipment.tracking_number,
        carrier=shipment.carrier,
        service=shipment.service,
        rate_amount=shipment.rate_amount,
        label_url=shipment.label_url,
        status=shipment.status,
        estimated_delivery=shipment.estimated_delivery.isoformat() if shipment.estimated_delivery else None,
        created_at=shipment.created_at.isoformat() if shipment.created_at else None,
    )


@app.get("/api/shipments/{shipment_id}/tracking", response_model=TrackingResponse)
async def get_tracking(
    shipment_id: str,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> TrackingResponse:
    """Get tracking events for a shipment."""
    from src.db.repository import ShipmentRepository
    from src.easypost_client import TrackingError

    customer_id_str = str(customer.id)

    try:
        sid = UUID(shipment_id)
    except ValueError:
        raise create_error_response(
            status_code=400,
            error="Invalid shipment ID format",
            code=ErrorCode.VALIDATION_ERROR,
            customer_id=customer_id_str,
            endpoint="/api/shipments/{id}/tracking",
        )

    shipment_repo = ShipmentRepository(db)
    shipment = shipment_repo.get_by_id(sid)

    if not shipment:
        raise create_error_response(
            status_code=404,
            error="Shipment not found",
            code=ErrorCode.NOT_FOUND,
            customer_id=customer_id_str,
            endpoint="/api/shipments/{id}/tracking",
        )

    if shipment.customer_id != customer.id:
        raise create_error_response(
            status_code=403,
            error="Access denied",
            code=ErrorCode.ACCESS_DENIED,
            customer_id=customer_id_str,
            endpoint="/api/shipments/{id}/tracking",
        )

    # Get live tracking from carrier
    client = get_easypost_client()
    try:
        tracking = client.get_tracking(shipment.tracking_number, shipment.carrier)
    except TrackingError as e:
        raise create_error_response(
            status_code=502,
            error=e.message,
            code=ErrorCode.EASYPOST_TRACKING_ERROR,
            customer_id=customer_id_str,
            endpoint="/api/shipments/{id}/tracking",
            exc=e,
        )
    except Exception as e:
        raise create_error_response(
            status_code=500,
            error="Unable to fetch tracking information. Please try again.",
            code=ErrorCode.EASYPOST_TRACKING_ERROR,
            customer_id=customer_id_str,
            endpoint="/api/shipments/{id}/tracking",
            exc=e,
        )

    events = []
    for event in tracking.get("events", []):
        # Handle location as string or dict
        location = event.get("location")
        if isinstance(location, str):
            location = {"description": location}
        elif location is None:
            location = None

        events.append(TrackingEventResponse(
            status=event.get("status", ""),
            description=event.get("message", event.get("description", "")),
            location=location,
            occurred_at=event.get("datetime", ""),
        ))

    return TrackingResponse(
        tracking_number=shipment.tracking_number,
        carrier=shipment.carrier,
        status=tracking.get("status", "unknown"),
        estimated_delivery=tracking.get("estimated_delivery"),
        events=events,
    )


# ============================================================================
# Customer API
# ============================================================================

@app.get("/api/me", response_model=CustomerResponse)
async def get_me(
    customer=Depends(get_current_customer),
) -> CustomerResponse:
    """Get current customer info."""
    return CustomerResponse(
        id=str(customer.id),
        name=customer.name,
        shop_domain=customer.shop_domain,
        plan_tier=customer.plan_tier,
        labels_this_month=customer.labels_this_month,
        labels_limit=customer.labels_limit,
        labels_remaining=max(0, customer.labels_limit - customer.labels_this_month),
    )


@app.put("/api/me/preferences")
async def update_preferences(
    request: UpdatePreferencesRequest,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> dict:
    """Update customer preferences."""
    from src.db.repository import CustomerRepository

    customer_repo = CustomerRepository(db)

    # For now, just store preferences in default_from_address JSON field
    # In a real app, we'd have a separate preferences table
    current_address = customer.default_from_address or {}

    if request.default_carrier is not None:
        current_address["default_carrier"] = request.default_carrier
    if request.auto_cheapest is not None:
        current_address["auto_cheapest"] = request.auto_cheapest

    customer_repo.update(customer.id, {"default_from_address": current_address})

    return {"status": "ok"}


# ============================================================================
# Shopify OAuth API
# ============================================================================

@app.get("/auth/shopify")
async def shopify_auth_start(
    shop: str = Query(..., description="Shopify store domain (e.g., store.myshopify.com)"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Start Shopify OAuth flow.

    Redirects the merchant to Shopify's authorization page.
    """
    from src.auth.shopify import ShopifyOAuth
    from src.db.repository import CustomerRepository

    try:
        oauth = ShopifyOAuth()
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"OAuth not configured: {e}. Set SHOPIFY_API_KEY and SHOPIFY_API_SECRET.",
        )

    # Validate shop domain
    if not oauth.validate_shop_domain(shop):
        raise HTTPException(
            status_code=400,
            detail="Invalid shop domain. Must be in format: store.myshopify.com",
        )

    # Generate nonce for CSRF protection
    nonce = oauth.generate_nonce()

    # Store nonce in database (create or update customer record)
    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_shop_domain(shop)

    if customer:
        # Update existing customer with new nonce
        customer_repo.update(customer.id, {"shopify_nonce": nonce})
    else:
        # Create placeholder customer record
        customer = customer_repo.create({
            "shop_domain": shop,
            "name": shop.split(".")[0].title(),  # Temporary name from domain
            "email": "",
            "shopify_nonce": nonce,
        })

    # Build authorization URL and redirect
    auth_url = oauth.get_authorization_url(shop, nonce)
    return RedirectResponse(url=auth_url, status_code=302)


@app.get("/auth/shopify/callback")
async def shopify_auth_callback(
    request: Request,
    shop: str = Query(...),
    code: str = Query(...),
    state: str = Query(...),
    hmac: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Handle Shopify OAuth callback.

    Exchanges authorization code for access token and creates session.
    """
    from src.auth.shopify import ShopifyOAuth, verify_hmac
    from src.auth.crypto import encrypt_token
    from src.auth.jwt import create_session_token
    from src.db.repository import CustomerRepository

    try:
        oauth = ShopifyOAuth()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"OAuth not configured: {e}")

    # Verify HMAC signature
    query_params = dict(request.query_params)
    if not verify_hmac(query_params, oauth.config.api_secret):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    # Verify nonce matches
    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_shop_domain(shop)

    if not customer:
        raise HTTPException(status_code=400, detail="Shop not found. Start OAuth flow again.")

    if customer.shopify_nonce != state:
        raise HTTPException(status_code=400, detail="Invalid state parameter (CSRF detected)")

    # Exchange code for access token
    try:
        token_response = await oauth.exchange_code_for_token(shop, code)
    except Exception as e:
        logger.exception("Token exchange failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to obtain access token from Shopify")

    # Encrypt and store the access token
    encrypted_token = encrypt_token(token_response.access_token)

    # Update customer record
    customer_repo.update(customer.id, {
        "shopify_access_token": encrypted_token,
        "shopify_scope": token_response.scope,
        "shopify_nonce": None,  # Clear nonce after use
        "installed_at": datetime.now(timezone.utc),
        "uninstalled_at": None,  # Clear if reinstalling
        "token_validated_at": datetime.now(timezone.utc),  # Token just validated
        "token_invalid": 0,  # Clear invalid flag on successful re-auth
    })

    # Create JWT session token
    session_token = create_session_token(str(customer.id), shop)

    # Redirect to app with token (in production, use secure cookie or fragment)
    # For now, redirect to home with token in query param
    redirect_url = f"/?token={session_token}&shop={shop}"
    return RedirectResponse(url=redirect_url, status_code=302)


@app.post("/webhooks/shopify/uninstall")
async def shopify_uninstall_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Handle Shopify app/uninstalled webhook.

    Clears customer access token and marks as uninstalled.
    """
    import os
    from src.auth.shopify import verify_webhook_hmac
    from src.db.repository import CustomerRepository

    # Get webhook secret
    webhook_secret = os.getenv("SHOPIFY_API_SECRET", "")

    # Verify HMAC
    body = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")

    if not verify_webhook_hmac(body, hmac_header, webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Parse webhook payload
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    shop_domain = data.get("myshopify_domain") or data.get("domain")
    if not shop_domain:
        raise HTTPException(status_code=400, detail="Missing shop domain in webhook")

    # Update customer record
    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_shop_domain(shop_domain)

    if customer:
        customer_repo.update(customer.id, {
            "shopify_access_token": None,
            "shopify_scope": None,
            "uninstalled_at": datetime.now(timezone.utc),
        })
        logger.info("App uninstalled for shop: %s", shop_domain)

    return {"status": "ok"}


@app.get("/api/oauth/status", response_model=OAuthStatusResponse)
async def get_oauth_status(
    customer=Depends(get_current_customer),
) -> OAuthStatusResponse:
    """Get OAuth connection status for current customer."""
    from src.auth.crypto import decrypt_token

    has_token = bool(customer.shopify_access_token and decrypt_token(customer.shopify_access_token))

    scopes = None
    if customer.shopify_scope:
        scopes = [s.strip() for s in customer.shopify_scope.split(",")]

    return OAuthStatusResponse(
        connected=has_token,
        shop_domain=customer.shop_domain,
        installed_at=customer.installed_at.isoformat() if customer.installed_at else None,
        scopes=scopes,
    )


@app.post("/api/oauth/refresh", response_model=SessionTokenResponse)
async def refresh_oauth_token(
    authorization: Annotated[str | None, Header()] = None,
    customer=Depends(get_current_customer),
) -> SessionTokenResponse:
    """Refresh the JWT session token."""
    from src.auth.jwt import create_session_token, DEFAULT_EXPIRATION_HOURS

    token = create_session_token(str(customer.id), customer.shop_domain)

    return SessionTokenResponse(
        token=token,
        expires_in=DEFAULT_EXPIRATION_HOURS * 3600,  # Convert to seconds
        customer_id=str(customer.id),
        shop_domain=customer.shop_domain,
    )


@app.get("/api/shopify/reconnect")
async def shopify_reconnect(
    x_customer_id: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Initiate re-authentication flow for expired Shopify token.

    This endpoint bypasses the normal token_invalid check to allow
    customers with invalid tokens to re-authenticate.
    """
    from src.auth.shopify import ShopifyOAuth
    from src.db.repository import CustomerRepository

    customer_repo = CustomerRepository(db)
    customer_id = None

    # Get customer ID from auth (without the token_invalid check)
    if authorization and authorization.startswith("Bearer "):
        from src.auth.jwt import verify_session_token

        token = authorization[7:]
        session = verify_session_token(token)
        if session:
            try:
                customer_id = UUID(session.customer_id)
            except ValueError:
                raise HTTPException(status_code=401, detail="Invalid session token")
        else:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
    elif x_customer_id:
        try:
            customer_id = UUID(x_customer_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid customer ID format")
    else:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to reconnect",
        )

    customer = customer_repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get the shop domain to start OAuth flow
    shop = customer.shop_domain
    if not shop:
        raise HTTPException(
            status_code=400,
            detail="No shop domain associated with this customer",
        )

    try:
        oauth = ShopifyOAuth()
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"OAuth not configured: {e}. Set SHOPIFY_API_KEY and SHOPIFY_API_SECRET.",
        )

    # Generate new nonce and update customer
    nonce = oauth.generate_nonce()
    customer_repo.update(customer.id, {"shopify_nonce": nonce})

    # Redirect to Shopify authorization
    auth_url = oauth.get_authorization_url(shop, nonce)
    return RedirectResponse(url=auth_url, status_code=302)


# ============================================================================
# Health Check
# ============================================================================

@app.get("/api/health")
async def health() -> dict:
    """Health check endpoint."""
    from src.agent.agent import is_mock_mode
    from src.db.migrations import get_current_revision

    try:
        revision = get_current_revision()
    except Exception:
        revision = None

    return {
        "status": "ok",
        "mock_mode": is_mock_mode(),
        "db_revision": revision,
    }


# ============================================================================
# Static Files
# ============================================================================

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main chat UI."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse(
        content="<h1>Shipping Agent</h1><p>Static files not found. Run from project root.</p>",
        status_code=200,
    )


# ============================================================================
# Entry Point
# ============================================================================

def main():
    """Run the server."""
    import uvicorn
    uvicorn.run(
        "src.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
