"""
RescuNet Backend — FastAPI Application Entry Point.

Run with:
    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.models.incident import HealthResponse
from app.routes import agent, incidents, plans, resources


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database on startup."""
    init_db()
    yield


app = FastAPI(
    title="RescuNet API",
    description=(
        "AI-powered community emergency coordination system. "
        "This backend handles emergency incident creation, tracking, "
        "and coordination for the RescuNet platform."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration for local Next.js frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(incidents.router)
app.include_router(agent.router)
app.include_router(resources.router)
app.include_router(plans.router)


@app.get("/", tags=["info"])
def root():
    """Basic RescuNet API information."""
    return {
        "name": "RescuNet API",
        "version": "0.1.0",
        "description": "AI-powered community emergency coordination system",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health", response_model=HealthResponse, tags=["info"])
def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", service="rescunet-backend")
