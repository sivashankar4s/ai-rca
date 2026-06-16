"""FastAPI application entry point.

Boots the AI-RCA service with permissive CORS for the single-page frontend and a
liveness ``/api/health`` probe. Domain routers and static frontend serving are wired
in by their respective work units.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI Root Cause Analyzer",
    version="1.0.0",
    description="AI-powered RCA tool for production incidents",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Deployment liveness probe."""
    return {"status": "ok"}
