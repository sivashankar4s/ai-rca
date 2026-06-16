from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import CaseSignatureLink, RootCauseSignature


def find_signature(
    db: Session, project_id: uuid.UUID, signature_hash: str
) -> RootCauseSignature | None:
    """Look up a signature scoped to this project, falling back to a global one."""
    project_match = db.execute(
        select(RootCauseSignature).where(
            RootCauseSignature.project_id == project_id,
            RootCauseSignature.signature_hash == signature_hash,
        )
    ).scalar_one_or_none()
    if project_match is not None:
        return project_match

    return db.execute(
        select(RootCauseSignature).where(
            RootCauseSignature.project_id.is_(None),
            RootCauseSignature.signature_hash == signature_hash,
        )
    ).scalar_one_or_none()


def touch_signature(db: Session, signature: RootCauseSignature) -> None:
    """Bump occurrence_count and last_seen on an existing signature match."""
    signature.occurrence_count += 1
    signature.last_seen = datetime.now(timezone.utc)
    db.flush()


def create_signature(
    db: Session,
    project_id: uuid.UUID,
    signature_hash: str,
    component_name: str | None,
    error_code: str | None,
    stage: str | None,
    root_cause: str,
    failure_category: str | None,
    fix_notes: str | None = None,
) -> RootCauseSignature:
    signature = RootCauseSignature(
        project_id=project_id,
        signature_hash=signature_hash,
        component_name=component_name,
        error_code=error_code,
        stage=stage,
        root_cause=root_cause,
        fix_notes=fix_notes,
        failure_category=failure_category,
        occurrence_count=1,
    )
    db.add(signature)
    db.flush()
    return signature


def link_case_to_signature(
    db: Session, case_id: uuid.UUID, signature_id: uuid.UUID
) -> CaseSignatureLink:
    link = db.get(CaseSignatureLink, {"case_id": case_id, "signature_id": signature_id})
    if link is not None:
        return link
    link = CaseSignatureLink(case_id=case_id, signature_id=signature_id)
    db.add(link)
    db.flush()
    return link
