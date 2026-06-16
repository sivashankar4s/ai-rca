import logging
from urllib.parse import urlsplit, urlunsplit

import requests as _requests
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..db.session import engine, get_db
from ..models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ConfigResponse,
    ConfigUpdateRequest,
    FailuresRequest,
    FailuresResponse,
    ProviderOption,
    ProvidersResponse,
)
from ..plugin_registry import get_data_source, get_llm, get_log_backend
from ..services import persistence_service
from ..services.rca_orchestrator import RCAOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analysis"])


def _make_orchestrator(
    data_source_override: str | None = None,
    log_backend_override: str | None = None,
) -> RCAOrchestrator:
    return RCAOrchestrator(
        data_source=get_data_source(data_source_override),
        llm=get_llm(),
        log_backend=get_log_backend(log_backend_override),
        log_backend_provider=log_backend_override or settings.log_analysis_provider,
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
async def fetch_failures(request: FailuresRequest, db: Session = Depends(get_db)):
    """Step 1 — Query Athena and return records for the user to review."""
    try:
        orchestrator = _make_orchestrator(data_source_override=request.data_source)
        result = orchestrator.fetch_records(
            request.time_range,
            request.component,
            start_date=request.start_date,
            end_date=request.end_date,
            failure_only=request.failure_only,
        )
        if result.records:
            try:
                persistence_service.persist_fetched_records(db, result)
            except Exception:
                db.rollback()
                logger.exception("Failed to persist fetched failure records to CRM tables")
        return result
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
        orchestrator = _make_orchestrator(log_backend_override=request.log_backend)
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


# ── Providers ─────────────────────────────────────────────────────────────────

@router.get("/providers", response_model=ProvidersResponse)
async def list_providers():
    """List selectable data-source / log-backend providers and their current defaults."""
    return ProvidersResponse(
        data_sources=[
            ProviderOption(id="athena", label="AWS Athena"),
            ProviderOption(id="postgres", label="Local Database (PostgreSQL)"),
        ],
        log_backends=[
            ProviderOption(id="cloudwatch", label="Amazon CloudWatch"),
            ProviderOption(id="grafana_loki", label="Grafana Loki"),
        ],
        defaults={
            "data_source": settings.data_source_provider,
            "log_backend": settings.log_analysis_provider,
        },
    )


# ── Config ────────────────────────────────────────────────────────────────────

def _mask_db_url(url: str) -> str:
    """Replace the password component of a DB connection string with '***'."""
    parts = urlsplit(url)
    if not parts.password:
        return url
    netloc = parts.netloc.replace(f":{parts.password}@", ":***@")
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _check_database_connected() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


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
        llm_provider=settings.llm_provider,
        anthropic_api_key_set=bool(settings.anthropic_api_key),
        grafana_loki_url=settings.grafana_loki_url,
        grafana_api_key_set=bool(settings.grafana_api_key),
        grafana_datasource_uid=settings.grafana_datasource_uid,
        database_url_masked=_mask_db_url(settings.database_url),
        database_connected=_check_database_connected(),
        github_repo=settings.github_repo,
        github_token_set=bool(settings.github_token),
        github_mcp_command=settings.github_mcp_command,
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
    if request.anthropic_api_key is not None and request.anthropic_api_key != "":
        _set("anthropic_api_key", request.anthropic_api_key)
    if request.grafana_loki_url is not None and request.grafana_loki_url != "":
        _set("grafana_loki_url", request.grafana_loki_url)
    if request.grafana_api_key is not None and request.grafana_api_key != "":
        _set("grafana_api_key", request.grafana_api_key)
    if request.grafana_datasource_uid is not None and request.grafana_datasource_uid != "":
        _set("grafana_datasource_uid", request.grafana_datasource_uid)
    if request.github_repo is not None and request.github_repo != "":
        _set("github_repo", request.github_repo)
    if request.github_token is not None and request.github_token != "":
        _set("github_token", request.github_token)
    if request.github_mcp_command is not None and request.github_mcp_command != "":
        _set("github_mcp_command", request.github_mcp_command)

    logger.info("Config updated in-memory: %s", updated)
    return {"status": "ok", "updated": updated}


# ── Models ────────────────────────────────────────────────────────────────────

_ANTHROPIC_FALLBACK_MODELS = [
    "claude-opus-4-1-20250805",
    "claude-opus-4-20250514",
    "claude-sonnet-4-6",
    "claude-sonnet-4-20250514",
    "claude-3-7-sonnet-20250219",
    "claude-3-5-haiku-20241022",
]


@router.get("/models")
async def list_models():
    """Return a flat list of available model IDs for the active LLM provider."""
    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured.")

        url = "https://api.anthropic.com/v1/models"
        try:
            resp = _requests.get(
                url,
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=15,
            )
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("data", []) if isinstance(payload, dict) else []
            model_ids = sorted({item.get("id") for item in data if item.get("id")})
            if not model_ids:
                model_ids = _ANTHROPIC_FALLBACK_MODELS
            return {"models": model_ids, "current": settings.llm_model}
        except _requests.exceptions.RequestException as exc:
            logger.warning("Failed to fetch models from %s: %s — using fallback list", url, exc)
            return {"models": _ANTHROPIC_FALLBACK_MODELS, "current": settings.llm_model}

    # OpenAI-compatible providers (navify / openai)
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
