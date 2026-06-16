"""Code Analysis Agent — surfaces recent commits & PRs that may relate to a failure.

Uses the GitHub MCP server (backend.mcp.client) to look up activity in the
configured repository within the failure's time window.
"""

import logging
from datetime import UTC, datetime, timedelta

from ..config import settings
from ..mcp.client import call_github_tool
from ..models.schemas import CodeAnalysisResult, CodeChangeItem
from ..services.github_service import parse_repo

logger = logging.getLogger(__name__)

_INTERVAL_MAP = {
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
    "1w": timedelta(weeks=1),
}

MAX_ITEMS_PER_KIND = 5


class CodeAnalysisAgent:
    """Looks up recent commits & pull requests in the configured GitHub repo
    that fall within the failure time window, for the on-call developer."""

    def analyze(
        self,
        time_range: str = "1h",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> CodeAnalysisResult | None:
        parsed = parse_repo(settings.github_repo)
        if not parsed:
            return None

        owner, name = parsed
        repo = f"{owner}/{name}"

        if not settings.github_token:
            return CodeAnalysisResult(
                repo=repo,
                items=[],
                error="GITHUB_TOKEN is not configured — set it in Configuration to enable code analysis.",
            )
        since = self._since(time_range, start_date)
        items: list[CodeChangeItem] = []

        try:
            commits = call_github_tool(
                "list_commits",
                {"owner": owner, "repo": name, "since": since, "perPage": MAX_ITEMS_PER_KIND},
            )
            for c in self._as_list(commits)[:MAX_ITEMS_PER_KIND]:
                commit = c.get("commit", {})
                author = commit.get("author") or {}
                items.append(CodeChangeItem(
                    type="commit",
                    title=(commit.get("message") or "").splitlines()[0][:200],
                    author=author.get("name"),
                    date=author.get("date"),
                    url=c.get("html_url"),
                ))
        except Exception as exc:
            logger.warning("GitHub MCP list_commits failed: %s", exc)
            return CodeAnalysisResult(repo=repo, items=[], error=str(exc))

        try:
            prs = call_github_tool(
                "list_pull_requests",
                {
                    "owner": owner,
                    "repo": name,
                    "state": "closed",
                    "sort": "updated",
                    "direction": "desc",
                    "perPage": MAX_ITEMS_PER_KIND,
                },
            )
            for pr in self._as_list(prs)[:MAX_ITEMS_PER_KIND]:
                updated = pr.get("updated_at")
                if since and updated and updated < since:
                    continue
                items.append(CodeChangeItem(
                    type="pull_request",
                    title=pr.get("title", ""),
                    author=(pr.get("user") or {}).get("login"),
                    date=updated,
                    url=pr.get("html_url"),
                ))
        except Exception as exc:
            logger.warning("GitHub MCP list_pull_requests failed: %s", exc)
            if not items:
                return CodeAnalysisResult(repo=repo, items=[], error=str(exc))

        return CodeAnalysisResult(repo=repo, items=items)

    @staticmethod
    def _since(time_range: str, start_date: str | None) -> str | None:
        if start_date:
            return start_date
        delta = _INTERVAL_MAP.get(time_range)
        if not delta:
            return None
        return (datetime.now(UTC) - delta).replace(microsecond=0).isoformat()

    @staticmethod
    def _as_list(data) -> list[dict]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("commits", "pull_requests", "items", "data"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []
