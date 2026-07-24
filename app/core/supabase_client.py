"""Supabase Client initialization and authentication utilities."""

import hashlib
import os

from supabase import Client, create_client

from app.core.config import settings

# Client used for public operations and validated requests.
# This client gets mutated with the user's JWT token and enforces RLS.
supabase_client: Client = create_client(
    supabase_url=str(settings.SUPABASE_URL), supabase_key=str(settings.SUPABASE_ANON_KEY)
)

# Client used for system-level operations that need to bypass RLS policies.
# This client uses the service role key and is never mutated.
supabase_service_client: Client = create_client(
    supabase_url=str(settings.SUPABASE_URL), supabase_key=str(settings.SUPABASE_SERVICE_ROLE_KEY)
)


def validate_user_jwt(token: str):
    """Validate a user's JWT against Supabase Auth.

    This helper calls `supabase_client.auth.get_user(token)` which communicates
    directly with the Supabase Auth server.

    Args:
        token: The Bearer JWT token from the Authorization header.

    Returns:
        The User object from Supabase if verification is successful.

    Raises:
        Exception: If token validation fails.
    """
    response = supabase_client.auth.get_user(token)
    if not response or not response.user:
        raise ValueError("No user returned in authentication response.")
    return response.user


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256.

    Since Supabase Auth handles the primary password hashing and authentication
    internally, this is used to populate the `password_hash` field in the
    `public.users` table to satisfy the NOT NULL constraint.

    Args:
        password: The plain-text password.

    Returns:
        A serialized hash string.
    """
    salt = os.urandom(16)
    db_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return f"pbkdf2_sha256$100000${salt.hex()}${db_hash.hex()}"
