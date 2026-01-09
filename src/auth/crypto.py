"""Token encryption utilities for secure storage of sensitive data."""

import os
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken


def _get_encryption_key() -> bytes:
    """Get or derive encryption key from environment.

    Uses ENCRYPTION_KEY if set (must be valid Fernet key),
    otherwise derives a key from SECRET_KEY.
    """
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if encryption_key:
        return encryption_key.encode()

    # Derive from SECRET_KEY if ENCRYPTION_KEY not set
    secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    # Fernet requires 32 url-safe base64-encoded bytes
    derived = hashlib.sha256(secret_key.encode()).digest()
    return base64.urlsafe_b64encode(derived)


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token for secure storage.

    Args:
        plaintext: The token to encrypt (e.g., Shopify access token)

    Returns:
        Base64-encoded encrypted string
    """
    if not plaintext:
        return ""

    key = _get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt_token(ciphertext: str) -> str | None:
    """Decrypt a stored token.

    Args:
        ciphertext: The encrypted token from storage

    Returns:
        Decrypted plaintext, or None if decryption fails
    """
    if not ciphertext:
        return None

    try:
        key = _get_encryption_key()
        f = Fernet(key)
        decrypted = f.decrypt(ciphertext.encode())
        return decrypted.decode()
    except InvalidToken:
        return None


def generate_encryption_key() -> str:
    """Generate a new Fernet encryption key.

    Use this to generate a key for ENCRYPTION_KEY env var.

    Returns:
        URL-safe base64-encoded 32-byte key
    """
    return Fernet.generate_key().decode()
