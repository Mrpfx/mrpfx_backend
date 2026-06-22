"""
MRPFX Backend - FastAPI Application

WordPress-compatible authentication backend with phpass and bcrypt password support.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import logging
import os

from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import ini_db
from app.v1.api.auth import router as auth_router
from app.v1.api.crypto_payments import router as crypto_payment_router
from fastapi import Header


# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def verify_api_key(
    x_api_key: str = Header(..., alias="X-API-KEY")
):
    """
    Dependency to verify the private API key in the X-API-KEY header.
    """
    if x_api_key != settings.API_KEY:
        logger.warning(f"Invalid API Key attempt: {x_api_key}")
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API Key"
        )
    return x_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting %s...", settings.APP_NAME)

    # Create uploads directory if it doesn't exist
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(os.path.join(base_dir, "wp-content/uploads"), exist_ok=True)

    # await ini_db()
    logger.info("Database tables created/verified")
    yield
    # Shutdown
    logger.info("Shutting down %s...", settings.APP_NAME)


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="WordPress-compatible authentication backend with support for imported user data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    dependencies=[Depends(verify_api_key)]
)

# Rate Limit Exception Handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security: Trusted Host
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Allow on Render and other platforms
)

# Performance: GZip Compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Security: CORS
origins = [
    "https://mrpfx.vercel.app",
    "http://localhost:3000",
    "http://localhost:8000",
    "https://mrpfx.com",
    "https://www.mrpfx.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount static files
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.mount("/wp-content", StaticFiles(directory=os.path.join(base_dir, "wp-content")), name="wp-content")


# Register routers
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
from app.v1.api.wordpress import router as wordpress_router
app.include_router(wordpress_router, prefix=settings.API_V1_PREFIX)
from app.v1.api.admin import router as admin_router
app.include_router(admin_router, prefix=settings.API_V1_PREFIX)
app.include_router(crypto_payment_router, prefix=settings.API_V1_PREFIX)
from app.v1.api.services import router as services_router
app.include_router(services_router, prefix=settings.API_V1_PREFIX)
from app.v1.api.traders import router as traders_router
app.include_router(traders_router, prefix=settings.API_V1_PREFIX)

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - health check."""
    return {
        "name": settings.APP_NAME,
        "status": "healthy",
        "version": "1.0.0"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
