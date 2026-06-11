import logging

import requests as _requests
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..db.session import get_db
from ..models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ConfigResponse,
    ConfigUpdateRequest,
    FailuresRequest,
    FailuresResponse,
)
from ..plugin_registry import get_data_source, get_llm, get_log_backend
from ..services import persistence_service
from ..services.rca_orchestrator import RCAOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analysis"])


def _make_orchestrator() -> RCAOrchestrator:
    return RCAOrchestrator(
        data_source=get_data_source(),
        llm=get_llm(),
        log_backend=get_log_backend(),
    )


def _handle_aws_error(exc: Exception):
    """Re-raise ClientError with expired-token as a clean 401."""
    if isinstance(exc, ClientError):
        code = exc.response["Error"]["Code"]
        if code in ("ExpiredTokenException", "ExpiredToken", "AuthFailure"):
            raise HTTPException(
                status_code=401,
                detail=(
                    "AWS credentials have expired. "
                    "Please refresh AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and "
                    "AWS_SESSION_TOKEN in your .env file and restart the server."
                ),
            )
    raise exc


@router.post("/failures", response_model=FailuresResponse)
async def fetch_failures(request: FailuresRequest):
    """Step 1 — Query Athena and return records for the user to review."""
    try:
        orchestrator = _make_orchestrator()
        return orchestrator.fetch_records(
            request.time_range,
            request.component,
            start_date=request.start_date,
            end_date=request.end_date,
            failure_only=request.failure_only,
        )
    except RuntimeError as e:
        if "credentials have expired" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        logger.error("Athena/AWS error fetching failures: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except TimeoutError as e:
        logger.error("Timeout fetching failures: %s", e)
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        try:
            _handle_aws_error(e)
        except HTTPException:
            raise
        logger.error("Unexpected error fetching failures: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch failures: {str(e)}")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest, db: Session = Depends(get_db)):
    """Step 2 — Run CloudWatch + Bedrock RCA on the user-selected failure records."""
    try:
        orchestrator = _make_orchestrator()
        result = orchestrator.analyze_records(
            request.time_range,
            request.records,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        if result.failure_groups:
            try:
                persistence_service.persist_analysis(db, result)
            except Exception:
                db.rollback()
                logger.exception("Failed to persist RCA analysis to CRM tables")
        return result
    except RuntimeError as e:
        if "credentials have expired" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        logger.error("Athena/AWS error during analysis: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except TimeoutError as e:
        logger.error("Timeout during analysis: %s", e)
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        try:
            _handle_aws_error(e)
        except HTTPException:
            raise
        logger.error("Unexpected error during analysis: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ── Config ────────────────────────────────────────────────────────────────────

@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """Return current runtime configuration (secrets are not exposed, only presence indicated)."""
    return ConfigResponse(
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key_set=bool(settings.aws_secret_access_key),
        aws_session_token_set=bool(settings.aws_session_token),
        aws_region=settings.aws_region,
        athena_database=settings.athena_database,
        athena_table=settings.athena_table,
        llm_model=settings.llm_model,
        llm_base_url=settings.llm_base_url,
    )


@router.post("/config")
async def update_config(request: ConfigUpdateRequest):
    """Update runtime configuration in-memory. Empty/None fields are left unchanged (fall back to .env)."""
    updated: list[str] = []

    def _set(field: str, value: str) -> None:
        # Use object.__setattr__ to bypass Pydantic's __setattr__ interceptor
        object.__setattr__(settings, field, value)
        updated.append(field)

    if request.aws_access_key_id is not None and request.aws_access_key_id != "":
        _set("aws_access_key_id", request.aws_access_key_id)
    if request.aws_secret_access_key is not None and request.aws_secret_access_key != "":
        _set("aws_secret_access_key", request.aws_secret_access_key)
    if request.aws_session_token is not None and request.aws_session_token != "":
        _set("aws_session_token", request.aws_session_token)
    if request.aws_region is not None and request.aws_region != "":
        _set("aws_region", request.aws_region)
    if request.athena_database is not None and request.athena_database != "":
        _set("athena_database", request.athena_database)
    if request.athena_table is not None and request.athena_table != "":
        _set("athena_table", request.athena_table)
    if request.llm_model is not None and request.llm_model != "":
        _set("llm_model", request.llm_model)

    logger.info("Config updated in-memory: %s", updated)
    return {"status": "ok", "updated": updated}


# ── Models ────────────────────────────────────────────────────────────────────

@router.get("/models")
async def list_models():
    """Proxy the LLM provider's /v1/models endpoint and return a flat list of model IDs."""
    if not settings.llm_api_key:
        raise HTTPException(status_code=503, detail="LLM_API_KEY is not configured.")

    base = settings.llm_base_url.rstrip("/")
    url  = f"{base}/v1/models"
    try:
        resp = _requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.llm_api_key}",
            },
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        # OpenAI-compatible: { "data": [ { "id": "...", ... }, ... ] }
        data = payload.get("data", payload) if isinstance(payload, dict) else payload
        model_ids = sorted({
            item.get("id") or item
            for item in (data if isinstance(data, list) else [])
            if item
        })
        return {"models": model_ids, "current": settings.llm_model}
    except _requests.exceptions.RequestException as exc:
        logger.error("Failed to fetch models from %s: %s", url, exc)
        raise HTTPException(status_code=502, detail=f"Could not reach LLM endpoint: {exc}")



@router.get("/health")
async def health():
    return {"status": "ok"}
