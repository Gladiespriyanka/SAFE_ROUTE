"""
SafeRoute Delhi API - FastAPI Application
Clean entry point with route setup.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    print("SafeRoute API is starting...")
    yield

# Initialize FastAPI app
app = FastAPI(
    title="SafeRoute Delhi API",
    description="FastAPI backend serving the SafeRoute Delhi women-centric safety model.",
    version="1.3.0",
    lifespan=lifespan,
)

# Enable CORS for Streamlit and other local frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routes
app.include_router(router)
