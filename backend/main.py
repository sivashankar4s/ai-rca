"""FastAPI application entry point.

Boots the AI-RCA service with permissive CORS for the single-page frontend and a
liveness ``/api/health`` probe. Domain routers and static frontend serving are wired
in by their respective work units.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.routers.analysis import router as analysis_router
from backend.routers.config import router as config_router
from backend.routers.github import router as github_router
from backend.routers.health import router as health_router

app = FastAPI(
    title="Sentinel AI",
    version="1.0.0",
    description="AI-powered service health monitoring and root-cause analysis for AWS pipelines",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


app.include_router(analysis_router)
app.include_router(config_router)
app.include_router(github_router)
app.include_router(health_router)


@app.exception_handler(ValueError)
async def _value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    """Translate registry ValueError (unknown provider) to HTTP 400 (FR-008)."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Deployment liveness probe."""
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
