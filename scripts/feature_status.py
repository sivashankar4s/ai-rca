#!/usr/bin/env python3
"""Parse specs/*/tasks.md and output GitHub-flavored markdown status tables."""
import re
import sys
from pathlib import Path


def parse_tasks(tasks_path: Path) -> dict[str, dict[str, int]]:
    phases: dict[str, dict[str, int]] = {}
    current_phase = None

    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        phase_match = re.match(r"^## (Phase \d+[^#]*)", line)
        if phase_match:
            current_phase = phase_match.group(1).strip()
            phases[current_phase] = {"done": 0, "total": 0}
            continue

        if current_phase and re.match(r"^\s*- \[[ xX]\]", line):
            phases[current_phase]["total"] += 1
            if re.match(r"^\s*- \[[xX]\]", line):
                phases[current_phase]["done"] += 1

    return phases


def feature_summary(feature_dir: Path) -> str:
    tasks_path = feature_dir / "tasks.md"
    if not tasks_path.exists():
        return f"_No tasks.md found for `{feature_dir.name}`_\n"

    phases = parse_tasks(tasks_path)
    if not phases:
        return f"_No tasks found in `{feature_dir.name}/tasks.md`_\n"

    total_done = sum(p["done"] for p in phases.values())
    total_tasks = sum(p["total"] for p in phases.values())
    pct = int(total_done / total_tasks * 100) if total_tasks else 0

    lines = [
        f"## `{feature_dir.name}`",
        "",
        f"**Overall: {total_done}/{total_tasks} tasks ({pct}%)**",
        "",
        "| Phase | Done | Total | Status |",
        "|-------|:----:|:-----:|--------|",
    ]

    for phase, counts in phases.items():
        done = counts["done"]
        total = counts["total"]
        if total == 0:
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


def main() -> None:
    feature_arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    specs_dir = Path("specs")

    if not specs_dir.exists():
        print("Error: specs/ directory not found", file=sys.stderr)
        sys.exit(1)

    if feature_arg == "all":
        dirs = sorted(
            d for d in specs_dir.iterdir()
            if d.is_dir() and (d / "tasks.md").exists()
        )
    else:
        dirs = sorted(
            d for d in specs_dir.iterdir()
            if d.is_dir() and d.name.startswith(feature_arg)
        )
        if not dirs:
            print(f"Error: no feature found matching '{feature_arg}'", file=sys.stderr)
            sys.exit(1)

    print("# Feature Task Status\n")
    for d in dirs:
        print(feature_summary(d))


if __name__ == "__main__":
    main()
