"""Shopify webhook handlers."""

import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.auth.shopify import verify_webhook_hmac
from src.db.repository import CustomerRepository, OrderRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/shopify", tags=["webhooks"])


@router.post("/uninstall")
async def shopify_uninstall_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Handle Shopify app/uninstalled webhook."""
    webhook_secret = os.getenv("SHOPIFY_API_SECRET", "")

    body = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")

    if not verify_webhook_hmac(body, hmac_header, webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    shop_domain = data.get("myshopify_domain") or data.get("domain")
    if not shop_domain:
        raise HTTPException(status_code=400, detail="Missing shop domain in webhook")

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


@router.post("/orders")
async def shopify_orders_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Handle Shopify order webhooks (orders/create, orders/updated, orders/cancelled)."""
    webhook_secret = os.getenv("SHOPIFY_API_SECRET", "")

    body = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")

    if not verify_webhook_hmac(body, hmac_header, webhook_secret):
        logger.warning("Invalid webhook signature for orders webhook")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    topic = request.headers.get("X-Shopify-Topic", "")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "")
    if not shop_domain:
        raise HTTPException(status_code=400, detail="Missing shop domain in webhook")

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_shop_domain(shop_domain)

    if not customer:
        logger.warning("Received order webhook for unknown shop: %s", shop_domain)
        return {"status": "ok", "message": "Shop not found"}

    order_repo = OrderRepository(db)
    shopify_order_id = str(data.get("id"))

    if topic == "orders/cancelled":
        existing_order = order_repo.get_by_shopify_id(customer.id, shopify_order_id)
        if existing_order:
            order_repo.update_status(existing_order.id, "cancelled")
            logger.info("Order %s cancelled for shop %s", shopify_order_id, shop_domain)
    else:
        order_data = parse_shopify_order_webhook(data, customer.id)
        existing_order = order_repo.get_by_shopify_id(customer.id, shopify_order_id)

        if existing_order:
            for key, value in order_data.items():
                if key not in ("customer_id", "shopify_order_id"):
                    setattr(existing_order, key, value)
            existing_order.updated_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("Order %s updated for shop %s", shopify_order_id, shop_domain)
        else:
            order_repo.create(order_data)
            logger.info("Order %s created for shop %s", shopify_order_id, shop_domain)

    return {"status": "ok"}


def parse_shopify_order_webhook(data: dict, customer_id: UUID) -> dict:
    """Parse Shopify order webhook data into order model format."""
    total_weight_grams = 0
    line_items = []
    for item in data.get("line_items", []):
        item_weight = item.get("grams", 0) * item.get("quantity", 1)
        total_weight_grams += item_weight
        line_items.append({
            "id": str(item.get("id")),
            "title": item.get("title"),
            "quantity": item.get("quantity", 1),
            "price": item.get("price"),
            "sku": item.get("sku"),
            "grams": item.get("grams", 0),
            "variant_title": item.get("variant_title"),
        })

    weight_oz = total_weight_grams / 28.3495

    shipping_address = None
    if data.get("shipping_address"):
        addr = data["shipping_address"]
        shipping_address = {
            "name": addr.get("name"),
            "street1": addr.get("address1"),
            "street2": addr.get("address2"),
            "city": addr.get("city"),
            "state": addr.get("province_code"),
            "zip": addr.get("zip"),
            "country": addr.get("country_code", "US"),
            "phone": addr.get("phone"),
        }

    fulfillment_status = data.get("fulfillment_status")
    if fulfillment_status is None:
        status = "unfulfilled"
    elif fulfillment_status == "fulfilled":
        status = "fulfilled"
    elif fulfillment_status == "partial":
        status = "partial"
    else:
        status = "unfulfilled"

    recipient_name = None
    if shipping_address:
        recipient_name = shipping_address.get("name")

    return {
        "customer_id": customer_id,
        "shopify_order_id": str(data.get("id")),
        "order_number": str(data.get("order_number", "")),
        "recipient_name": recipient_name,
        "status": status,
        "shipping_address": shipping_address,
        "line_items": line_items,
        "weight_oz": weight_oz,
    }
