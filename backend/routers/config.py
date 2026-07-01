import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..db.session import get_db
from ..models.schemas import (
    MASK_SENTINEL,
    AppConfigRead,
    AthenaConfigStatus,
    AthenaConfigUpdate,
    AwsConfigStatus,
    AwsConfigUpdate,
    CloudWatchConfigStatus,
    CloudWatchConfigUpdate,
    CloudWatchLogGroupsResponse,
    ConfigSaveResult,
    GithubMcpConfigStatus,
    GithubMcpConfigUpdate,
)
from ..plugin_registry import get_data_source
from ..repositories import config_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])


def _build_aws_status(row_cfg: dict | None, *, db_row_exists: bool) -> AwsConfigStatus:
    """Build AwsConfigStatus: use DB values when a row exists, env-vars only as fallback."""
    if db_row_exists:
        cfg = row_cfg or {}
        key_id: str = cfg.get("access_key_id") or ""
        secret: str = cfg.get("secret_access_key") or ""
        token: str = cfg.get("session_token") or ""
        region: str | None = cfg.get("region") or None
        if not key_id or not secret:
            return AwsConfigStatus(configured=False, access_key_id=key_id or None, region=region)
        return AwsConfigStatus(
            configured=True,
            access_key_id=key_id,
            secret_access_key=MASK_SENTINEL,
            session_token=MASK_SENTINEL if token else None,
            region=region,
        )

    # No DB row — fall back to environment variables
    key_id = settings.aws_access_key_id or ""
    secret = settings.aws_secret_access_key or ""
    token = settings.aws_session_token or ""
    region = settings.aws_region or None
    if key_id and secret:
        logger.warning("AWS config falling back to environment variables")
        return AwsConfigStatus(
            configured=True,
            access_key_id=key_id,
            secret_access_key=MASK_SENTINEL,
            session_token=MASK_SENTINEL if token else None,
            region=region,
        )
    return AwsConfigStatus(configured=False)


def _build_github_mcp_status(row_cfg: dict | None, *, db_row_exists: bool) -> GithubMcpConfigStatus:
    """Build GithubMcpConfigStatus: use DB values when a row exists, env-vars only as fallback."""
    if db_row_exists:
        cfg = row_cfg or {}
        repo: str = cfg.get("repo") or ""
        token: str = cfg.get("token") or ""
        branch: str | None = cfg.get("default_branch")
        if not repo or not token:
            return GithubMcpConfigStatus(configured=False, repo=repo or None, default_branch=branch)
        return GithubMcpConfigStatus(
            configured=True, repo=repo, token=MASK_SENTINEL, default_branch=branch
        )

    # No DB row — fall back to environment variables
    repo = settings.github_repo or ""
    token = settings.github_token or ""
    if repo and token:
        logger.warning("GitHub MCP config falling back to environment variables")
        return GithubMcpConfigStatus(configured=True, repo=repo, token=MASK_SENTINEL)
    return GithubMcpConfigStatus(configured=False)


def _build_cloudwatch_status(
    row_cfg: dict | None, *, db_row_exists: bool
) -> CloudWatchConfigStatus:
    """Build CloudWatchConfigStatus: use DB values when a row exists, env-vars only as fallback."""
    if db_row_exists:
        cfg = row_cfg or {}
        groups: list[str] = cfg.get("log_groups") or []
        timeout: int | None = cfg.get("query_timeout")
        return CloudWatchConfigStatus(
            configured=bool(groups), log_groups=groups, query_timeout=timeout
        )

    # No DB row — fall back to environment variables
    env_groups = settings.cloudwatch_log_groups
    if env_groups:
        logger.warning("CloudWatch config falling back to environment variables")
        return CloudWatchConfigStatus(
            configured=True,
            log_groups=env_groups,
            query_timeout=settings.cloudwatch_query_timeout,
        )
    return CloudWatchConfigStatus(configured=False)


def _build_athena_status(row_cfg: dict | None, *, db_row_exists: bool) -> AthenaConfigStatus:
    """Build AthenaConfigStatus: use DB values when a row exists, env-vars only as fallback."""
    if db_row_exists:
        cfg = row_cfg or {}
        database: str = cfg.get("database") or ""
        table: str = cfg.get("table") or ""
        return AthenaConfigStatus(
            configured=bool(database and table),
            database=database or None,
            table=table or None,
        )

    # No DB row — fall back to environment variables
    database = settings.athena_database or ""
    table = settings.athena_table or ""
    if database and table:
        logger.warning("Athena config falling back to environment variables")
        return AthenaConfigStatus(configured=True, database=database, table=table)
    return AthenaConfigStatus(configured=False)


@router.get("", response_model=AppConfigRead)
async def get_config(db: Session = Depends(get_db)) -> AppConfigRead:
    row = config_repo.get_app_config(db)
    db_row_exists = row is not None
    aws_cfg = row.aws_config if row else None
    github_cfg = row.github_mcp_config if row else None
    cloudwatch_cfg = row.cloudwatch_config if row else None
    athena_cfg = row.athena_config if row else None
    return AppConfigRead(
        aws=_build_aws_status(aws_cfg, db_row_exists=db_row_exists),
        github_mcp=_build_github_mcp_status(github_cfg, db_row_exists=db_row_exists),
        cloudwatch=_build_cloudwatch_status(cloudwatch_cfg, db_row_exists=db_row_exists),
        athena=_build_athena_status(athena_cfg, db_row_exists=db_row_exists),
    )


@router.patch("/aws", response_model=ConfigSaveResult)
async def patch_aws_config(
    data: AwsConfigUpdate, db: Session = Depends(get_db)
) -> ConfigSaveResult:
    row = config_repo.upsert_aws_config(db, data)
    db.commit()
    return ConfigSaveResult(
        success=True,
        message="AWS configuration saved.",
        updated_at=row.updated_at,
    )


@router.patch("/github-mcp", response_model=ConfigSaveResult)
async def patch_github_mcp_config(
    data: GithubMcpConfigUpdate, db: Session = Depends(get_db)
) -> ConfigSaveResult:
    row = config_repo.upsert_github_mcp_config(db, data)
    db.commit()
    return ConfigSaveResult(
        success=True,
        message="GitHub MCP configuration saved.",
        updated_at=row.updated_at,
    )


@router.get("/cloudwatch/log-groups", response_model=CloudWatchLogGroupsResponse)
async def discover_cloudwatch_log_groups(
    prefix: str | None = None, db: Session = Depends(get_db)
) -> CloudWatchLogGroupsResponse:
    """List AWS log groups (optionally by name prefix) for the config picker."""
    ds = get_data_source("cloudwatch", db=db)
    try:
        groups = ds.list_log_groups(prefix)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CloudWatchLogGroupsResponse(log_groups=groups)


@router.patch("/cloudwatch", response_model=ConfigSaveResult)
async def patch_cloudwatch_config(
    data: CloudWatchConfigUpdate, db: Session = Depends(get_db)
) -> ConfigSaveResult:
    row = config_repo.upsert_cloudwatch_config(db, data)
    db.commit()
    return ConfigSaveResult(
        success=True,
        message="CloudWatch configuration saved.",
        updated_at=row.updated_at,
    )


@router.patch("/athena", response_model=ConfigSaveResult)
async def patch_athena_config(
    data: AthenaConfigUpdate, db: Session = Depends(get_db)
) -> ConfigSaveResult:
    row = config_repo.upsert_athena_config(db, data)
    db.commit()
    return ConfigSaveResult(
        success=True,
        message="Athena configuration saved.",
        updated_at=row.updated_at,
    )
