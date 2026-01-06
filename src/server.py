"""FastAPI server for the shipping agent."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
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
class ChatRequest(BaseModel):
    """Chat request body."""
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    """Chat response body."""
    response: str
    session_id: str


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
    db: Session = Depends(get_db),
):
    """Get current customer from X-Customer-ID header."""
    from src.db.repository import CustomerRepository

    if not x_customer_id:
        raise HTTPException(status_code=401, detail="X-Customer-ID header required")

    try:
        customer_id = UUID(x_customer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid customer ID format")

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(customer_id)

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return customer


def get_optional_customer(
    x_customer_id: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
):
    """Get current customer if header provided, otherwise None."""
    from src.db.repository import CustomerRepository

    if not x_customer_id:
        return None

    try:
        customer_id = UUID(x_customer_id)
    except ValueError:
        return None

    customer_repo = CustomerRepository(db)
    return customer_repo.get_by_id(customer_id)


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
        raise HTTPException(status_code=400, detail="Message cannot be empty")

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
    except Exception as e:
        logger.exception("Chat error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


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
    from src.easypost_client import Address, Parcel

    client = get_easypost_client()

    # Get address from order or request
    if request.order_id:
        try:
            oid = UUID(request.order_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid order ID format")

        order_repo = OrderRepository(db)
        order = order_repo.get_by_id(oid)

        if not order or order.customer_id != customer.id:
            raise HTTPException(status_code=404, detail="Order not found")

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
            raise HTTPException(
                status_code=400,
                detail="Either order_id or (to_city, to_state, to_zip, weight_oz) required",
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting rates: {e}")

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


@app.post("/api/shipments", response_model=ShipmentResponse)
async def create_shipment(
    request: CreateShipmentRequest,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    """Create a shipment and purchase a label."""
    from src.db.repository import OrderRepository, ShipmentRepository, CustomerRepository
    from src.easypost_client import Address, Parcel

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
            raise HTTPException(status_code=400, detail="Invalid order ID format")

        order = order_repo.get_by_id(order_id)
        if not order or order.customer_id != customer.id:
            raise HTTPException(status_code=404, detail="Order not found")

    # Check label limit
    if customer.labels_this_month >= customer.labels_limit:
        raise HTTPException(
            status_code=403,
            detail=f"Label limit reached ({customer.labels_limit}/month). Upgrade your plan.",
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating shipment: {e}")

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

    # Get live tracking from carrier
    client = get_easypost_client()
    try:
        tracking = client.get_tracking(shipment.tracking_number, shipment.carrier)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting tracking: {e}")

    events = []
    for event in tracking.get("events", []):
        events.append(TrackingEventResponse(
            status=event.get("status", ""),
            description=event.get("message", event.get("description", "")),
            location=event.get("location"),
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
