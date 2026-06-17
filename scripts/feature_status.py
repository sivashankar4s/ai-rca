#!/usr/bin/env python3
"""Parse specs/*/tasks.md and output GitHub-flavored markdown status tables.

Usage:
  python3 scripts/feature_status.py [feature|all]          # job summary format
  python3 scripts/feature_status.py --wiki [feature|all]   # full wiki page format
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 output so emoji render correctly on all platforms
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# Ordered metaswarm workflow artifacts for each feature
WORKFLOW_STEPS = [
    ("Spec",       "spec.md"),
    ("Research",   "research.md"),
    ("Data Model", "data-model.md"),
    ("API",        "contracts/api.md"),
    ("Plan",       "plan.md"),
    ("Tasks",      "tasks.md"),
    ("Quickstart", "quickstart.md"),
    ("Checklist",  "checklists/requirements.md"),
]


def fix_mojibake(text: str) -> str:
    """Fix UTF-8 text that was saved as cp1252 (e.g. â€" → —)."""
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def clean_phase_name(name: str) -> str:
    """Strip trailing punctuation noise and fix encoding."""
    name = fix_mojibake(name)
    # Remove trailing separators left by some tasks.md authors
    return name.strip(" -—–")


def read_frontmatter_status(tasks_path: Path) -> str | None:
    """Return the value of 'status:' in YAML frontmatter, or None if absent."""
    lines = tasks_path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^status:\s*(.+)", line, re.IGNORECASE)
        if m:
            return m.group(1).strip().lower()
    return None


def parse_tasks(tasks_path: Path) -> dict[str, dict[str, int]]:
    phases: dict[str, dict[str, int]] = {}
    current_phase = None

    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        phase_match = re.match(r"^## (Phase \d+[^#]*)", line)
        if phase_match:
            current_phase = clean_phase_name(phase_match.group(1))
            phases[current_phase] = {"done": 0, "total": 0}
            continue

        if current_phase and re.match(r"^\s*- \[[ xX]\]", line):
            phases[current_phase]["total"] += 1
            if re.match(r"^\s*- \[[xX]\]", line):
                phases[current_phase]["done"] += 1

    return phases


def artifact_presence(feature_dir: Path) -> dict[str, bool]:
    return {name: (feature_dir / path).exists() for name, path in WORKFLOW_STEPS}


def task_progress(feature_dir: Path) -> tuple[int, int]:
    """Return (done, total) task counts. Returns (0, 0) if no tasks.md."""
    tasks_path = feature_dir / "tasks.md"
    if not tasks_path.exists():
        return 0, 0
    phases = parse_tasks(tasks_path)
    done = sum(p["done"] for p in phases.values())
    total = sum(p["total"] for p in phases.values())
    return done, total


def is_manually_done(feature_dir: Path) -> bool:
    """Return True if tasks.md frontmatter has 'status: done'."""
    tasks_path = feature_dir / "tasks.md"
    return tasks_path.exists() and read_frontmatter_status(tasks_path) == "done"


def overall_status(artifacts: dict[str, bool], done: int, total: int, manually_done: bool = False) -> str:
    if manually_done:
        return "✅ Done"
    if not artifacts.get("Spec"):
        return "💡 Planned"
    if not artifacts.get("Tasks"):
        return "📋 Speccing"
    if total == 0:
        return "⏳ Not started"
    if done == total:
        return "✅ Done"
    return "🔄 In progress"


# ---------------------------------------------------------------------------
# Job summary format (used in feature-dashboard.yml)
# ---------------------------------------------------------------------------

def phase_summary_table(feature_dir: Path) -> str:
    tasks_path = feature_dir / "tasks.md"
    if not tasks_path.exists():
        return f"_No tasks.md found for `{feature_dir.name}`_\n"

    manually_done = read_frontmatter_status(tasks_path) == "done"
    phases = parse_tasks(tasks_path)
    if not phases:
        return f"_No tasks found in `{feature_dir.name}/tasks.md`_\n"

    total_done = sum(p["done"] for p in phases.values())
    total_tasks = sum(p["total"] for p in phases.values())
    pct = int(total_done / total_tasks * 100) if total_tasks else 0

    overall = "✅ Done (shipped)" if manually_done else f"{total_done}/{total_tasks} tasks ({pct}%)"
    lines = [
        f"## `{feature_dir.name}`",
        "",
        f"**Overall: {overall}**",
        "",
        "| Phase | Done | Total | Status |",
        "|-------|:----:|:-----:|--------|",
    ]

    for phase, counts in phases.items():
        done = counts["done"]
        total = counts["total"]
        if manually_done:
            status = "✅ Done"
        elif total == 0:
            status = "—"
        elif done == total:
            status = "✅ Done"
        elif done == 0:
            status = "⏳ Not started"
        else:
            status = "🔄 In progress"
        lines.append(f"| {phase} | {done} | {total} | {status} |")

    lines.append("")
    return "\n".join(lines)


def print_job_summary(specs_dir: Path, feature_arg: str) -> None:
    dirs = resolve_dirs(specs_dir, feature_arg)
    print("# Feature Task Status\n")
    for d in dirs:
        print(phase_summary_table(d))


# ---------------------------------------------------------------------------
# Wiki page format
# ---------------------------------------------------------------------------

def wiki_step_cell(present: bool) -> str:
    return "✅" if present else "—"


def wiki_overview_table(dirs: list[Path]) -> str:
    step_names = [name for name, _ in WORKFLOW_STEPS]

    header = "| # | Feature | " + " | ".join(step_names) + " | Progress | Status |"
    sep    = "|---|---------|" + "|".join([":---:"] * len(step_names)) + "|:--------:|--------|"

    rows = [header, sep]
    for d in dirs:
        num = d.name.split("-")[0]
        name = "-".join(d.name.split("-")[1:]).replace("-", " ").title()
        artifacts = artifact_presence(d)
        done, total = task_progress(d)
        manually_done = is_manually_done(d)
        status = overall_status(artifacts, done, total, manually_done)

        cells = " | ".join(wiki_step_cell(artifacts.get(s, False)) for s in step_names)
        progress = f"{done}/{total}" if total else "—"
        rows.append(f"| {num} | [{name}](#{d.name}) | {cells} | {progress} | {status} |")

    return "\n".join(rows)


def wiki_feature_detail(feature_dir: Path) -> str:
    tasks_path = feature_dir / "tasks.md"
    if not tasks_path.exists():
        return ""

    manually_done = read_frontmatter_status(tasks_path) == "done"
    phases = parse_tasks(tasks_path)
    if not phases:
        return ""

    total_done = sum(p["done"] for p in phases.values())
    total_tasks = sum(p["total"] for p in phases.values())

    name = "-".join(feature_dir.name.split("-")[1:]).replace("-", " ").title()
    summary = "✅ Shipped" if manually_done else f"{total_done}/{total_tasks} tasks ({int(total_done/total_tasks*100) if total_tasks else 0}%)"
    lines = [
        f"### {feature_dir.name}",
        f"**{name}** — {summary}",
        "",
        "| Phase | Done | Total | Status |",
        "|-------|:----:|:-----:|--------|",
    ]

    for phase, counts in phases.items():
        done = counts["done"]
        total = counts["total"]
        if manually_done:
            status = "✅ Done"
        elif total == 0:
            status = "—"
        elif done == total:
            status = "✅ Done"
        elif done == 0:
            status = "⏳ Not started"
        else:
            status = "🔄 In progress"
        lines.append(f"| {phase} | {done} | {total} | {status} |")

    lines.append("")
    return "\n".join(lines)


def print_wiki_page(specs_dir: Path, feature_arg: str) -> None:
    all_dirs = sorted(d for d in specs_dir.iterdir() if d.is_dir())
    detail_dirs = resolve_dirs(specs_dir, feature_arg)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print(f"# Feature Status\n")
    print(f"_Last updated: {now}_\n")
    print("## Metaswarm Workflow Steps\n")
    print("Each column represents one metaswarm artifact. A ✅ means the artifact exists in `specs/`.\n")

    step_descriptions = {
        "Spec":       "Feature specification (`spec.md`)",
        "Research":   "Research & decision log (`research.md`)",
        "Data Model": "Data model (`data-model.md`)",
        "API":        "API contract (`contracts/api.md`)",
        "Plan":       "Implementation plan (`plan.md`)",
        "Tasks":      "Task list (`tasks.md`)",
        "Quickstart": "Quickstart guide (`quickstart.md`)",
        "Checklist":  "Requirements checklist (`checklists/requirements.md`)",
    }
    for name, desc in step_descriptions.items():
        print(f"- **{name}**: {desc}")
    print()

    print("## All Features\n")
    print(wiki_overview_table(all_dirs))
    print()

    print("## Implementation Progress\n")
    any_detail = False
    for d in detail_dirs:
        section = wiki_feature_detail(d)
        if section:
            print(section)
            any_detail = True

    if not any_detail:
        print("_No features with task breakdowns found._\n")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_dirs(specs_dir: Path, feature_arg: str) -> list[Path]:
    if feature_arg == "all":
        return sorted(
            d for d in specs_dir.iterdir()
            if d.is_dir() and (d / "tasks.md").exists()
        )
    dirs = sorted(
        d for d in specs_dir.iterdir()
        if d.is_dir() and d.name.startswith(feature_arg)
    )
    if not dirs:
        print(f"Error: no feature found matching '{feature_arg}'", file=sys.stderr)
        sys.exit(1)
    return dirs


def main() -> None:
    args = sys.argv[1:]

    wiki_mode = "--wiki" in args
    remaining = [a for a in args if a != "--wiki"]
    feature_arg = remaining[0] if remaining else "all"

    specs_dir = Path("specs")
    if not specs_dir.exists():
        print("Error: specs/ directory not found", file=sys.stderr)
        sys.exit(1)

    if wiki_mode:
        print_wiki_page(specs_dir, feature_arg)
    else:
        print_job_summary(specs_dir, feature_arg)


if __name__ == "__main__":
    main()
