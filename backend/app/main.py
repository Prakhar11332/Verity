from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # Ensure all SQLAlchemy models are registered
from app.api.routes import api_router
from app.config import settings
from app.database import Base, engine

# Initialize SQLite tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    description="Explainable finance-reconciliation engine for multi-source payment and settlement reconciliation.",
    version="0.1.0",
)

# CORS middleware for local frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "docs_url": "/docs",
        "health": "/api/health",
    }
