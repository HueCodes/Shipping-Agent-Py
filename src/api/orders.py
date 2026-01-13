"""Order management endpoints."""

import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_current_customer
from src.api.errors import create_error_response, ErrorCode
from src.api.schemas import OrderResponse, OrderListResponse, OrderSyncResponse
from src.auth.shopify import ShopifyAdminClient
from src.auth.crypto import decrypt_token
from src.db.repository import OrderRepository, ShipmentRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("", response_model=OrderListResponse)
async def list_orders(
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
    limit: int = 50,
    status: str | None = None,
    search: str | None = None,
) -> OrderListResponse:
    """List orders for the current customer."""
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


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> OrderResponse:
    """Get order details."""
    try:
        oid = UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order ID format")

    order_repo = OrderRepository(db)
    order = order_repo.get_by_id(oid)

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

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


@router.post("/{order_id}/fulfill")
async def fulfill_order(
    order_id: str,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> dict:
    """Mark order as fulfilled (shipped)."""
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


@router.post("/sync", response_model=OrderSyncResponse)
async def sync_orders(
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
    status: str = "unfulfilled",
    limit: int = 50,
) -> OrderSyncResponse:
    """Sync orders from Shopify."""
    customer_id_str = str(customer.id)

    if not customer.shopify_access_token:
        raise create_error_response(
            status_code=400,
            error="Shopify not connected",
            code=ErrorCode.SHOPIFY_TOKEN_INVALID,
            detail="Connect your Shopify store to sync orders",
            customer_id=customer_id_str,
            endpoint="/api/orders/sync",
        )

    access_token = decrypt_token(customer.shopify_access_token)
    if not access_token:
        raise create_error_response(
            status_code=400,
            error="Invalid Shopify token",
            code=ErrorCode.SHOPIFY_TOKEN_INVALID,
            detail="Please reconnect your Shopify store",
            customer_id=customer_id_str,
            endpoint="/api/orders/sync",
        )

    shopify_client = ShopifyAdminClient(customer.shop_domain, access_token)

    try:
        shopify_orders = await shopify_client.get_orders(status=status, limit=min(limit, 250))
    except Exception as e:
        logger.error("Failed to fetch orders from Shopify: %s", e, exc_info=True)
        raise create_error_response(
            status_code=502,
            error="Failed to fetch orders from Shopify",
            code=ErrorCode.SHOPIFY_API_ERROR,
            detail="Please try again later",
            customer_id=customer_id_str,
            endpoint="/api/orders/sync",
            exc=e,
        )

    order_repo = OrderRepository(db)
    created_count = 0
    updated_count = 0
    errors = []

    for shopify_order in shopify_orders:
        try:
            order_data = {
                "customer_id": customer.id,
                "shopify_order_id": shopify_order.id,
                "order_number": str(shopify_order.order_number),
                "recipient_name": shopify_order.shipping_address.get("name") if shopify_order.shipping_address else None,
                "status": "unfulfilled" if shopify_order.fulfillment_status is None else (
                    "fulfilled" if shopify_order.fulfillment_status == "fulfilled" else "partial"
                ),
                "shipping_address": shopify_order.shipping_address,
                "line_items": shopify_order.line_items,
                "weight_oz": shopify_order.total_weight / 28.3495,
            }

            existing_order = order_repo.get_by_shopify_id(customer.id, shopify_order.id)

            if existing_order:
                for key, value in order_data.items():
                    if key not in ("customer_id", "shopify_order_id"):
                        setattr(existing_order, key, value)
                existing_order.updated_at = datetime.now(timezone.utc)
                db.commit()
                updated_count += 1
            else:
                order_repo.create(order_data)
                created_count += 1

        except Exception as e:
            error_msg = f"Failed to sync order {shopify_order.id}: {str(e)}"
            logger.warning(error_msg)
            errors.append(error_msg)

    logger.info(
        "Order sync completed for %s: %d created, %d updated, %d errors",
        customer.shop_domain, created_count, updated_count, len(errors)
    )

    return OrderSyncResponse(
        synced=created_count + updated_count,
        created=created_count,
        updated=updated_count,
        errors=errors[:10],
    )


@router.post("/webhooks/register")
async def register_order_webhooks(
    customer=Depends(get_current_customer),
) -> dict:
    """Register Shopify webhooks for order events."""
    customer_id_str = str(customer.id)

    if not customer.shopify_access_token:
        raise create_error_response(
            status_code=400,
            error="Shopify not connected",
            code=ErrorCode.SHOPIFY_TOKEN_INVALID,
            customer_id=customer_id_str,
            endpoint="/api/orders/webhooks/register",
        )

    access_token = decrypt_token(customer.shopify_access_token)
    if not access_token:
        raise create_error_response(
            status_code=400,
            error="Invalid Shopify token",
            code=ErrorCode.SHOPIFY_TOKEN_INVALID,
            customer_id=customer_id_str,
            endpoint="/api/orders/webhooks/register",
        )

    app_url = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")

    shopify_client = ShopifyAdminClient(customer.shop_domain, access_token)

    try:
        registered = await shopify_client.register_webhooks(app_url)
    except Exception as e:
        logger.error("Failed to register webhooks: %s", e, exc_info=True)
        raise create_error_response(
            status_code=502,
            error="Failed to register webhooks",
            code=ErrorCode.SHOPIFY_API_ERROR,
            customer_id=customer_id_str,
            endpoint="/api/orders/webhooks/register",
            exc=e,
        )

    return {
        "status": "ok",
        "webhooks_registered": len(registered),
        "webhooks": [{"topic": w.get("topic"), "id": w.get("id")} for w in registered],
    }
