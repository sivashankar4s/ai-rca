from unittest.mock import patch

from backend.agents.code_analysis_agent import CodeAnalysisAgent
from backend.config import settings


def test_analyze_returns_none_when_repo_not_configured():
    original_repo = settings.github_repo
    try:
        settings.github_repo = ""
        result = CodeAnalysisAgent().analyze("1h")
        assert result is None
    finally:
        settings.github_repo = original_repo


def test_analyze_returns_error_when_token_missing():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "acme/widgets"
        settings.github_token = ""
        result = CodeAnalysisAgent().analyze("1h")
        assert result is not None
        assert result.repo == "acme/widgets"
        assert result.items == []
        assert result.error and "GITHUB_TOKEN" in result.error
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_analyze_combines_commits_and_pull_requests():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "acme/widgets"
        settings.github_token = "fake-token"

        commits = [
            {
                "commit": {
                    "message": "Fix S3 retry bug\n\nDetails here",
                    "author": {"name": "alice", "date": "2026-06-12T01:00:00Z"},
                },
                "html_url": "https://github.com/acme/widgets/commit/abc123",
            }
        ]
        pulls = [
            {
                "title": "Add retry backoff",
                "user": {"login": "bob"},
                "updated_at": "2026-06-12T02:00:00Z",
                "html_url": "https://github.com/acme/widgets/pull/42",
            }
        ]

        def fake_call(tool_name, arguments):
            if tool_name == "list_commits":
                return commits
            if tool_name == "list_pull_requests":
                return pulls
            raise AssertionError(f"unexpected tool: {tool_name}")

        with patch("backend.agents.code_analysis_agent.call_github_tool", side_effect=fake_call):
            result = CodeAnalysisAgent().analyze("1h", start_date="2026-06-12T00:00:00Z")

        assert result is not None
        assert result.error is None
        assert result.repo == "acme/widgets"
        assert len(result.items) == 2

        commit_item = next(i for i in result.items if i.type == "commit")
        assert commit_item.title == "Fix S3 retry bug"
        assert commit_item.author == "alice"
        assert commit_item.url == "https://github.com/acme/widgets/commit/abc123"

        pr_item = next(i for i in result.items if i.type == "pull_request")
        assert pr_item.title == "Add retry backoff"
        assert pr_item.author == "bob"
        assert pr_item.url == "https://github.com/acme/widgets/pull/42"
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_analyze_handles_mcp_failure_gracefully():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "acme/widgets"
        settings.github_token = "fake-token"

        with patch(
            "backend.agents.code_analysis_agent.call_github_tool",
            side_effect=RuntimeError("github-mcp-server: command not found"),
        ):
            result = CodeAnalysisAgent().analyze("1h")

        assert result is not None
        assert result.items == []
        assert "command not found" in result.error
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token
