import hashlib
import re
import secrets
from typing import Tuple
import argon2
from argon2.exceptions import VerifyMismatchError

# Argon2id hasher configured with OWASP recommendations
# time_cost=2, memory_cost=65536 (64MB), parallelism=1, hash_len=32
_hasher = argon2.PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
    type=argon2.Type.ID,
)

# Password requirement: at least 9 characters, at least 1 uppercase, at least 1 lowercase, at least 1 special character
SPECIAL_CHARS = set("!@#$%^&*()_+-=[]{}|;:,.<>?/~`'\"\\")


def normalize_email(email: str) -> str:
    """Trim whitespace and convert to lowercase."""
    return email.strip().lower()


def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plain password against an Argon2id hash."""
    try:
        return _hasher.verify(hashed_password, password)
    except (VerifyMismatchError, Exception):
        return False


def validate_password_complexity(password: str) -> Tuple[bool, str]:
    """
    Validate that password meets the brief's requirements:
    - At least 9 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one special character
    """
    if len(password) < 9:
        return False, "Password must be at least 9 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c in SPECIAL_CHARS for c in password):
        return False, "Password must contain at least one special character"
    return True, ""


def generate_secure_token(nbytes: int = 32) -> str:
    """Generate a high-entropy URL-safe bearer token."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Compute SHA-256 hex digest of a bearer token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
