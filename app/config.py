"""Configuration settings for PR Chronicler using Pydantic Settings."""

import os
from pathlib import Path
from typing import Any, Optional
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=(str(ENV_FILE), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Google Gemini LLM
    GOOGLE_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        description="Google API Key for Gemini models via langchain-google-genai"
    )
    GEMINI_MODEL: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model identifier (e.g. gemini-2.5-flash, gemini-2.5-pro, gemini-flash-latest)"
    )
    GEMINI_TEMPERATURE: float = Field(
        default=0.1,
        description="Sampling temperature for the reflection chain"
    )

    @field_validator("GOOGLE_API_KEY", mode="before")
    @classmethod
    def sanitize_api_key(cls, v: Any) -> str:
        if v is None:
            return ""
        s = str(v).strip()
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1].strip()
        return s

    # GitHub API & Webhook
    GITHUB_TOKEN: Optional[str] = Field(
        default=None,
        description="GitHub personal access token for higher rate limits and API access"
    )
    GITHUB_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("GITHUB_WEBHOOK_SECRET", "WEBHOOK_SECRET"),
        description="HMAC SHA-256 secret configured in GitHub Webhook settings"
    )

    # SMTP Configuration
    SMTP_EMAIL: str = Field(
        default="",
        description="Sender email address for SMTP dispatch"
    )
    SMTP_APP_PASSWORD: str = Field(
        default="",
        description="App password or credential for SMTP authentication"
    )
    SMTP_HOST: str = Field(
        default="smtp.gmail.com",
        description="SMTP server hostname"
    )
    SMTP_PORT: int = Field(
        default=587,
        description="SMTP server port (e.g. 587 for STARTTLS, 465 for SSL)"
    )
    SMTP_USE_TLS: bool = Field(
        default=True,
        description="Whether to initiate STARTTLS when connecting to SMTP"
    )
    RECIPIENT_EMAIL: str = Field(
        default="",
        description="Destination email address for PR reflections"
    )

    # Database & Storage
    DATABASE_PATH: str = Field(
        default="pr_chronicler.db",
        description="Path to local SQLite database for delivery tracking and idempotency"
    )

    # Logging
    LOG_FILE: str = Field(
        default="pr_chronicler.log",
        description="Path to log file"
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )

    # Webhook server
    HOST: str = Field(default="0.0.0.0", description="FastAPI host")
    PORT: int = Field(default=8000, description="FastAPI port")


# Global settings singleton
settings = Settings()
