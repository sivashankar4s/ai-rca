"""Failure-pattern signature computation and knowledge-base matching.

A "signature" identifies a recurring failure pattern as
``(component_name, error_code, stage)``. See CRM_PLAN.md section 5.
"""
from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.orm import Session

from ..db.models import RootCauseSignature
from ..repositories import signature_repo


def compute_signature_hash(
    component_name: str | None, error_code: str | None, stage: str | None
) -> str:
    """Deterministic hash identifying a failure pattern."""
    raw = "|".join(
        part.strip().lower()
        for part in (component_name or "", error_code or "", stage or "")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def match_or_create_signature(
    db: Session,
    project_id: uuid.UUID,
    signature_hash: str,
    component_name: str | None,
    error_code: str | None,
    stage: str | None,
    root_cause: str,
    failure_category: str | None,
) -> tuple[RootCauseSignature, bool]:
    """Find an existing signature (project-scoped, falling back to global) or create one.

    Returns ``(signature, is_new)``. Existing signatures have their
    ``occurrence_count``/``last_seen`` bumped.
    """
    existing = signature_repo.find_signature(db, project_id, signature_hash)
    if existing is not None:
        signature_repo.touch_signature(db, existing)
        return existing, False

    created = signature_repo.create_signature(
        db,
        project_id=project_id,
        signature_hash=signature_hash,
        component_name=component_name,
        error_code=error_code,
        stage=stage,
        root_cause=root_cause,
        failure_category=failure_category,
    )
    return created, True
