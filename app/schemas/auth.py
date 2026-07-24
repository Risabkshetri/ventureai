"""Authentication schemas for request validation and response serialization."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """Schema for user registration request."""

    email: EmailStr
    password: str = Field(
        ..., min_length=6, description="Plain text password, must be at least 6 characters."
    )
    name: str = Field(..., min_length=1, description="The user's full name.")
    role: Literal["founder", "investor"] = Field(
        ..., description="Role must be either 'founder' or 'investor'."
    )


class UserLogin(BaseModel):
    """Schema for user login request."""

    email: EmailStr
    password: str


class UserProfile(BaseModel):
    """Schema representing the user profile."""

    id: str
    email: EmailStr
    name: str
    role: str
    bio: str | None = None
    headline: str | None = None
    profile_photo_url: str | None = None
    linkedin_url: str | None = None


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile details."""

    name: str = Field(..., min_length=1, description="The user's full name.")
    bio: str | None = Field(None, description="Short biography of the user.")
    headline: str | None = Field(None, description="Quick professional headline/introduction.")
    profile_photo_url: str | None = Field(None, description="URL of the founder's profile photo.")
    linkedin_url: str | None = Field(None, description="LinkedIn profile URL.")
    email: EmailStr | None = Field(None, description="New email address, if changing.")
    password: str | None = Field(
        None, min_length=6, description="New plain text password, if changing."
    )


class LoginResponse(BaseModel):
    """Schema for login response returning user profile instead of session tokens."""

    status: str = "success"
    user: UserProfile


class UserVerifyOTP(BaseModel):
    """Schema for OTP verification request."""

    email: EmailStr
    token: str = Field(..., min_length=6, description="OTP token, usually 6 digits")


class UserResendOTP(BaseModel):
    """Schema for OTP resend request."""

    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    """Schema for requesting a password reset email."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Schema for resetting password with OTP token."""

    email: EmailStr
    token: str = Field(..., min_length=6, description="OTP token from the reset email")
    new_password: str = Field(
        ..., min_length=6, description="New password, at least 6 characters."
    )

