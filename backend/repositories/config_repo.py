"""Repository for AppConfig — single-row global credential storage (Constitution Principle III)."""

import logging

from sqlalchemy.orm import Session

from backend.db.models import AppConfig
from backend.models.schemas import (
    MASK_SENTINEL,
    AwsConfigUpdate,
    CloudWatchConfigUpdate,
    GithubMcpConfigUpdate,
)

logger = logging.getLogger(__name__)


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
