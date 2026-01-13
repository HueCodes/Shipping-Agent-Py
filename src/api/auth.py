"""Authentication and OAuth endpoints."""

import logging
import os
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_current_customer
from src.api.schemas import (
    CustomerResponse,
    UpdatePreferencesRequest,
    OAuthStatusResponse,
    SessionTokenResponse,
)
from src.auth.shopify import ShopifyOAuth, verify_hmac
from src.auth.crypto import encrypt_token, decrypt_token
from src.auth.jwt import create_session_token, verify_session_token, DEFAULT_EXPIRATION_HOURS
from src.db.repository import CustomerRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


@router.get("/api/me", response_model=CustomerResponse)
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


@router.put("/api/me/preferences")
async def update_preferences(
    request: UpdatePreferencesRequest,
    customer=Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> dict:
    """Update customer preferences."""
    customer_repo = CustomerRepository(db)

    current_address = customer.default_from_address or {}

    if request.default_carrier is not None:
        current_address["default_carrier"] = request.default_carrier
    if request.auto_cheapest is not None:
        current_address["auto_cheapest"] = request.auto_cheapest

    customer_repo.update(customer.id, {"default_from_address": current_address})

    return {"status": "ok"}


@router.get("/auth/shopify")
async def shopify_auth_start(
    shop: str = Query(..., description="Shopify store domain (e.g., store.myshopify.com)"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Start Shopify OAuth flow."""
    try:
        oauth = ShopifyOAuth()
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"OAuth not configured: {e}. Set SHOPIFY_API_KEY and SHOPIFY_API_SECRET.",
        )

    if not oauth.validate_shop_domain(shop):
        raise HTTPException(
            status_code=400,
            detail="Invalid shop domain. Must be in format: store.myshopify.com",
        )

    nonce = oauth.generate_nonce()

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_shop_domain(shop)

    if customer:
        customer_repo.update(customer.id, {"shopify_nonce": nonce})
    else:
        customer = customer_repo.create({
            "shop_domain": shop,
            "name": shop.split(".")[0].title(),
            "email": "",
            "shopify_nonce": nonce,
        })

    auth_url = oauth.get_authorization_url(shop, nonce)
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/auth/shopify/callback")
async def shopify_auth_callback(
    request: Request,
    shop: str = Query(...),
    code: str = Query(...),
    state: str = Query(...),
    hmac: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Handle Shopify OAuth callback."""
    try:
        oauth = ShopifyOAuth()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"OAuth not configured: {e}")

    query_params = dict(request.query_params)
    if not verify_hmac(query_params, oauth.config.api_secret):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_shop_domain(shop)

    if not customer:
        raise HTTPException(status_code=400, detail="Shop not found. Start OAuth flow again.")

    if customer.shopify_nonce != state:
        raise HTTPException(status_code=400, detail="Invalid state parameter (CSRF detected)")

    try:
        token_response = await oauth.exchange_code_for_token(shop, code)
    except Exception as e:
        logger.exception("Token exchange failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to obtain access token from Shopify")

    encrypted_token = encrypt_token(token_response.access_token)

    customer_repo.update(customer.id, {
        "shopify_access_token": encrypted_token,
        "shopify_scope": token_response.scope,
        "shopify_nonce": None,
        "installed_at": datetime.now(timezone.utc),
        "uninstalled_at": None,
        "token_validated_at": datetime.now(timezone.utc),
        "token_invalid": 0,
    })

    session_token = create_session_token(str(customer.id), shop)

    redirect_url = f"/?token={session_token}&shop={shop}"
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/api/oauth/status", response_model=OAuthStatusResponse)
async def get_oauth_status(
    customer=Depends(get_current_customer),
) -> OAuthStatusResponse:
    """Get OAuth connection status for current customer."""
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


@router.post("/api/oauth/refresh", response_model=SessionTokenResponse)
async def refresh_oauth_token(
    authorization: Annotated[str | None, Header()] = None,
    customer=Depends(get_current_customer),
) -> SessionTokenResponse:
    """Refresh the JWT session token."""
    token = create_session_token(str(customer.id), customer.shop_domain)

    return SessionTokenResponse(
        token=token,
        expires_in=DEFAULT_EXPIRATION_HOURS * 3600,
        customer_id=str(customer.id),
        shop_domain=customer.shop_domain,
    )


@router.get("/api/shopify/reconnect")
async def shopify_reconnect(
    x_customer_id: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Initiate re-authentication flow for expired Shopify token."""
    customer_repo = CustomerRepository(db)
    customer_id = None

    if authorization and authorization.startswith("Bearer "):
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

    nonce = oauth.generate_nonce()
    customer_repo.update(customer.id, {"shopify_nonce": nonce})

    auth_url = oauth.get_authorization_url(shop, nonce)
    return RedirectResponse(url=auth_url, status_code=302)
