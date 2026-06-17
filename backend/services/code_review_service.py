"""AI Code Review — analyzes PR/branch diffs and posts findings to GitHub."""

import json
import logging

from ..config import settings
from ..mcp.client import call_github_tool
from ..models.schemas import CodeReviewFinding, CodeReviewResult, PostedReviewResult
from ..plugin_registry import get_llm
from .github_service import parse_repo

logger = logging.getLogger(__name__)

MAX_DIFF_CHARS = 24000

_REVIEW_PROMPT = (
    "You are a senior software engineer performing an automated code review"
    " on the git diff below.\n\n"
    "Carefully review the changes and identify concrete issues. Focus on:\n"
    "- Security vulnerabilities (SQL injection, command injection, XSS, hardcoded secrets)\n"
    "- Bugs and correctness issues (logic errors, null handling, off-by-one, race conditions)\n"
    "- Code quality / SonarQube-style issues (duplicated code, dead code, poor naming)\n"
    "- Formatting / style issues that violate common conventions\n"
    "- Recommendations for improvements suggested by the context of this change\n\n"
    "For each issue found, provide the file path and line number from the diff when possible.\n\n"
    "Return ONLY a valid JSON object (no markdown fences, no explanation):\n"
    "{{\n"
    '  "summary": "2-3 sentence overview",\n'
    '  "findings": [\n'
    "    {{\n"
    '      "severity": "critical | high | medium | low | info",\n'
    '      "category": "security | sql_injection | bug | code_quality | performance | style",\n'
    '      "file": "path/to/file.py",\n'
    '      "line": 42,\n'
    '      "title": "Short title",\n'
    '      "description": "What the issue is and why it matters",\n'
    '      "recommendation": "Specific fix or improvement"\n'
    "    }}\n"
    "  ]\n"
    "}}\n\n"
    "If no issues are found, return an empty findings array but still include a summary.\n\n"
    "Diff ({target}):\n{diff}"
)


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
        return CodeReviewResult(
            repo=repo_label, target=target, summary="No changes found to review."
        )

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
            repo=repo_label,
            target=target,
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
        return CodeReviewResult(
            repo="", target=f"PR #{number}", error="GITHUB_REPO is not configured."
        )

    owner, name = parsed
    repo_label = f"{owner}/{name}"
    target = f"PR #{number}"
    if not settings.github_token:
        return CodeReviewResult(
            repo=repo_label, target=target, error="GITHUB_TOKEN is not configured."
        )

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
        return CodeReviewResult(
            repo="", target=f"branch {branch}", error="GITHUB_REPO is not configured."
        )

    owner, name = parsed
    repo_label = f"{owner}/{name}"
    target = f"branch {branch}"
    if not settings.github_token:
        return CodeReviewResult(
            repo=repo_label, target=target, error="GITHUB_TOKEN is not configured."
        )

    try:
        commit = call_github_tool(
            "get_commit",
            {"owner": owner, "repo": name, "sha": branch, "detail": "full_patch"},
        )
        files = commit.get("files", []) if isinstance(commit, dict) else []
        diff_text = "\n".join(
            f"--- {f.get('filename')}\n{f.get('patch', '')}" for f in files if f.get("patch")
        )
        return _review_diff(repo_label, target, diff_text)
    except Exception as exc:
        logger.warning("GitHub MCP get_commit failed: %s", exc)
        return CodeReviewResult(repo=repo_label, target=target, error=str(exc))


# ── Inline PR comment posting (feature 003-inline-pr-comments) ─────────────────


def _is_anchorable(finding: CodeReviewFinding) -> bool:
    """True when the finding can be posted as an inline diff comment."""
    return bool(finding.file) and isinstance(finding.line, int) and finding.line > 0


def _format_comment_body(finding: CodeReviewFinding) -> str:
    """Render a finding as a Markdown comment body."""
    parts = [
        f"**[{finding.severity.upper()}] {finding.title}**",
        f"*Category: {finding.category}*",
        "",
        finding.description,
    ]
    if finding.recommendation:
        parts += ["", f"**Recommendation**: {finding.recommendation}"]
    return "\n".join(parts)


def post_review_to_pull_request(number: int, review: CodeReviewResult) -> PostedReviewResult:
    """Post the AI review findings onto a PR as a single GitHub COMMENT review."""
    parsed = parse_repo(settings.github_repo)
    if not parsed:
        return PostedReviewResult(
            repo="", target=f"PR #{number}", error="GITHUB_REPO is not configured."
        )

    owner, name = parsed
    repo_label = f"{owner}/{name}"
    target = f"PR #{number}"

    if not settings.github_token:
        return PostedReviewResult(
            repo=repo_label, target=target, error="GITHUB_TOKEN is not configured."
        )

    if not review.findings:
        return PostedReviewResult(
            repo=repo_label, target=target, error="Nothing to post: no findings."
        )

    anchorable = [f for f in review.findings if _is_anchorable(f)]
    summary_only = [f for f in review.findings if not _is_anchorable(f)]

    body = review.summary
    if summary_only:
        non_inline = "\n\n---\n\n".join(_format_comment_body(f) for f in summary_only)
        body = f"{body}\n\n## Additional Findings (non-inline)\n\n{non_inline}"

    pending_review_id: int | None = None
    try:
        created = call_github_tool(
            "pull_request_review_write",
            {"method": "create", "owner": owner, "repo": name, "pullNumber": number},
        )
        pending_review_id = created.get("id") if isinstance(created, dict) else None

        for finding in anchorable:
            call_github_tool(
                "add_comment_to_pending_review",
                {
                    "owner": owner,
                    "repo": name,
                    "pullNumber": number,
                    "path": finding.file,
                    "line": finding.line,
                    "body": _format_comment_body(finding),
                    "subjectType": "line",
                    "side": "RIGHT",
                },
            )

        submitted = call_github_tool(
            "pull_request_review_write",
            {
                "method": "submit",
                "owner": owner,
                "repo": name,
                "pullNumber": number,
                "event": "COMMENT",
                "body": body,
            },
        )

        review_url: str | None = None
        if isinstance(submitted, dict):
            review_url = submitted.get("html_url") or submitted.get("url")
        if not review_url:
            review_url = f"https://github.com/{repo_label}/pull/{number}"

        return PostedReviewResult(
            repo=repo_label,
            target=target,
            posted=True,
            review_url=review_url,
            inline_comment_count=len(anchorable),
            summary_only_count=len(summary_only),
            verdict="COMMENT",
        )

    except Exception as exc:
        logger.warning("post_review_to_pull_request failed: %s", exc)
        if pending_review_id is not None:
            try:
                call_github_tool(
                    "pull_request_review_write",
                    {
                        "method": "delete",
                        "owner": owner,
                        "repo": name,
                        "pullNumber": number,
                        "reviewId": pending_review_id,
                    },
                )
            except Exception as del_exc:
                logger.warning("Failed to delete pending review %s: %s", pending_review_id, del_exc)
        return PostedReviewResult(repo=repo_label, target=target, error=str(exc))
