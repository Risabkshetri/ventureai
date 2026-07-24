"""Authentication API endpoints for registration and login."""

import contextlib
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from supabase import create_client

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.supabase_client import hash_password, supabase_client, supabase_service_client
from app.schemas.auth import (
    LoginResponse,
    UserLogin,
    UserProfile,
    UserRegister,
    UserProfileUpdate,
    UserVerifyOTP,
    UserResendOTP,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)

router = APIRouter()



def _cookie_secure() -> bool:
    return not settings.is_development


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new founder or investor user",

)
async def register(register_data: UserRegister):
    """Register a new user.

    Creates a Supabase Auth user first. Then inserts a matching row in the
    public.users table. If the database insert fails, the created Auth user is
    deleted to avoid orphaned accounts.
    """
    # Enforce validation of role to reject admin just to be explicit
    # (Pydantic Literal already rejects non-matching values at schema level)
    if register_data.role not in ("founder", "investor"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public registration is only allowed for 'founder' or 'investor' roles.",
        )

    # 1. Create the Supabase Auth user
    try:
        if settings.AUTO_CONFIRM_EMAIL:
            # Bypass email confirmation (for development/testing)
            auth_response = supabase_service_client.auth.admin.create_user(
                {
                    "email": register_data.email,
                    "password": register_data.password,
                    "email_confirm": True,
                    "user_metadata": {
                        "name": register_data.name,
                        "role": register_data.role,
                    },
                }
            )
        else:
            # Standard signup requiring email verification/OTP
            auth_response = supabase_client.auth.sign_up(
                {
                    "email": register_data.email,
                    "password": register_data.password,
                    "options": {
                        "data": {
                            "name": register_data.name,
                            "role": register_data.role,
                        }
                    }
                }
            )
    except Exception as e:
        err_str = str(e).lower()
        if "already registered" in err_str or "already exists" in err_str or "23505" in err_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email address already exists. Please log in instead.",
            ) from e
        if "11001" in err_str or "getaddrinfo failed" in err_str or "max retries exceeded" in err_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Network error: Unable to connect to the authentication service. Please check your internet connection.",
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Supabase Auth user creation failed: {e!s}",
        ) from e

    if not auth_response or not auth_response.user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supabase Auth failed to return the created user.",
        )

    user_id = auth_response.user.id

    # 2. Insert user details into the public.users table
    try:
        password_hash = hash_password(register_data.password)

        supabase_service_client.table("users").insert(
            {
                "id": user_id,
                "name": register_data.name,
                "email": register_data.email,
                "password_hash": password_hash,
                "role": register_data.role,
            }
        ).execute()
    except Exception as db_err:
        # Rollback: Clean up/delete the newly created Supabase Auth user on failure
        with contextlib.suppress(Exception):
            supabase_service_client.auth.admin.delete_user(user_id)

        err_str = str(db_err).lower()
        if "already exists" in err_str or "duplicate key" in err_str or "23505" in err_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email address already exists. Please log in instead.",
            ) from db_err

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database user record registration failed: {db_err!s}",
        ) from db_err

    requires_verification = not settings.AUTO_CONFIRM_EMAIL
    message = "User registered successfully."
    if requires_verification:
        message += " Please check your email for the verification OTP code."

    return {
        "status": "success",
        "message": message,
        "requires_verification": requires_verification,
        "user": {
            "id": user_id,
            "email": register_data.email,
            "name": register_data.name,
            "role": register_data.role,
        },
    }


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login user and set secure httpOnly cookie",
)
async def login(login_data: UserLogin, response: Response):
    """Authenticate a user using email and password.

    Sets the session token in an httpOnly secure cookie and returns the user profile.
    """
    try:
        auth_response = supabase_client.auth.sign_in_with_password(
            {"email": login_data.email, "password": login_data.password}
        )
    except Exception as e:
        err_str = str(e).lower()
        if "11001" in err_str or "getaddrinfo failed" in err_str or "max retries exceeded" in err_str:
            detail = "Network error: Unable to connect to the authentication service. Please check your internet connection."
        else:
            detail = f"Authentication failed: {e!s}"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        ) from e

    if not auth_response or not auth_response.session or not auth_response.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login failed. Verify your email is confirmed or check credentials.",
        )

    session = auth_response.session
    user_id = auth_response.user.id

    # Query the user profile from the database to ensure sync
    try:
        db_res = (
            supabase_client.table("users")
            .select("id", "email", "name", "role", "bio", "headline", "profile_photo_url", "linkedin_url")
            .eq("id", user_id)
            .execute()
        )
        if not db_res.data or not isinstance(db_res.data[0], dict):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User record not found in database.",
            )
        user_info = cast(dict[str, Any], db_res.data[0])
    except HTTPException:
        raise
    except Exception as e:
        err_str = str(e).lower()
        if "11001" in err_str or "getaddrinfo failed" in err_str or "max retries exceeded" in err_str:
            detail = "Network error: Unable to connect to the database. Please check your internet connection."
        else:
            detail = f"Database synchronization failed: {e!s}"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        ) from e

    # Set access token cookie
    response.set_cookie(
        key="access_token",
        value=session.access_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=session.expires_in,
        path="/",
    )

    # Set refresh token cookie as well
    if session.refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=session.refresh_token,
            httponly=True,
            secure=_cookie_secure(),
            samesite="lax",
            max_age=session.expires_in * 10,
            path="/",
        )

    return LoginResponse(
        status="success",
        user=UserProfile(
            id=user_info["id"],
            email=user_info["email"],
            name=user_info.get("name") or "",
            role=user_info["role"],
            bio=user_info.get("bio"),
            headline=user_info.get("headline"),
            profile_photo_url=user_info.get("profile_photo_url"),
            linkedin_url=user_info.get("linkedin_url"),
        ),
    )


@router.get(
    "/oauth/google",
    summary="Get Google OAuth authorization URL and redirect",
)
async def google_oauth(role: str = "founder", redirect_url: str = "http://localhost:5173"):
    """Initiate Google OAuth login/registration via Supabase."""
    try:
        if role not in ("founder", "investor"):
            role = "founder"
        callback_uri = f"http://localhost:8000/auth/callback?role={role}&redirect_url={redirect_url}"
        res = supabase_client.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": callback_uri,
            }
        })
        if not res or not res.url:
            raise HTTPException(status_code=500, detail="Failed to get Google OAuth URL from Supabase.")
        return RedirectResponse(url=res.url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate Google OAuth: {e!s}",
        ) from e


@router.get(
    "/callback",
    summary="Handle OAuth callback from Supabase/Google",
)
async def oauth_callback(code: str, role: str = "founder", redirect_url: str = "http://localhost:5173"):
    """Exchange OAuth code for session, sync user in database, set httpOnly cookies, and redirect to dashboard."""
    try:
        auth_response = supabase_client.auth.exchange_code_for_session({"auth_code": code})  # type: ignore
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OAuth code exchange failed: {e!s}",
        ) from e

    if not auth_response or not auth_response.session or not auth_response.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuth login failed. Session could not be created.",
        )

    session = auth_response.session
    user = auth_response.user
    user_id = user.id

    if role not in ("founder", "investor"):
        role = "founder"

    # Query or insert user into public.users table using service client to bypass RLS
    try:
        db_res = supabase_service_client.table("users").select("*").eq("id", user_id).execute()
        
        # If not found by ID, check by email (handles users who registered via email/password previously)
        if not db_res.data and user.email:
            email_res = supabase_service_client.table("users").select("*").eq("email", user.email).execute()
            if email_res.data:
                try:
                    supabase_service_client.table("users").update({"id": user_id, "password_hash": "oauth_google"}).eq("email", user.email).execute()
                except Exception:
                    pass
                db_res = email_res

        if not db_res.data:
            # First time logging in with OAuth! Create record in public.users
            name = (
                user.user_metadata.get("full_name")
                or user.user_metadata.get("name")
                or (user.email.split("@")[0] if user.email else "User")
            )
            try:
                supabase_service_client.table("users").insert({
                    "id": user_id,
                    "email": user.email,
                    "name": name,
                    "password_hash": "oauth_google",
                    "role": role,
                }).execute()
            except Exception as ins_err:
                if "23505" in str(ins_err) or "already exists" in str(ins_err).lower() or "duplicate key" in str(ins_err).lower():
                    # Fallback: update existing record to link OAuth ID
                    supabase_service_client.table("users").update({"id": user_id, "password_hash": "oauth_google"}).eq("email", user.email).execute()
                    email_res = supabase_service_client.table("users").select("*").eq("email", user.email).execute()
                    if email_res.data:
                        db_res = email_res
                else:
                    raise ins_err
        
        if db_res and db_res.data:
            db_data: Any = db_res.data
            # Use their existing role from db if they are already registered
            existing_user = db_data[0]
            if isinstance(existing_user, dict) and existing_user.get("role"):
                role = existing_user["role"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database synchronization failed during OAuth: {e!s}",
        ) from e

    # Determine redirect destination based on role
    target_dashboard = f"{redirect_url}/founder/dashboard" if role == "founder" else f"{redirect_url}/investor/dashboard"
    redirect_res = RedirectResponse(url=target_dashboard)

    # Set access_token cookie
    redirect_res.set_cookie(
        key="access_token",
        value=session.access_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=session.expires_in,
        path="/",
    )

    # Set refresh_token cookie
    if session.refresh_token:
        redirect_res.set_cookie(
            key="refresh_token",
            value=session.refresh_token,
            httponly=True,
            secure=_cookie_secure(),
            samesite="lax",
            max_age=session.expires_in * 10,
            path="/",
        )

    return redirect_res


@router.get(
    "/me",
    response_model=UserProfile,
    summary="Get current user profile",
)
async def get_me(current_user: dict = Depends(get_current_user)):  # noqa: B008
    """Fetch the authenticated user's profile information."""
    return UserProfile(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user.get("name") or "",
        role=current_user["role"],
        bio=current_user.get("bio"),
        headline=current_user.get("headline"),
        profile_photo_url=current_user.get("profile_photo_url"),
        linkedin_url=current_user.get("linkedin_url"),
    )


@router.put(
    "/profile",
    response_model=UserProfile,
    summary="Update the authenticated user's profile details",
)
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),  # noqa: B008
):
    """Updates user name, bio, email, and password.
    
    If email or password is changed, it is updated in Supabase Auth via the admin API.
    Updates the fields in the public.users database table.
    """
    user_id = current_user["id"]
    new_email = profile_data.email
    new_password = profile_data.password

    # 1. Update Supabase Auth if credentials changed
    auth_updates = {}
    if new_email and new_email != current_user["email"]:
        # Verify email is not already taken in the public database
        existing_res = (
            supabase_client.table("users")
            .select("id")
            .eq("email", new_email)
            .execute()
        )
        if existing_res.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already in use by another user."
            )
        auth_updates["email"] = new_email

    if new_password:
        auth_updates["password"] = new_password

    if auth_updates:
        try:
            supabase_service_client.auth.admin.update_user_by_id(user_id, auth_updates)  # type: ignore
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update authentication credentials: {e!s}"
            ) from e

    # 2. Update details in public.users table
    db_updates = {
        "name": profile_data.name,
        "bio": profile_data.bio,
        "headline": profile_data.headline,
        "profile_photo_url": profile_data.profile_photo_url,
        "linkedin_url": profile_data.linkedin_url,
    }
    if new_email and new_email != current_user["email"]:
        db_updates["email"] = new_email
    if new_password:
        db_updates["password_hash"] = hash_password(new_password)

    try:
        db_res = (
            supabase_client.table("users")
            .update(db_updates)
            .eq("id", user_id)
            .execute()
        )
        if not db_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User database record not found."
            )
        updated_user = cast(dict[str, Any], db_res.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database update failed: {e!s}"
        ) from e

    return UserProfile(
        id=updated_user["id"],
        email=updated_user["email"],
        name=updated_user.get("name") or "",
        role=updated_user["role"],
        bio=updated_user.get("bio"),
        headline=updated_user.get("headline"),
        profile_photo_url=updated_user.get("profile_photo_url"),
        linkedin_url=updated_user.get("linkedin_url"),
    )


@router.post(
    "/verify-otp",
    response_model=LoginResponse,
    summary="Verify signup OTP and set session cookies",
)
async def verify_otp(verify_data: UserVerifyOTP, response: Response):
    """Verify the registration OTP code sent to the user's email.

    On success, logs the user in by setting session cookies.
    """
    try:
        auth_response = supabase_client.auth.verify_otp(
            {
                "email": verify_data.email,
                "token": verify_data.token,
                "type": "signup",
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Verification failed: {e!s}",
        ) from e

    if not auth_response or not auth_response.session or not auth_response.user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification failed. Invalid or expired OTP.",
        )

    session = auth_response.session
    user_id = auth_response.user.id

    # Query the user profile from the database to ensure sync
    try:
        db_res = (
            supabase_client.table("users")
            .select("id", "email", "name", "role", "bio", "headline", "profile_photo_url", "linkedin_url")
            .eq("id", user_id)
            .execute()
        )
        if not db_res.data or not isinstance(db_res.data[0], dict):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User record not found in database.",
            )
        user_info = cast(dict[str, Any], db_res.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Database synchronization failed: {e!s}",
        ) from e

    # Set access token cookie
    response.set_cookie(
        key="access_token",
        value=session.access_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=session.expires_in,
        path="/",
    )

    # Set refresh token cookie as well
    if session.refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=session.refresh_token,
            httponly=True,
            secure=_cookie_secure(),
            samesite="lax",
            max_age=session.expires_in * 10,
            path="/",
        )

    return LoginResponse(
        status="success",
        user=UserProfile(
            id=user_info["id"],
            email=user_info["email"],
            name=user_info.get("name") or "",
            role=user_info["role"],
            bio=user_info.get("bio"),
            headline=user_info.get("headline"),
            profile_photo_url=user_info.get("profile_photo_url"),
            linkedin_url=user_info.get("linkedin_url"),
        ),
    )


@router.post(
    "/resend-otp",
    summary="Resend registration verification OTP",
)
async def resend_otp(resend_data: UserResendOTP):
    """Resend signup verification email."""
    try:
        supabase_client.auth.resend(
            {
                "type": "signup",
                "email": resend_data.email,
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to resend verification: {e!s}",
        ) from e

    return {"status": "success", "message": "Verification email resent successfully."}


@router.post(
    "/forgot-password",
    summary="Send password reset email with OTP",
)
async def forgot_password(data: ForgotPasswordRequest):
    """Send a password reset OTP to the user's email via Supabase."""
    try:
        supabase_client.auth.reset_password_email(data.email)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send reset email: {e!s}",
        ) from e

    return {
        "status": "success",
        "message": "If an account exists with this email, a password reset code has been sent.",
    }


@router.post(
    "/reset-password",
    summary="Reset password using OTP token",
)
async def reset_password(data: ResetPasswordRequest):
    """Verify the recovery OTP and set a new password."""
    # Create an ephemeral client for this request to avoid modifying global client session
    ephemeral_client = create_client(
        settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY
    )

    # Step 1: Verify the recovery OTP (this logs the ephemeral client in)
    try:
        auth_response = ephemeral_client.auth.verify_otp(
            {
                "email": data.email,
                "token": data.token,
                "type": "recovery",
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or expired reset code: {e!s}",
        ) from e

    if not auth_response or not auth_response.user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code.",
        )

    user_id = auth_response.user.id

    # Step 2: Update the password using the user's new session
    try:
        ephemeral_client.auth.update_user({"password": data.new_password})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update password: {e!s}",
        ) from e

    # Step 3: Update password hash in public.users table (using global service_role client)
    try:
        supabase_client.table("users").update(
            {"password_hash": hash_password(data.new_password)}
        ).eq("id", user_id).execute()
    except Exception:
        pass  # Non-critical, auth password is already updated

    return {
        "status": "success",
        "message": "Password has been reset successfully. You can now log in with your new password.",
    }


@router.post(
    "/logout",
    summary="Logout user and clear session cookies",
)
async def logout(response: Response):
    """Logs out the user and clears authentication cookies."""
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
    )
    response.delete_cookie(
        key="refresh_token",
        path="/",
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
    )
    return {"status": "success", "message": "Logged out successfully."}
