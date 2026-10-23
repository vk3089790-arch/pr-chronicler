"""Main FastAPI application entry point for PR Chronicler."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import DatabaseManager
from app.logging_config import logger
from app.api import router as api_router
from app.webhook import router as webhook_router, pipeline_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler for startup initialization and graceful shutdown."""
    logger.info("Initializing PR Chronicler services and SQLite database...")
    # Initialize database tables
    await pipeline_service.db.init_db()

    # Log configuration summary (masking secrets)
    configured_model = settings.GEMINI_MODEL
    effective_model = pipeline_service.reflection_chain.model_name
    if effective_model != configured_model:
        logger.info(
            "Gemini Model: %s [migrated to effective model: %s] (temp=%.1f)",
            configured_model,
            effective_model,
            settings.GEMINI_TEMPERATURE,
        )
    else:
        logger.info("Gemini Model: %s (temp=%.1f)", configured_model, settings.GEMINI_TEMPERATURE)
    logger.info("SMTP Host: %s:%d (TLS=%s)", settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_USE_TLS)
    logger.info("Recipient Email: %s", settings.RECIPIENT_EMAIL or "Not configured")
    logger.info("GitHub Token: %s", "Configured" if settings.GITHUB_TOKEN else "None (unauthenticated rate limits)")
    logger.info("Webhook HMAC Secret: %s", "Configured" if settings.GITHUB_WEBHOOK_SECRET else "Disabled")

    yield

    logger.info("Shutting down PR Chronicler application.")


app = FastAPI(
    title="PR Chronicler",
    description="Automated event-driven technical reflections for merged GitHub pull requests using LangChain and Gemini.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware - configure for local development frontend
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):(3000|8000)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API and webhook routers
app.include_router(api_router)
app.include_router(webhook_router)


@app.get("/")
async def root():
    """Application metadata and service status."""
    return {
        "service": "PR Chronicler",
        "status": "online",
        "version": "1.0.0",
        "endpoints": {
            "webhook": "POST /webhook/github",
            "health": "GET /health",
            "docs": "GET /docs",
        },
    }


@app.get("/health")
async def health_check():
    """System health check and configuration readiness."""
    return {
        "status": "healthy",
        "database": settings.DATABASE_PATH,
        "gemini_model": settings.GEMINI_MODEL,
        "gemini_effective_model": pipeline_service.reflection_chain.model_name,
        "gemini_configured": bool(settings.GOOGLE_API_KEY),
        "smtp_configured": bool(settings.SMTP_EMAIL and settings.SMTP_APP_PASSWORD and settings.RECIPIENT_EMAIL),
        "github_token_configured": bool(settings.GITHUB_TOKEN),
        "webhook_secret_enforced": bool(settings.GITHUB_WEBHOOK_SECRET),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
