"""AI Code Review — analyzes PR/branch diffs for bugs, security issues
(including SQL injection), Sonar-style code quality/formatting issues, and
feature recommendations, using the GitHub MCP server + configured LLM.
"""

import json
import logging

from ..config import settings
from ..mcp.client import call_github_tool
from ..models.schemas import CodeReviewFinding, CodeReviewResult
from ..plugin_registry import get_llm
from .github_service import parse_repo

logger = logging.getLogger(__name__)

MAX_DIFF_CHARS = 24000

_REVIEW_PROMPT = """You are a senior software engineer performing an automated code review on the git diff below.

Carefully review the changes and identify concrete issues. Focus on:
- Security vulnerabilities (e.g. SQL injection, command injection, XSS, hardcoded secrets/credentials, insecure deserialization, path traversal, SSRF, missing auth checks)
- Bugs and correctness issues (logic errors, null/undefined handling, off-by-one, race conditions, unhandled exceptions)
- Code quality / SonarQube-style issues (duplicated code, overly complex functions, dead code, poor naming, missing error handling, magic numbers)
- Formatting / style issues that violate common conventions
- Recommendations for new features or improvements suggested by the context of this change

For each issue found, provide the file path and line number from the diff when possible.

Return ONLY a valid JSON object (no markdown fences, no explanation) with this exact shape:
{{
  "summary": "2-3 sentence overview of the change and its overall quality/risk",
  "findings": [
    {{
      "severity": "critical | high | medium | low | info",
      "category": "security | sql_injection | bug | code_quality | performance | style | suggestion",
      "file": "path/to/file.py",
      "line": 42,
      "title": "Short title",
      "description": "What the issue is and why it matters",
      "recommendation": "Specific fix or improvement"
    }}
  ]
}}

If no issues are found, return an empty "findings" array but still include a "summary".

Diff ({target}):
{diff}"""


def _extract_json_object(text: str) -> dict | None:
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError) as exc:
        logger.debug("JSON extraction failed: %s  raw_response_start=%s", exc, text[:120])
    return None


def _review_diff(repo_label: str, target: str, diff_text: str) -> CodeReviewResult:
    if not diff_text.strip():
        return CodeReviewResult(repo=repo_label, target=target, summary="No changes found to review.")

    diff_text = diff_text[:MAX_DIFF_CHARS]
    prompt = _REVIEW_PROMPT.format(target=target, diff=diff_text)

    try:
        response = get_llm().invoke(prompt, max_tokens=4096)
    except Exception as exc:
        logger.warning("Code review LLM call failed: %s", exc)
        return CodeReviewResult(repo=repo_label, target=target, error=str(exc))

    data = _extract_json_object(response)
    if not data:
        logger.warning("Code review LLM did not return valid JSON")
        return CodeReviewResult(
            repo=repo_label, target=target,
            error="LLM did not return a valid review.",
            summary=response[:500],
        )

    findings = [
        CodeReviewFinding(
            severity=f.get("severity", "info"),
            category=f.get("category", "suggestion"),
            file=f.get("file"),
            line=f.get("line"),
            title=f.get("title", ""),
            description=f.get("description", ""),
            recommendation=f.get("recommendation"),
        )
        for f in data.get("findings", [])
        if f.get("title")
    ]

    return CodeReviewResult(
        repo=repo_label,
        target=target,
        summary=data.get("summary", ""),
        findings=findings,
    )


def review_pull_request(number: int) -> CodeReviewResult:
    parsed = parse_repo(settings.github_repo)
    if not parsed:
        return CodeReviewResult(repo="", target=f"PR #{number}", error="GITHUB_REPO is not configured.")

    owner, name = parsed
    repo_label = f"{owner}/{name}"
    target = f"PR #{number}"
    if not settings.github_token:
        return CodeReviewResult(repo=repo_label, target=target, error="GITHUB_TOKEN is not configured.")

    try:
        diff = call_github_tool(
            "pull_request_read",
            {"method": "get_diff", "owner": owner, "repo": name, "pullNumber": number},
        )
        diff_text = diff if isinstance(diff, str) else json.dumps(diff)
        return _review_diff(repo_label, target, diff_text)
    except Exception as exc:
        logger.warning("GitHub MCP get_diff failed: %s", exc)
        return CodeReviewResult(repo=repo_label, target=target, error=str(exc))


def review_branch(branch: str) -> CodeReviewResult:
    parsed = parse_repo(settings.github_repo)
    if not parsed:
        return CodeReviewResult(repo="", target=f"branch {branch}", error="GITHUB_REPO is not configured.")

    owner, name = parsed
    repo_label = f"{owner}/{name}"
    target = f"branch {branch}"
    if not settings.github_token:
        return CodeReviewResult(repo=repo_label, target=target, error="GITHUB_TOKEN is not configured.")

    try:
        commit = call_github_tool(
            "get_commit",
            {"owner": owner, "repo": name, "sha": branch, "detail": "full_patch"},
        )
        files = commit.get("files", []) if isinstance(commit, dict) else []
        diff_text = "\n".join(
            f"--- {f.get('filename')}\n{f.get('patch', '')}"
            for f in files
            if f.get("patch")
        )
        return _review_diff(repo_label, target, diff_text)
    except Exception as exc:
        logger.warning("GitHub MCP get_commit failed: %s", exc)
        return CodeReviewResult(repo=repo_label, target=target, error=str(exc))
