"""JWT session token management."""

import os
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional

import jwt
from jwt.exceptions import InvalidTokenError


# Algorithm for JWT signing
ALGORITHM = "HS256"

# Default token expiration (24 hours)
DEFAULT_EXPIRATION_HOURS = 24


def _get_secret_key() -> str:
    """Get JWT signing secret from environment."""
    return os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")


@dataclass
class SessionPayload:
    """Payload data from a verified session token."""

    customer_id: str
    shop_domain: str
    exp: datetime
    iat: datetime


def create_session_token(
    customer_id: str,
    shop_domain: str,
    expiration_hours: int = DEFAULT_EXPIRATION_HOURS,
) -> str:
    """Create a JWT session token for an authenticated customer.

    Args:
        customer_id: UUID of the customer
        shop_domain: Shopify store domain
        expiration_hours: Token validity period in hours

    Returns:
        Encoded JWT token string
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(customer_id),
        "shop": shop_domain,
        "iat": now,
        "exp": now + timedelta(hours=expiration_hours),
    }

    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


def verify_session_token(token: str) -> Optional[SessionPayload]:
    """Verify and decode a session token.

    Args:
        token: JWT token string

    Returns:
        SessionPayload if valid, None if invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            _get_secret_key(),
            algorithms=[ALGORITHM],
        )

        return SessionPayload(
            customer_id=payload["sub"],
            shop_domain=payload["shop"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
        )
    except InvalidTokenError:
        return None


def refresh_session_token(token: str) -> Optional[str]:
    """Refresh a valid session token with a new expiration.

    Args:
        token: Existing JWT token

    Returns:
        New token if valid, None if invalid
    """
    session = verify_session_token(token)
    if session is None:
        return None

    return create_session_token(session.customer_id, session.shop_domain)
