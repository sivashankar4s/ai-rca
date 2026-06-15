from unittest.mock import patch

from backend.config import settings
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

        diff = "diff --git a/app/db.py b/app/db.py\n+cursor.execute(f\"SELECT * FROM users WHERE id={user_id}\")"

        with patch("backend.services.code_review_service.call_github_tool", return_value=diff), \
             patch("backend.services.code_review_service.get_llm") as mock_get_llm:
            mock_get_llm.return_value.invoke.return_value = _REVIEW_JSON
            result = code_review_service.review_pull_request(42)

        assert result.repo == "owner/repo"
        assert result.target == "PR #42"
        assert result.error is None
        assert "retry helper" in result.summary
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.severity == "high"
        assert finding.category == "sql_injection"
        assert finding.file == "app/db.py"
        assert finding.line == 42
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_review_branch_success():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"

        commit = {
            "files": [
                {"filename": "app/db.py", "patch": "+cursor.execute(f\"SELECT * FROM users WHERE id={user_id}\")"}
            ]
        }

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


def test_review_diff_no_changes():
    result = code_review_service._review_diff("owner/repo", "branch empty", "")
    assert result.summary == "No changes found to review."
    assert result.findings == []
