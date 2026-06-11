import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import settings
from .routers import analysis

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Root Cause Analyzer",
    version="1.0.0",
    description="Automated RCA using Amazon Athena, CloudWatch, and AWS Bedrock",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(analysis.router)


@app.on_event("startup")
async def _startup() -> None:
    try:
        settings.validate_required()
    except ValueError as exc:
        # Log each misconfiguration as a distinct WARNING so the server still
        # starts (useful in dev / CI).  The first API call will fail with a
        # clear error message if the config is still wrong.
        for line in str(exc).splitlines():
            logger.warning("CONFIG: %s", line)

    logger.info(
        "Starting AI-RCA  region=%s  database=%s  table=%s  model=%s  log_group=%s",
        settings.aws_region,
        settings.athena_database,
        settings.athena_table,
        settings.llm_model,
        settings.cloudwatch_log_group,
    )
    cred_source = (
        "explicit AWS keys" if settings.aws_access_key_id else "IAM role / env chain"
    )
    logger.info("AWS credential source: %s", cred_source)


@app.middleware("http")
async def _log_requests(request: Request, call_next):
    logger.info("→ %s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.info("← %s %s  status=%s", request.method, request.url.path, response.status_code)
    return response

# Serve the frontend as static files
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
_frontend_dir = os.path.abspath(_frontend_dir)

if os.path.isdir(_frontend_dir):
    app.mount("/assets", StaticFiles(directory=_frontend_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_ui():
        return FileResponse(os.path.join(_frontend_dir, "index.html"))
