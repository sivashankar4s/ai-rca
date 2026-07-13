"""Shared AWS helpers for health-check providers (feature 021).

``build_client`` centralises the single-source credential resolution used across the
four providers — DB ``aws_config`` when present, env settings otherwise, never mixed
(mirrors ``backend/providers/data_source/cloudwatch.py``).
"""

from datetime import datetime
from typing import Any

import boto3

from backend.config import settings


def build_client(service: str, aws_credentials: dict | None) -> Any:
    """Return a boto3 client for ``service`` using DB creds first, env as fallback."""
    creds = aws_credentials or {}
    if creds.get("access_key_id"):
        region = creds.get("region") or settings.aws_region
        access_key = creds.get("access_key_id")
        secret_key = creds.get("secret_access_key")
        session_token = creds.get("session_token") or None
    else:
        region = settings.aws_region
        access_key = settings.aws_access_key_id or None
        secret_key = settings.aws_secret_access_key or None
        session_token = settings.aws_session_token or None
    return boto3.client(
        service,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token,
    )


def in_window(ts: datetime | None, start: datetime, end: datetime) -> bool:
    """True when ``ts`` is a real timestamp inside ``[start, end]``."""
    return ts is not None and start <= ts <= end
