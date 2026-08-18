"""Repository for AppConfig — single-row global credential storage (Constitution Principle III)."""

import logging

from sqlalchemy.orm import Session

from backend.db.models import AppConfig
from backend.models.schemas import (
    MASK_SENTINEL,
    AthenaConfigUpdate,
    AwsConfigUpdate,
    CloudWatchConfigUpdate,
    GithubMcpConfigUpdate,
    HealthConfigUpdate,
    HealthProfileUpdate,
)

logger = logging.getLogger(__name__)

_RESOURCE_KEYS = ("glue_jobs", "glue_workflows", "lambda_functions", "datasync_tasks")


class ProfileNameConflict(Exception):
    """Raised when a profile name would collide with an existing one (case-insensitive)."""


class ProfileNotFound(Exception):
    """Raised when an operation targets a profile name that does not exist."""


def get_app_config(db: Session) -> AppConfig | None:
    """Return the single AppConfig row, or None if the table is empty."""
    return db.get(AppConfig, 1)


def _upsert_app_config(db: Session, **kwargs: dict | None) -> AppConfig:
    """INSERT ON CONFLICT DO UPDATE for the single app_config row."""
    existing = db.get(AppConfig, 1)
    if existing is None:
        row = AppConfig(id=1, **kwargs)
        db.add(row)
    else:
        for key, value in kwargs.items():
            setattr(existing, key, value)
        row = existing
    db.flush()
    db.refresh(row)
    logger.info("app_config upserted (fields: %s)", list(kwargs.keys()))
    return row


def upsert_aws_config(db: Session, data: AwsConfigUpdate) -> AppConfig:
    """Persist AWS credentials, honouring the mask sentinel for secrets."""
    existing = get_app_config(db)
    existing_cfg: dict = (existing.aws_config or {}) if existing else {}

    secret: str | None
    if data.secret_access_key == MASK_SENTINEL:
        secret = existing_cfg.get("secret_access_key")
    else:
        secret = data.secret_access_key if data.secret_access_key else None

    token: str | None
    if data.session_token == MASK_SENTINEL:
        token = existing_cfg.get("session_token")
    else:
        token = data.session_token if data.session_token else None

    aws_cfg: dict = {
        "access_key_id": data.access_key_id,
        "secret_access_key": secret,
        "session_token": token,
    }
    if data.region is not None:
        aws_cfg["region"] = data.region

    return _upsert_app_config(db, aws_config=aws_cfg)


def upsert_github_mcp_config(db: Session, data: GithubMcpConfigUpdate) -> AppConfig:
    """Persist GitHub MCP settings, honouring the mask sentinel for the token."""
    existing = get_app_config(db)
    existing_cfg: dict = (existing.github_mcp_config or {}) if existing else {}

    token: str | None
    if data.token == MASK_SENTINEL:
        token = existing_cfg.get("token")
    else:
        token = data.token if data.token else None

    github_cfg: dict = {
        "repo": data.repo,
        "token": token,
    }
    if data.default_branch is not None:
        github_cfg["default_branch"] = data.default_branch

    return _upsert_app_config(db, github_mcp_config=github_cfg)


def upsert_cloudwatch_config(db: Session, data: CloudWatchConfigUpdate) -> AppConfig:
    """Persist CloudWatch log groups + query timeout (no secrets to mask)."""
    cloudwatch_cfg: dict = {"log_groups": data.log_groups}
    if data.query_timeout is not None:
        cloudwatch_cfg["query_timeout"] = data.query_timeout

    return _upsert_app_config(db, cloudwatch_config=cloudwatch_cfg)


def upsert_athena_config(db: Session, data: AthenaConfigUpdate) -> AppConfig:
    """Persist Athena database + table (no secrets to mask)."""
    athena_cfg: dict = {"database": data.database, "table": data.table}
    return _upsert_app_config(db, athena_config=athena_cfg)


def upsert_health_config(db: Session, data: HealthConfigUpdate) -> AppConfig:
    """Persist the monitored-resource selection (no secrets to mask). Legacy single config."""
    health_cfg: dict = {
        "glue_jobs": data.glue_jobs,
        "glue_workflows": data.glue_workflows,
        "lambda_functions": data.lambda_functions,
        "datasync_tasks": [t.model_dump() for t in data.datasync_tasks],
    }
    return _upsert_app_config(db, health_config=health_cfg)


# ── Health profiles — named resource sets, stored in the health_profiles JSONB list ──


def _name_key(name: str) -> str:
    return name.strip().casefold()


def _empty_resources() -> dict:
    return {k: [] for k in _RESOURCE_KEYS}


def _default_from_legacy(health_cfg: dict) -> dict:
    """Surface a pre-profiles ``health_config`` as a 'Default' profile."""
    return {"name": "Default", **{k: health_cfg.get(k, []) for k in _RESOURCE_KEYS}}


def _legacy_has_resources(health_cfg: object | None) -> bool:
    if not isinstance(health_cfg, dict):
        return False
    return any(health_cfg.get(k) for k in _RESOURCE_KEYS)


def _legacy_profiles(health_cfg: object | None) -> list[dict] | None:
    if not isinstance(health_cfg, list):
        return None
    if not all(isinstance(profile, dict) and isinstance(profile.get("name"), str) for profile in health_cfg):
        return None
    return [dict(profile) for profile in health_cfg]


def get_profiles(db: Session) -> list[dict]:
    """Return all health profiles.

    Once profiles have been managed the stored list wins (even when empty). Before that,
    ``health_config`` may contain either a legacy single resource dict or an older seeded
    list of profile dicts.
    """
    row = get_app_config(db)
    if row is not None and row.health_profiles is not None:
        return [dict(p) for p in row.health_profiles]
    legacy_profiles = _legacy_profiles(row.health_config if row is not None else None)
    if legacy_profiles is not None:
        return legacy_profiles
    if row is not None and _legacy_has_resources(row.health_config):
        return [_default_from_legacy(row.health_config)]
    return []


def get_profile_resources(db: Session, name: str | None = None) -> dict | None:
    """Return one profile's resource dict; ``None`` selects the first profile."""
    profiles = get_profiles(db)
    if not profiles:
        return None
    if name is None:
        return profiles[0]
    key = _name_key(name)
    return next((p for p in profiles if _name_key(p["name"]) == key), None)


def _persist_profiles(db: Session, profiles: list[dict]) -> None:
    _upsert_app_config(db, health_profiles=profiles)


def create_profile(db: Session, name: str) -> dict:
    """Create a new empty profile; raise ProfileNameConflict on a duplicate name."""
    profiles = get_profiles(db)
    key = _name_key(name)
    if any(_name_key(p["name"]) == key for p in profiles):
        raise ProfileNameConflict(name)
    profile = {"name": name.strip(), **_empty_resources()}
    profiles.append(profile)
    _persist_profiles(db, profiles)
    return profile


def update_profile(db: Session, data: HealthProfileUpdate) -> dict:
    """Replace an existing profile's resource lists; raise ProfileNotFound if missing."""
    profiles = get_profiles(db)
    key = _name_key(data.name)
    for i, p in enumerate(profiles):
        if _name_key(p["name"]) == key:
            profiles[i] = {
                "name": p["name"],
                "glue_jobs": data.glue_jobs,
                "glue_workflows": data.glue_workflows,
                "lambda_functions": data.lambda_functions,
                "datasync_tasks": [t.model_dump() for t in data.datasync_tasks],
            }
            _persist_profiles(db, profiles)
            return profiles[i]
    raise ProfileNotFound(data.name)


def rename_profile(db: Session, name: str, new_name: str) -> dict:
    """Rename a profile; raise ProfileNotFound / ProfileNameConflict as appropriate."""
    profiles = get_profiles(db)
    key = _name_key(name)
    new_key = _name_key(new_name)
    if new_key != key and any(_name_key(p["name"]) == new_key for p in profiles):
        raise ProfileNameConflict(new_name)
    for p in profiles:
        if _name_key(p["name"]) == key:
            p["name"] = new_name.strip()
            _persist_profiles(db, profiles)
            return dict(p)
    raise ProfileNotFound(name)


def delete_profile(db: Session, name: str) -> None:
    """Delete a profile by name; raise ProfileNotFound if missing."""
    profiles = get_profiles(db)
    key = _name_key(name)
    remaining = [p for p in profiles if _name_key(p["name"]) != key]
    if len(remaining) == len(profiles):
        raise ProfileNotFound(name)
    _persist_profiles(db, remaining)
