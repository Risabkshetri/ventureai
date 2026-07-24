"""FastAPI dependencies for authentication and authorization."""

from fastapi import Depends, HTTPException, Request, status

from app.core.supabase_client import supabase_client, validate_user_jwt


async def get_current_user(request: Request) -> dict:
    """Extracts and validates the bearer token from the Authorization header.

    Queries the `public.users` table to fetch the user's current role and info.

    Args:
        request: The incoming FastAPI request.

    Returns:
        A dictionary containing the user's `id`, `email`, and `role`.

    Raises:
        HTTPException: 401 if token is missing, invalid, or database record is missing.
    """
    # 1. Retrieve access token from cookies first, then fallback to Authorization header
    token = request.cookies.get("access_token")

    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate token against Supabase Auth
    try:
        auth_user = validate_user_jwt(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired credentials: {e!s}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # Fetch corresponding database record in public.users to get correct role and name
    try:
        response = (
            supabase_client.table("users")
            .select("id", "email", "name", "role", "bio", "headline", "profile_photo_url", "linkedin_url")
            .eq("id", auth_user.id)
            .execute()
        )
        if not response.data or not isinstance(response.data[0], dict):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User record not found in database.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Database retrieval failed: {e!s}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def require_role(role: str):
    """Dependency factory to restrict access to a specific role.

    Args:
        role: The role required to access the endpoint ('founder', 'investor', 'admin').

    Returns:
        A dependency function that raises 403 if roles do not match.
    """

    async def role_checker(
        current_user: dict = Depends(get_current_user),  # noqa: B008
    ) -> dict:
        if current_user.get("role") != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: role '{role}' is required.",
            )
        return current_user

    return role_checker
