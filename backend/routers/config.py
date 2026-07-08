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
    HealthConfigStatus,
    HealthConfigUpdate,
    HealthProfile,
    HealthProfileCreate,
    HealthProfileRename,
    HealthProfilesResponse,
    HealthProfileUpdate,
    HealthResource,
    HealthResourcesResponse,
    HealthServiceType,
)
from ..plugin_registry import get_data_source, get_health_checkers
from ..repositories import config_repo
from ..repositories.config_repo import ProfileNameConflict, ProfileNotFound

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


def _build_health_status(row_cfg: dict | None) -> HealthConfigStatus:
    """Build HealthConfigStatus from the persisted health_config (no env fallback)."""
    cfg = row_cfg or {}
    glue_jobs: list[str] = cfg.get("glue_jobs") or []
    glue_workflows: list[str] = cfg.get("glue_workflows") or []
    lambda_functions: list[str] = cfg.get("lambda_functions") or []
    datasync_tasks = [HealthResource(**t) for t in cfg.get("datasync_tasks") or []]
    configured = bool(glue_jobs or glue_workflows or lambda_functions or datasync_tasks)
    return HealthConfigStatus(
        configured=configured,
        glue_jobs=glue_jobs,
        glue_workflows=glue_workflows,
        lambda_functions=lambda_functions,
        datasync_tasks=datasync_tasks,
    )


@router.get("", response_model=AppConfigRead)
async def get_config(db: Session = Depends(get_db)) -> AppConfigRead:
    row = config_repo.get_app_config(db)
    db_row_exists = row is not None
    aws_cfg = row.aws_config if row else None
    github_cfg = row.github_mcp_config if row else None
    cloudwatch_cfg = row.cloudwatch_config if row else None
    athena_cfg = row.athena_config if row else None
    health_cfg = row.health_config if row else None
    return AppConfigRead(
        aws=_build_aws_status(aws_cfg, db_row_exists=db_row_exists),
        github_mcp=_build_github_mcp_status(github_cfg, db_row_exists=db_row_exists),
        cloudwatch=_build_cloudwatch_status(cloudwatch_cfg, db_row_exists=db_row_exists),
        athena=_build_athena_status(athena_cfg, db_row_exists=db_row_exists),
        health=_build_health_status(health_cfg),
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


def _discover(service_type: HealthServiceType, db: Session) -> HealthResourcesResponse:
    """Run one health provider's discovery for the config picker."""
    checker = get_health_checkers(db)[service_type]
    try:
        resources = checker.discover()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return HealthResourcesResponse(resources=resources)


@router.get("/health/glue-jobs", response_model=HealthResourcesResponse)
async def discover_glue_jobs(db: Session = Depends(get_db)) -> HealthResourcesResponse:
    return _discover(HealthServiceType.GLUE_JOB, db)


@router.get("/health/glue-workflows", response_model=HealthResourcesResponse)
async def discover_glue_workflows(
    db: Session = Depends(get_db),
) -> HealthResourcesResponse:
    return _discover(HealthServiceType.GLUE_WORKFLOW, db)


@router.get("/health/lambda-functions", response_model=HealthResourcesResponse)
async def discover_lambda_functions(
    db: Session = Depends(get_db),
) -> HealthResourcesResponse:
    return _discover(HealthServiceType.LAMBDA_FUNCTION, db)


@router.get("/health/datasync-tasks", response_model=HealthResourcesResponse)
async def discover_datasync_tasks(
    db: Session = Depends(get_db),
) -> HealthResourcesResponse:
    return _discover(HealthServiceType.DATASYNC_TASK, db)


@router.patch("/health", response_model=ConfigSaveResult)
async def patch_health_config(
    data: HealthConfigUpdate, db: Session = Depends(get_db)
) -> ConfigSaveResult:
    row = config_repo.upsert_health_config(db, data)
    db.commit()
    return ConfigSaveResult(
        success=True,
        message="Health configuration saved.",
        updated_at=row.updated_at,
    )


# ── Health profiles — named resource sets ────────────────────────────────────────


@router.get("/health/profiles", response_model=HealthProfilesResponse)
async def list_health_profiles(db: Session = Depends(get_db)) -> HealthProfilesResponse:
    """List all health profiles (each a named set of monitored resources)."""
    return HealthProfilesResponse(
        profiles=[HealthProfile(**p) for p in config_repo.get_profiles(db)]
    )


@router.post("/health/profiles", response_model=HealthProfile, status_code=201)
async def create_health_profile(
    data: HealthProfileCreate, db: Session = Depends(get_db)
) -> HealthProfile:
    """Create a new empty profile; 409 if the name is already in use."""
    try:
        profile = config_repo.create_profile(db, data.name)
    except ProfileNameConflict as exc:
        raise HTTPException(
            status_code=409, detail=f"A profile named '{data.name}' already exists."
        ) from exc
    db.commit()
    return HealthProfile(**profile)


@router.patch("/health/profiles", response_model=HealthProfile)
async def update_health_profile(
    data: HealthProfileUpdate, db: Session = Depends(get_db)
) -> HealthProfile:
    """Replace a profile's monitored-resource selection; 404 if it doesn't exist."""
    try:
        profile = config_repo.update_profile(db, data)
    except ProfileNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Profile '{data.name}' not found.") from exc
    db.commit()
    return HealthProfile(**profile)


@router.post("/health/profiles/rename", response_model=HealthProfile)
async def rename_health_profile(
    data: HealthProfileRename, db: Session = Depends(get_db)
) -> HealthProfile:
    """Rename a profile; 404 if missing, 409 if the new name is taken."""
    try:
        profile = config_repo.rename_profile(db, data.name, data.new_name)
    except ProfileNameConflict as exc:
        raise HTTPException(
            status_code=409, detail=f"A profile named '{data.new_name}' already exists."
        ) from exc
    except ProfileNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Profile '{data.name}' not found.") from exc
    db.commit()
    return HealthProfile(**profile)


@router.delete("/health/profiles", response_model=ConfigSaveResult)
async def delete_health_profile(
    name: str, db: Session = Depends(get_db)
) -> ConfigSaveResult:
    """Delete a profile by name; 404 if missing."""
    try:
        config_repo.delete_profile(db, name)
    except ProfileNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found.") from exc
    db.commit()
    return ConfigSaveResult(success=True, message=f"Profile '{name}' deleted.")
