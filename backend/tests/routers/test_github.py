"""Contract tests for backend/routers/github.py — FastAPI TestClient, service mocked."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.models.schemas import (
    BranchesResponse,
    BranchInfo,
    CodeReviewResult,
    PostedReviewResult,
    PullRequestInfo,
    PullRequestsResponse,
    RepoInfo,
)

client = TestClient(app)

_FINDING_BODY = {
    "severity": "high",
    "category": "sql_injection",
    "file": "app/db.py",
    "line": 42,
    "title": "SQL Injection",
    "description": "User input in query.",
    "recommendation": "Use params.",
}

_REVIEW_BODY = {
    "repo": "owner/repo",
    "target": "PR #42",
    "summary": "Two issues found.",
    "findings": [_FINDING_BODY],
}

_POSTED_OK = PostedReviewResult(
    repo="owner/repo",
    target="PR #42",
    posted=True,
    review_url="https://github.com/owner/repo/pull/42#pullrequestreview-1",
    inline_comment_count=1,
    summary_only_count=0,
    verdict="COMMENT",
)


# ── GET /api/github/repo ──────────────────────────────────────────────────────

def test_get_repo():
    repo_info = RepoInfo(configured=True, repo="owner/repo", owner="owner", name="repo")
    with patch("backend.routers.github.github_service.get_repo_info", return_value=repo_info):
        resp = client.get("/api/github/repo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["repo"] == "owner/repo"


# ── GET /api/github/branches ──────────────────────────────────────────────────

def test_get_branches():
    branches_resp = BranchesResponse(
        repo="owner/repo",
        branches=[BranchInfo(name="main", sha="abc123", protected=True)],
    )
    with patch("backend.routers.github.github_service.list_branches", return_value=branches_resp):
        resp = client.get("/api/github/branches")
    assert resp.status_code == 200
    data = resp.json()
    assert data["repo"] == "owner/repo"
    assert len(data["branches"]) == 1
    assert data["branches"][0]["name"] == "main"


# ── GET /api/github/pull-requests ─────────────────────────────────────────────

def test_get_pull_requests():
    prs_resp = PullRequestsResponse(
        repo="owner/repo",
        pull_requests=[PullRequestInfo(number=42, title="Test PR", state="open")],
    )
    with patch("backend.routers.github.github_service.list_pull_requests", return_value=prs_resp):
        resp = client.get("/api/github/pull-requests")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pull_requests"][0]["number"] == 42


def test_get_pull_requests_with_state():
    prs_resp = PullRequestsResponse(repo="owner/repo", pull_requests=[])
    with patch(
        "backend.routers.github.github_service.list_pull_requests", return_value=prs_resp
    ) as mock_svc:
        resp = client.get("/api/github/pull-requests?state=closed")
    assert resp.status_code == 200
    mock_svc.assert_called_once_with("closed")


# ── GET /api/github/pull-requests/{number}/review ─────────────────────────────

def test_review_pull_request():
    review = CodeReviewResult(repo="owner/repo", target="PR #42", summary="ok")
    with patch(
        "backend.routers.github.code_review_service.review_pull_request", return_value=review
    ):
        resp = client.get("/api/github/pull-requests/42/review")
    assert resp.status_code == 200
    assert resp.json()["target"] == "PR #42"


# ── GET /api/github/branches/review ──────────────────────────────────────────

def test_review_branch():
    review = CodeReviewResult(repo="owner/repo", target="branch main", summary="ok")
    with patch("backend.routers.github.code_review_service.review_branch", return_value=review):
        resp = client.get("/api/github/branches/review?branch=main")
    assert resp.status_code == 200
    assert resp.json()["target"] == "branch main"


# ── T006: POST /api/github/pull-requests/{number}/review/comments ─────────────

def test_post_review_comments_success():
    """T006: 200 with posted=True when service succeeds."""
    with patch("backend.routers.github.code_review_service.post_review_to_pull_request",
               return_value=_POSTED_OK):
        resp = client.post("/api/github/pull-requests/42/review/comments", json=_REVIEW_BODY)

    assert resp.status_code == 200
    data = resp.json()
    assert data["posted"] is True
    assert data["inline_comment_count"] == 1
    assert data["verdict"] == "COMMENT"
    assert "pullrequestreview-1" in data["review_url"]


def test_post_review_comments_passes_number_and_body():
    """T006: service receives the correct PR number and CodeReviewResult."""
    with patch("backend.routers.github.code_review_service.post_review_to_pull_request",
               return_value=_POSTED_OK) as mock_svc:
        client.post("/api/github/pull-requests/99/review/comments", json=_REVIEW_BODY)

    call_args = mock_svc.call_args
    assert call_args[0][0] == 99
    assert call_args[0][1].findings[0].file == "app/db.py"


# ── T013: error / degradation contract ───────────────────────────────────────

def test_post_review_comments_empty_findings_returns_posted_false():
    """T013: empty findings → 200 with posted=False and populated error."""
    not_posted = PostedReviewResult(
        repo="owner/repo", target="PR #42", posted=False,
        error="Nothing to post: no findings.",
    )
    body_no_findings = {**_REVIEW_BODY, "findings": []}
    with patch("backend.routers.github.code_review_service.post_review_to_pull_request",
               return_value=not_posted):
        resp = client.post("/api/github/pull-requests/42/review/comments", json=body_no_findings)

    assert resp.status_code == 200
    data = resp.json()
    assert data["posted"] is False
    assert data["error"] is not None


def test_post_review_comments_unconfigured_returns_posted_false():
    """T013: GITHUB_REPO unset → 200 with posted=False."""
    not_posted = PostedReviewResult(
        repo="", target="PR #42", posted=False,
        error="GITHUB_REPO is not configured.",
    )
    with patch("backend.routers.github.code_review_service.post_review_to_pull_request",
               return_value=not_posted):
        resp = client.post("/api/github/pull-requests/42/review/comments", json=_REVIEW_BODY)

    assert resp.status_code == 200
    data = resp.json()
    assert data["posted"] is False
    assert "GITHUB_REPO" in data["error"]


def test_post_review_comments_invalid_body_returns_422():
    """Missing required fields on CodeReviewResult → 422 Unprocessable Entity."""
    resp = client.post("/api/github/pull-requests/42/review/comments", json={"bad": "body"})
    assert resp.status_code == 422
