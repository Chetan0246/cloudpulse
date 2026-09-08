"""
FastAPI application factory.

This module creates the FastAPI app. It is imported by:
  - lambda/api/handler.py  (Mangum wraps it for Lambda)
  - local development: `uvicorn app.main:app --reload`

No Lambda-specific code lives here.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_config import configure_logging
from app.routers import health, incidents, resources, simulate


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Configure logging on startup."""
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="CloudPulse API",
        description=(
            "Autonomous Cloud Reliability and Self-Healing Simulator — "
            "BCSE355L Fall 2026-2027"
        ),
        version="0.1.0",
        lifespan=lifespan,
        # Disable docs in production (Lambda env)
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )

    app.include_router(health.router)
    app.include_router(resources.router)
    app.include_router(incidents.router)
    app.include_router(simulate.router)

    return app


# Module-level app instance for uvicorn and Mangum
app = create_app()
