"""Source Code Intelligence — repo/branch/PR lookups via the GitHub MCP server."""

import logging

from ..config import settings
from ..mcp.client import call_github_tool
from ..models.schemas import (
    BranchesResponse,
    BranchInfo,
    PullRequestInfo,
    PullRequestsResponse,
    RepoInfo,
)

logger = logging.getLogger(__name__)


def parse_repo(repo: str) -> tuple[str, str] | None:
    """Parse 'owner/repo' or a full GitHub URL into (owner, repo)."""
    repo = (repo or "").strip()
    if not repo:
        return None
    if "github.com" in repo:
        repo = repo.split("github.com/", 1)[-1]
    repo = repo.strip("/")
    if repo.endswith(".git"):
        repo = repo[:-4]
    if "/" not in repo:
        return None
    owner, name = repo.split("/", 1)
    if not owner or not name:
        return None
    return owner, name


def _as_list(data, key: str) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in (key, "items", "data"):
            value = data.get(k)
            if isinstance(value, list):
                return value
    return []


def get_repo_info() -> RepoInfo:
    parsed = parse_repo(settings.github_repo)
    if not parsed:
        return RepoInfo(configured=False)

    owner, name = parsed
    repo_label = f"{owner}/{name}"
    if not settings.github_token:
        return RepoInfo(
            configured=True, repo=repo_label, owner=owner, name=name,
            error="GITHUB_TOKEN is not configured.",
        )

    try:
        data = call_github_tool("search_repositories", {"query": f"repo:{repo_label}"})
        items = data.get("items", []) if isinstance(data, dict) else []
        info = items[0] if items else {}
        return RepoInfo(
            configured=True,
            repo=repo_label,
            owner=owner,
            name=name,
            default_branch=info.get("default_branch"),
            description=info.get("description"),
            url=info.get("html_url"),
        )
    except Exception as exc:
        logger.warning("GitHub MCP search_repositories failed: %s", exc)
        return RepoInfo(configured=True, repo=repo_label, owner=owner, name=name, error=str(exc))


def list_branches() -> BranchesResponse:
    parsed = parse_repo(settings.github_repo)
    if not parsed:
        return BranchesResponse(repo="", error="GITHUB_REPO is not configured.")

    owner, name = parsed
    repo_label = f"{owner}/{name}"
    if not settings.github_token:
        return BranchesResponse(repo=repo_label, error="GITHUB_TOKEN is not configured.")

    try:
        data = call_github_tool("list_branches", {"owner": owner, "repo": name, "perPage": 100})
        branches = []
        for b in _as_list(data, "branches"):
            sha = b.get("sha") or (b.get("commit") or {}).get("sha")
            branches.append(BranchInfo(
                name=b.get("name", ""),
                sha=sha,
                protected=bool(b.get("protected", False)),
            ))
        return BranchesResponse(repo=repo_label, branches=branches)
    except Exception as exc:
        logger.warning("GitHub MCP list_branches failed: %s", exc)
        return BranchesResponse(repo=repo_label, error=str(exc))


def list_pull_requests(state: str = "open") -> PullRequestsResponse:
    parsed = parse_repo(settings.github_repo)
    if not parsed:
        return PullRequestsResponse(repo="", error="GITHUB_REPO is not configured.")

    owner, name = parsed
    repo_label = f"{owner}/{name}"
    if not settings.github_token:
        return PullRequestsResponse(repo=repo_label, error="GITHUB_TOKEN is not configured.")

    try:
        data = call_github_tool(
            "list_pull_requests",
            {"owner": owner, "repo": name, "state": state, "sort": "updated", "direction": "desc", "perPage": 20},
        )
        prs = []
        for pr in _as_list(data, "pull_requests"):
            prs.append(PullRequestInfo(
                number=pr.get("number", 0),
                title=pr.get("title", ""),
                state=pr.get("state", state),
                author=(pr.get("user") or {}).get("login"),
                url=pr.get("html_url"),
                updated_at=pr.get("updated_at"),
                branch=(pr.get("head") or {}).get("ref"),
            ))
        return PullRequestsResponse(repo=repo_label, pull_requests=prs)
    except Exception as exc:
        logger.warning("GitHub MCP list_pull_requests failed: %s", exc)
        return PullRequestsResponse(repo=repo_label, error=str(exc))
