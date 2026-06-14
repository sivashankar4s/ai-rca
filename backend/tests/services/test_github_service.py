from unittest.mock import patch

import pytest

from backend.config import settings
from backend.services import github_service


@pytest.mark.parametrize(
    "repo,expected",
    [
        ("owner/repo", ("owner", "repo")),
        ("https://github.com/owner/repo", ("owner", "repo")),
        ("https://github.com/owner/repo.git", ("owner", "repo")),
        ("https://github.com/owner/repo/", ("owner", "repo")),
        ("", None),
        ("not-a-repo", None),
    ],
)
def test_parse_repo(repo, expected):
    assert github_service.parse_repo(repo) == expected


def test_list_branches_not_configured():
    original = settings.github_repo
    try:
        settings.github_repo = ""
        result = github_service.list_branches()
        assert result.error == "GITHUB_REPO is not configured."
        assert result.branches == []
    finally:
        settings.github_repo = original


def test_list_branches_missing_token():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = ""
        result = github_service.list_branches()
        assert result.repo == "owner/repo"
        assert "GITHUB_TOKEN" in result.error
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_list_branches_success():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "https://github.com/owner/repo"
        settings.github_token = "fake-token"

        branches = [
            {"name": "main", "sha": "abc123", "protected": True},
            {"name": "feature/foo", "commit": {"sha": "def456"}, "protected": False},
        ]

        with patch("backend.services.github_service.call_github_tool", return_value=branches):
            result = github_service.list_branches()

        assert result.repo == "owner/repo"
        assert result.error is None
        assert len(result.branches) == 2
        assert result.branches[0].name == "main"
        assert result.branches[0].protected is True
        assert result.branches[1].sha == "def456"
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_list_pull_requests_success():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"

        prs = [
            {
                "number": 42,
                "title": "Add retry backoff",
                "state": "open",
                "user": {"login": "bob"},
                "html_url": "https://github.com/owner/repo/pull/42",
                "updated_at": "2026-06-12T02:00:00Z",
                "head": {"ref": "feature/retry"},
            }
        ]

        with patch("backend.services.github_service.call_github_tool", return_value=prs):
            result = github_service.list_pull_requests("open")

        assert result.repo == "owner/repo"
        assert result.error is None
        assert len(result.pull_requests) == 1
        pr = result.pull_requests[0]
        assert pr.number == 42
        assert pr.title == "Add retry backoff"
        assert pr.author == "bob"
        assert pr.branch == "feature/retry"
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token


def test_get_repo_info_not_configured():
    original = settings.github_repo
    try:
        settings.github_repo = ""
        result = github_service.get_repo_info()
        assert result.configured is False
    finally:
        settings.github_repo = original


def test_get_repo_info_success():
    original_repo, original_token = settings.github_repo, settings.github_token
    try:
        settings.github_repo = "owner/repo"
        settings.github_token = "fake-token"

        data = {
            "items": [{
                "default_branch": "main",
                "description": "Sample repo",
                "html_url": "https://github.com/owner/repo",
            }]
        }

        with patch("backend.services.github_service.call_github_tool", return_value=data):
            result = github_service.get_repo_info()

        assert result.configured is True
        assert result.repo == "owner/repo"
        assert result.default_branch == "main"
        assert result.description == "Sample repo"
        assert result.url == "https://github.com/owner/repo"
    finally:
        settings.github_repo, settings.github_token = original_repo, original_token
