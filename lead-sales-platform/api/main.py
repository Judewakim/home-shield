"""
Lead Sales Platform API - Main Application.

FastAPI application with CORS enabled for frontend communication.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import __version__

# Create FastAPI application
app = FastAPI(
    title="Lead Sales Platform API",
    description="REST API for purchasing and managing real estate leads",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS - Allow all origins for development
# TODO: Restrict origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for demo
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)


@app.get("/health", tags=["Health"])
def health_check():
    """
    Health check endpoint.

    Returns the API status and version.
    """
    return {
        "status": "healthy",
        "version": __version__,
        "service": "lead-sales-platform-api"
    }


@app.get("/", tags=["Root"])
def root():
    """
    Root endpoint with API information.
    """
    return {
        "message": "Lead Sales Platform API",
        "version": __version__,
        "docs": "/docs",
        "health": "/health"
    }


# Import and include routers
from api.routers import inventory, quotes, purchases

app.include_router(inventory.router, prefix="/api/v1", tags=["Inventory"])
app.include_router(quotes.router, prefix="/api/v1", tags=["Quotes"])
app.include_router(purchases.router, prefix="/api/v1", tags=["Purchases"])
