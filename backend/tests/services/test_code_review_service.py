"""Tests for backend.services.code_review_service — both existing review functions
and the new post_review_to_pull_request flow (feature 003-inline-pr-comments)."""

from unittest.mock import call, patch

import pytest

from backend.config import settings
from backend.models.schemas import CodeReviewFinding, CodeReviewResult
from backend.services import code_review_service

_REVIEW_JSON = """{
  "summary": "Adds a retry helper with a raw SQL query.",
  "findings": [
    {
      "severity": "high",
      "category": "sql_injection",
      "file": "app/db.py",
      "line": 42,
      "title": "String-formatted SQL query",
      "description": "User input is interpolated directly into the SQL string.",
      "recommendation": "Use parameterized queries instead."
    }
  ]
}"""


# ── Existing review functions ──────────────────────────────────────────────────

def test_review_pull_request_not_configured():
    original = settings.github_repo
    try:
        settings.github_repo = ""
        result = code_review_service.review_pull_request(42)
        assert result.error == "GITHUB_REPO is not configured."
    finally:
        settings.github_repo = original


def test_review_pull_request_missing_token():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = ""
        result = code_review_service.review_pull_request(42)
        assert result.repo == "owner/repo"
        assert "GITHUB_TOKEN" in result.error
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_review_pull_request_success():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"
        diff = "diff --git a/app/db.py b/app/db.py\n+cursor.execute(f\"SELECT * FROM users\")"

        with patch("backend.services.code_review_service.call_github_tool", return_value=diff), \
             patch("backend.services.code_review_service.get_llm") as mock_get_llm:
            mock_get_llm.return_value.invoke.return_value = _REVIEW_JSON
            result = code_review_service.review_pull_request(42)

        assert result.repo == "owner/repo"
        assert result.target == "PR #42"
        assert result.error is None
        assert len(result.findings) == 1
        assert result.findings[0].severity == "high"
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_review_pull_request_mcp_error():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"
        with patch("backend.services.code_review_service.call_github_tool", side_effect=RuntimeError("MCP down")):
            result = code_review_service.review_pull_request(42)
        assert result.error == "MCP down"
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_review_pull_request_non_string_diff():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"
        with patch("backend.services.code_review_service.call_github_tool", return_value={"diff": "some diff"}), \
             patch("backend.services.code_review_service.get_llm") as mock_llm:
            mock_llm.return_value.invoke.return_value = '{"summary": "ok", "findings": []}'
            result = code_review_service.review_pull_request(42)
        assert result.error is None
        assert result.summary == "ok"
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_review_branch_not_configured():
    original = settings.github_repo
    try:
        settings.github_repo = ""
        result = code_review_service.review_branch("feature/foo")
        assert result.error == "GITHUB_REPO is not configured."
    finally:
        settings.github_repo = original


def test_review_branch_missing_token():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = ""
        result = code_review_service.review_branch("feature/foo")
        assert "GITHUB_TOKEN" in result.error
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_review_branch_success():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"
        commit = {"files": [{"filename": "app/db.py", "patch": "+cursor.execute(...)"}]}

        with patch("backend.services.code_review_service.call_github_tool", return_value=commit), \
             patch("backend.services.code_review_service.get_llm") as mock_get_llm:
            mock_get_llm.return_value.invoke.return_value = _REVIEW_JSON
            result = code_review_service.review_branch("feature/foo")

        assert result.repo == "owner/repo"
        assert result.target == "branch feature/foo"
        assert result.error is None
        assert len(result.findings) == 1
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_review_branch_no_patches():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"
        commit = {"files": [{"filename": "README.md"}]}

        with patch("backend.services.code_review_service.call_github_tool", return_value=commit), \
             patch("backend.services.code_review_service.get_llm") as mock_get_llm:
            mock_get_llm.return_value.invoke.return_value = '{"summary": "ok", "findings": []}'
            result = code_review_service.review_branch("feature/foo")
        assert result.summary == "No changes found to review."
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_review_branch_mcp_error():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"
        with patch("backend.services.code_review_service.call_github_tool", side_effect=RuntimeError("err")):
            result = code_review_service.review_branch("feature/foo")
        assert result.error == "err"
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_review_diff_no_changes():
    result = code_review_service._review_diff("owner/repo", "branch empty", "")
    assert result.summary == "No changes found to review."
    assert result.findings == []


def test_review_diff_llm_error():
    with patch("backend.services.code_review_service.get_llm") as mock_llm:
        mock_llm.return_value.invoke.side_effect = RuntimeError("LLM down")
        result = code_review_service._review_diff("owner/repo", "PR #1", "some diff")
    assert result.error == "LLM down"


def test_review_diff_invalid_json():
    with patch("backend.services.code_review_service.get_llm") as mock_llm:
        mock_llm.return_value.invoke.return_value = "not json at all"
        result = code_review_service._review_diff("owner/repo", "PR #1", "some diff")
    assert result.error is not None
    assert "valid review" in result.error


def test_review_diff_json_parse_error_in_braces():
    """_extract_json_object logs debug and returns None when text has braces but invalid JSON."""
    with patch("backend.services.code_review_service.get_llm") as mock_llm:
        mock_llm.return_value.invoke.return_value = "{ definitely not : valid json !! }"
        result = code_review_service._review_diff("owner/repo", "PR #1", "some diff")
    assert result.error is not None
    assert "valid review" in result.error


def test_review_diff_findings_without_title_skipped():
    json_with_no_title = '{"summary": "ok", "findings": [{"severity": "low", "category": "style", "description": "x"}]}'
    with patch("backend.services.code_review_service.get_llm") as mock_llm:
        mock_llm.return_value.invoke.return_value = json_with_no_title
        result = code_review_service._review_diff("owner/repo", "PR #1", "diff")
    assert result.findings == []


# ── Helpers: _is_anchorable and _format_comment_body ──────────────────────────

def _finding(**kwargs) -> CodeReviewFinding:
    defaults = {"severity": "high", "category": "bug", "title": "T", "description": "D"}
    return CodeReviewFinding(**{**defaults, **kwargs})


@pytest.mark.parametrize("file,line,expected", [
    ("app/db.py", 42, True),
    ("app/db.py", 1, True),
    ("app/db.py", 0, False),
    ("app/db.py", -1, False),
    ("app/db.py", None, False),
    ("", 42, False),
    (None, 42, False),
])
def test_is_anchorable(file, line, expected):
    f = _finding(file=file, line=line)
    assert code_review_service._is_anchorable(f) is expected


def test_format_comment_body_with_recommendation():
    f = _finding(severity="high", category="sql_injection", title="SQL Injection",
                 description="User input directly in query.", recommendation="Use params.")
    body = code_review_service._format_comment_body(f)
    assert "[HIGH] SQL Injection" in body
    assert "sql_injection" in body
    assert "User input directly in query." in body
    assert "Recommendation" in body
    assert "Use params." in body


def test_format_comment_body_without_recommendation():
    f = _finding(severity="low", category="style", title="Style", description="Minor style issue.")
    body = code_review_service._format_comment_body(f)
    assert "[LOW] Style" in body
    assert "Recommendation" not in body


# ── T005: post_review_to_pull_request — happy path ───────────────────────────

def test_post_review_not_configured():
    original = settings.github_repo
    try:
        settings.github_repo = ""
        review = CodeReviewResult(repo="", target="PR #42", findings=[_finding(file="a.py", line=1)])
        result = code_review_service.post_review_to_pull_request(42, review)
        assert result.posted is False
        assert "GITHUB_REPO" in result.error
    finally:
        settings.github_repo = original


def test_post_review_missing_token():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = ""
        review = CodeReviewResult(repo="", target="PR #42", findings=[_finding(file="a.py", line=1)])
        result = code_review_service.post_review_to_pull_request(42, review)
        assert result.posted is False
        assert "GITHUB_TOKEN" in result.error
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_post_review_empty_findings():
    """FR-008: empty findings → no MCP calls, posted=False with error."""
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"
        review = CodeReviewResult(repo="owner/repo", target="PR #42", findings=[])
        with patch("backend.services.code_review_service.call_github_tool") as mock_mcp:
            result = code_review_service.post_review_to_pull_request(42, review)
            mock_mcp.assert_not_called()
        assert result.posted is False
        assert result.error is not None
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_post_review_happy_path_all_anchorable():
    """T005: create → add_comment (×N) → submit; returns posted=True with correct counts."""
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"

        findings = [
            _finding(file="a.py", line=10, title="F1"),
            _finding(file="b.py", line=20, title="F2"),
        ]
        review = CodeReviewResult(repo="owner/repo", target="PR #42",
                                  summary="Two issues found.", findings=findings)

        create_resp = {"id": 999}
        submit_resp = {"html_url": "https://github.com/owner/repo/pull/42#pullrequestreview-999"}
        mcp_side_effects = [create_resp, None, None, submit_resp]

        with patch("backend.services.code_review_service.call_github_tool",
                   side_effect=mcp_side_effects) as mock_mcp:
            result = code_review_service.post_review_to_pull_request(42, review)

        assert result.posted is True
        assert result.inline_comment_count == 2
        assert result.summary_only_count == 0
        assert result.verdict == "COMMENT"
        assert "pullrequestreview-999" in result.review_url
        assert result.error is None

        calls = mock_mcp.call_args_list
        assert calls[0] == call("pull_request_review_write",
                                {"method": "create", "owner": "owner", "repo": "repo", "pullNumber": 42})
        assert calls[1][0][0] == "add_comment_to_pending_review"
        assert calls[2][0][0] == "add_comment_to_pending_review"
        assert calls[3][0][0] == "pull_request_review_write"
        assert calls[3][0][1]["method"] == "submit"
        assert calls[3][0][1]["event"] == "COMMENT"
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_post_review_review_url_fallback():
    """When submit returns no html_url, falls back to the PR URL."""
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"
        findings = [_finding(file="a.py", line=1)]
        review = CodeReviewResult(repo="owner/repo", target="PR #5", findings=findings)
        mcp_side_effects = [{"id": 1}, None, {}]

        with patch("backend.services.code_review_service.call_github_tool",
                   side_effect=mcp_side_effects):
            result = code_review_service.post_review_to_pull_request(5, review)

        assert result.posted is True
        assert result.review_url == "https://github.com/owner/repo/pull/5"
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


# ── T010: mixed / non-anchorable findings ────────────────────────────────────

def test_post_review_mixed_findings():
    """T010a: mixed list → correct inline_comment_count and summary_only_count."""
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"

        findings = [
            _finding(file="a.py", line=10, title="Inline"),
            _finding(file=None, line=None, title="Non-inline"),
        ]
        review = CodeReviewResult(repo="owner/repo", target="PR #42",
                                  summary="Summary.", findings=findings)
        mcp_side_effects = [{"id": 1}, None, {"html_url": "https://github.com/owner/repo/pull/42#review-1"}]

        with patch("backend.services.code_review_service.call_github_tool",
                   side_effect=mcp_side_effects) as mock_mcp:
            result = code_review_service.post_review_to_pull_request(42, review)

        assert result.posted is True
        assert result.inline_comment_count == 1
        assert result.summary_only_count == 1

        submit_call = mock_mcp.call_args_list[-1]
        submit_body = submit_call[0][1]["body"]
        assert "Non-inline" in submit_body
        assert "Additional Findings" in submit_body
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_post_review_all_non_anchorable():
    """T010b: all non-anchorable → zero inline comments, all in review body."""
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"

        findings = [
            _finding(file=None, line=None, title="NI-1"),
            _finding(file="", line=0, title="NI-2"),
        ]
        review = CodeReviewResult(repo="owner/repo", target="PR #42",
                                  summary="Summary.", findings=findings)
        mcp_side_effects = [{"id": 1}, {"html_url": "https://github.com/owner/repo/pull/42#review-1"}]

        with patch("backend.services.code_review_service.call_github_tool",
                   side_effect=mcp_side_effects) as mock_mcp:
            result = code_review_service.post_review_to_pull_request(42, review)

        assert result.posted is True
        assert result.inline_comment_count == 0
        assert result.summary_only_count == 2

        add_comment_calls = [
            c for c in mock_mcp.call_args_list if c[0][0] == "add_comment_to_pending_review"
        ]
        assert len(add_comment_calls) == 0
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


# ── T012: error handling / cleanup ───────────────────────────────────────────

def test_post_review_mcp_failure_cleans_up_pending_review():
    """T012b: failure after create → delete pending review, return posted=False."""
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"
        findings = [_finding(file="a.py", line=1, title="X")]
        review = CodeReviewResult(repo="owner/repo", target="PR #42",
                                  summary="Summary.", findings=findings)

        create_resp = {"id": 777}
        mcp_side_effects = [
            create_resp,
            RuntimeError("comment rejected"),
        ]

        with patch("backend.services.code_review_service.call_github_tool",
                   side_effect=mcp_side_effects) as mock_mcp:
            result = code_review_service.post_review_to_pull_request(42, review)

        assert result.posted is False
        assert "comment rejected" in result.error

        delete_call = mock_mcp.call_args_list[-1]
        assert delete_call[0][0] == "pull_request_review_write"
        assert delete_call[0][1]["method"] == "delete"
        assert delete_call[0][1]["reviewId"] == 777
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_post_review_delete_also_fails():
    """Cleanup delete failure is logged but the original error is still returned."""
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"
        findings = [_finding(file="a.py", line=1)]
        review = CodeReviewResult(repo="owner/repo", target="PR #42", findings=findings)

        mcp_side_effects = [
            {"id": 888},
            RuntimeError("add_comment failed"),
            RuntimeError("delete failed too"),
        ]

        with patch("backend.services.code_review_service.call_github_tool",
                   side_effect=mcp_side_effects):
            result = code_review_service.post_review_to_pull_request(42, review)

        assert result.posted is False
        assert "add_comment failed" in result.error
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_post_review_mcp_failure_no_pending_review_id():
    """When create returns no id, cleanup is skipped but error still returned."""
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"
        findings = [_finding(file="a.py", line=1)]
        review = CodeReviewResult(repo="owner/repo", target="PR #42", findings=findings)

        mcp_side_effects = [
            {},
            RuntimeError("add_comment failed"),
        ]

        with patch("backend.services.code_review_service.call_github_tool",
                   side_effect=mcp_side_effects) as mock_mcp:
            result = code_review_service.post_review_to_pull_request(42, review)

        assert result.posted is False
        delete_calls = [
            c for c in mock_mcp.call_args_list
            if c[0][0] == "pull_request_review_write" and c[0][1].get("method") == "delete"
        ]
        assert len(delete_calls) == 0
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_post_review_create_returns_non_dict():
    """When create response is not a dict, pending_review_id stays None (no delete on failure)."""
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"
        findings = [_finding(file="a.py", line=1)]
        review = CodeReviewResult(repo="owner/repo", target="PR #42", findings=findings)
        mcp_side_effects = [
            "pending-review-as-string",
            RuntimeError("add_comment failed"),
        ]
        with patch("backend.services.code_review_service.call_github_tool",
                   side_effect=mcp_side_effects) as mock_mcp:
            result = code_review_service.post_review_to_pull_request(42, review)

        assert result.posted is False
        delete_calls = [
            c for c in mock_mcp.call_args_list
            if c[0][0] == "pull_request_review_write" and c[0][1].get("method") == "delete"
        ]
        assert len(delete_calls) == 0
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_post_review_submit_returns_non_dict():
    """When submit returns a non-dict, falls back to PR URL."""
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"
        findings = [_finding(file="a.py", line=1)]
        review = CodeReviewResult(repo="owner/repo", target="PR #7", findings=findings)
        mcp_side_effects = [{"id": 1}, None, "ok"]

        with patch("backend.services.code_review_service.call_github_tool",
                   side_effect=mcp_side_effects):
            result = code_review_service.post_review_to_pull_request(7, review)

        assert result.posted is True
        assert result.review_url == "https://github.com/owner/repo/pull/7"
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_post_review_submit_returns_url_field():
    """When submit returns 'url' (not 'html_url'), it is used as review_url."""
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"
        findings = [_finding(file="a.py", line=1)]
        review = CodeReviewResult(repo="owner/repo", target="PR #42", findings=findings)
        mcp_side_effects = [{"id": 1}, None, {"url": "https://api.github.com/reviews/1"}]

        with patch("backend.services.code_review_service.call_github_tool",
                   side_effect=mcp_side_effects):
            result = code_review_service.post_review_to_pull_request(42, review)

        assert result.posted is True
        assert result.review_url == "https://api.github.com/reviews/1"
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token
