"""Shipping, rates, and address validation endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_current_customer, get_easypost_client
from src.api.errors import create_error_response, ErrorCode
from src.api.schemas import (
    RateRequest,
    RateResponse,
    RatesResponse,
    CreateShipmentRequest,
    ShipmentResponse,
    ValidateAddressRequest,
    ValidateAddressResponse,
    StandardizedAddress,
    TrackingResponse,
    TrackingEventResponse,
)
from src.auth.crypto import decrypt_token
from src.auth.shopify import ShopifyAdminClient
from src.db.repository import OrderRepository, ShipmentRepository, CustomerRepository
from src.easypost_client import (
    Address,
    Parcel,
    RateError,
    ShipmentError,
    AddressValidationError,
    TrackingError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["shipping"])


@router.post("/rates", response_model=RatesResponse)
async def get_rates(
    request: RateRequest,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> RatesResponse:
    """Get shipping rates for an order or address."""
    customer_id_str = str(customer.id)
    client = get_easypost_client()

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


@router.post("/addresses/validate", response_model=ValidateAddressResponse)
async def validate_address(
    request: ValidateAddressRequest,
    customer=Depends(get_current_customer),
) -> ValidateAddressResponse:
    """Validate and standardize a shipping address."""
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


@router.post("/shipments", response_model=ShipmentResponse)
async def create_shipment(
    request: CreateShipmentRequest,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    """Create a shipment and purchase a label."""
    customer_id_str = str(customer.id)
    client = get_easypost_client()
    order_repo = OrderRepository(db)
    shipment_repo = ShipmentRepository(db)
    customer_repo = CustomerRepository(db)

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

    if order_id:
        order_repo.update_status(order_id, "shipped")

        order = order_repo.get_by_id(order_id)
        if order and order.shopify_order_id and customer.shopify_access_token:
            await _create_shopify_fulfillment(
                customer=customer,
                shopify_order_id=order.shopify_order_id,
                tracking_number=shipment.tracking_number,
                carrier=shipment.carrier,
            )

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


@router.get("/shipments/{shipment_id}", response_model=ShipmentResponse)
async def get_shipment(
    shipment_id: str,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> ShipmentResponse:
    """Get shipment details."""
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


@router.get("/shipments/{shipment_id}/tracking", response_model=TrackingResponse)
async def get_tracking(
    shipment_id: str,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> TrackingResponse:
    """Get tracking events for a shipment."""
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


async def _create_shopify_fulfillment(
    customer,
    shopify_order_id: str,
    tracking_number: str,
    carrier: str,
) -> bool:
    """Create a fulfillment in Shopify for a shipped order."""
    if not customer.shopify_access_token:
        logger.debug("Skipping Shopify fulfillment: no access token")
        return False

    access_token = decrypt_token(customer.shopify_access_token)
    if not access_token:
        logger.warning("Failed to decrypt Shopify token for customer %s", customer.id)
        return False

    carrier_map = {
        "USPS": "USPS",
        "UPS": "UPS",
        "FedEx": "FedEx",
        "DHL": "DHL Express",
        "DHL Express": "DHL Express",
    }
    tracking_company = carrier_map.get(carrier, carrier)

    try:
        shopify_client = ShopifyAdminClient(customer.shop_domain, access_token)
        fulfillment = await shopify_client.create_fulfillment(
            order_id=shopify_order_id,
            tracking_number=tracking_number,
            tracking_company=tracking_company,
            notify_customer=True,
        )
        logger.info(
            "Created Shopify fulfillment %s for order %s",
            fulfillment.id,
            shopify_order_id,
        )
        return True
    except Exception as e:
        logger.error(
            "Failed to create Shopify fulfillment for order %s: %s",
            shopify_order_id,
            e,
            exc_info=True,
        )
        return False
