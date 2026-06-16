from backend.repositories import project_repo
from backend.services.signature_service import compute_signature_hash, match_or_create_signature


def test_compute_signature_hash_deterministic_and_case_insensitive():
    a = compute_signature_hash("dp-lz-s3-event-processor", "S3_PUT_FAILED", "lz-processor")
    b = compute_signature_hash("DP-LZ-S3-EVENT-PROCESSOR", "s3_put_failed", "LZ-PROCESSOR")
    assert a == b


def test_compute_signature_hash_differs_by_error_code():
    a = compute_signature_hash("componentA", "ERROR_1", "stage1")
    b = compute_signature_hash("componentA", "ERROR_2", "stage1")
    assert a != b


def test_match_or_create_signature_creates_then_matches(db_session):
    project = project_repo.get_or_create_default_project(db_session)
    sig_hash = compute_signature_hash("comp-x", "TIMEOUT", "stage-x")

    first, is_new_first = match_or_create_signature(
        db_session,
        project_id=project.id,
        signature_hash=sig_hash,
        component_name="comp-x",
        error_code="TIMEOUT",
        stage="stage-x",
        root_cause="Downstream service took too long to respond.",
        failure_category="Timeout",
    )
    assert is_new_first is True
    assert first.occurrence_count == 1

    second, is_new_second = match_or_create_signature(
        db_session,
        project_id=project.id,
        signature_hash=sig_hash,
        component_name="comp-x",
        error_code="TIMEOUT",
        stage="stage-x",
        root_cause="Downstream service took too long to respond.",
        failure_category="Timeout",
    )
    assert is_new_second is False
    assert second.id == first.id
    assert second.occurrence_count == 2
