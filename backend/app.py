"""
SafeRoute Delhi API - FastAPI Application
Clean entry point with route setup.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import router

# Initialize FastAPI app
app = FastAPI(
    title="SafeRoute Delhi API",
    description="FastAPI backend serving the SafeRoute Delhi women-centric safety model.",
    version="1.3.0",
)

# Enable CORS for Streamlit and other local frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routes
app.include_router(router)
