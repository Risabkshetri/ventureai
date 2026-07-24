"""Application-wide configuration via pydantic-settings.

All environment variables are loaded from the .env file at the backend root.
Required variables with no default will cause a ValidationError at startup
(fail-fast) if they are missing or empty in the environment.
"""

from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Alias for a non-empty required string — rejects both missing and "" values.
NonEmptyStr = Annotated[str, Field(min_length=1)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Extra env vars in .env that aren't fields here won't raise an error
        extra="ignore",
    )

    # ── App Metadata ─────────────────────────────────────────────────────────
    PROJECT_NAME: str = "VentureAI"
    VERSION: str = "0.1.0"

    # ── Environment ──────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"

    # ── Supabase ─────────────────────────────────────────────────────────────
    SUPABASE_URL: NonEmptyStr  # required
    SUPABASE_SERVICE_ROLE_KEY: NonEmptyStr  # required
    SUPABASE_ANON_KEY: NonEmptyStr  # required
    AUTO_CONFIRM_EMAIL: bool = False

    # ── LLM Settings ─────────────────────────────────────────────────────────
    GROQ_API_KEY: NonEmptyStr  # required
    TAVILY_API_KEY: str | None = None

    # ── JWT ──────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: NonEmptyStr  # required
    JWT_ALGORITHM: str = "HS256"

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    # ── Cloudinary ───────────────────────────────────────────────────────────
    CLOUDINARY_CLOUD_NAME: NonEmptyStr  # required
    CLOUDINARY_API_KEY: NonEmptyStr  # required
    CLOUDINARY_API_SECRET: NonEmptyStr  # required

    # ── LlamaParse ───────────────────────────────────────────────────────────
    LLAMA_CLOUD_API_KEY: NonEmptyStr  # required

    # ── Zoom ─────────────────────────────────────────────────────────────────
    ZOOM_ACCOUNT_ID: str | None = None
    ZOOM_CLIENT_ID: str | None = None
    ZOOM_CLIENT_SECRET: str | None = None

    # ── Computed helpers ─────────────────────────────────────────────────────
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


# Instantiate the settings. This triggers validation against `.env`.
settings = Settings()
