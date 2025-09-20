"""
Main entry point for ML Chat Billing Service
"""
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.ml import router as ml_router
from app.api.chat import router as chat_router
from app.api.monitoring import router as monitoring_router
from app.api.admin import router as admin_router
from app.api.performance import router as performance_router
from app.api.middleware import (
    LoggingMiddleware,
    AuthLoggingMiddleware,
    RateLimitingMiddleware,
    SecurityHeadersMiddleware
)
from app.api.performance_middleware import (
    PerformanceMiddleware,
    MemoryMonitoringMiddleware,
    HealthCheckMiddleware
)


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting ML Chat Billing Service...")
    
    # Initialize database
    from app.database import init_db
    init_db()
    logger.info("Database initialized")
    
    # Load ML models
    # TODO: Add model loading
    
    logger.info("Service started successfully")
    yield
    
    logger.info("Shutting down ML Chat Billing Service...")


# Create FastAPI app
app = FastAPI(
    title="ML Chat Billing Service",
    description="Chat service with ML models and billing system",
    version="1.0.0",
    lifespan=lifespan
)

# Add custom middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(PerformanceMiddleware, enable_detailed_logging=settings.debug)
app.add_middleware(MemoryMonitoringMiddleware, memory_threshold=0.85)
app.add_middleware(HealthCheckMiddleware)
app.add_middleware(AuthLoggingMiddleware)
app.add_middleware(LoggingMiddleware)
if not settings.debug:
    app.add_middleware(RateLimitingMiddleware, calls_per_minute=100)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(ml_router)
app.include_router(chat_router)
app.include_router(monitoring_router)
app.include_router(admin_router)
app.include_router(performance_router)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "ML Chat Billing Service is running"}


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "service": "ML Chat Billing Service",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )