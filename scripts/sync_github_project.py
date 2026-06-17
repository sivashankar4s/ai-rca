#!/usr/bin/env python3
"""
Sync specs/*/tasks.md → GitHub Milestones, Issues, and Project v2.

Usage:
  python3 scripts/sync_github_project.py [--dry-run] [--feature 004]

Requires: gh CLI authenticated  (gh auth login  or  GH_TOKEN env var)

Project v2 creation needs a PAT with 'project' scope stored as
PROJECT_TOKEN secret. Milestones and issues work with GITHUB_TOKEN alone.
"""
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_TITLE = "AI RCA Roadmap"
SYNC_LABEL    = "project-sync"
DRY_RUN       = "--dry-run" in sys.argv
FILTER_FEAT   = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--feature"), None)
_REPO: str | None = None


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class Task:
    feat_num:  str
    task_id:   str
    phase:     str
    title:     str   # ≤78 chars for issue title
    body:      str   # full description
    done:      bool
    prefix:    str   # "[001][T001]"


@dataclass
class Feature:
    num:       str
    name:      str
    directory: str
    ms_title:  str
    done:      bool
    tasks:     list[Task] = field(default_factory=list)


# ── Parsing ──────────────────────────────────────────────────────────────────

def _fix(text: str) -> str:
    """Fix UTF-8 bytes saved as cp1252 (â€" → —)."""
    try:
        return text.encode("cp1252").decode("utf-8")
    except Exception:
        return text


_PHASE = re.compile(r"^## (Phase \d+[^#]*)")
_TASK  = re.compile(r"^\s*- \[([xX ])\]\s+(T\d+)(.*)")
_CONT  = re.compile(r"^\s{4,}")
_TAGS  = re.compile(r"\[P\d*\]|\[P\]|\[US\d+\]")
_STAT  = re.compile(r"^status:\s*(.+)", re.IGNORECASE)


def _frontmatter_status(path: Path) -> str | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = _STAT.match(line)
        if m:
            return m.group(1).strip().lower()
    return None


def parse_features(specs_dir: Path) -> list[Feature]:
    features = []
    for d in sorted(specs_dir.iterdir()):
        tasks_md = d / "tasks.md"
        if not d.is_dir() or not tasks_md.exists():
            continue
        num = d.name.split("-")[0]
        if FILTER_FEAT and num != FILTER_FEAT:
            continue

        name = " ".join(p.title() for p in d.name.split("-")[1:])
        done = _frontmatter_status(tasks_md) == "done"
        feat = Feature(num=num, name=name, directory=d.name,
                       ms_title=f"{num} — {name}", done=done)

        phase = "General"
        buf: tuple | None = None   # (is_done, task_id, [lines])

        def flush(b: tuple | None) -> None:
            if b is None:
                return
            is_done, tid, desc_lines = b
            full  = _fix(_TAGS.sub("", " ".join(l.strip() for l in desc_lines)).strip())
            title = (full[:78] + "…") if len(full) > 78 else full
            feat.tasks.append(Task(
                feat_num=num, task_id=tid, phase=_fix(phase),
                title=title, body=full, done=is_done or done,
                prefix=f"[{num}][{tid}]",
            ))

        for line in tasks_md.read_text(encoding="utf-8").splitlines():
            pm = _PHASE.match(line)
            if pm:
                flush(buf); buf = None
                phase = pm.group(1).strip()
                continue
            tm = _TASK.match(line)
            if tm:
                flush(buf)
                buf = (tm.group(1).lower() == "x", tm.group(2), [tm.group(3).strip()])
                continue
            if buf and _CONT.match(line):
                buf[2].append(line)

        flush(buf)
        features.append(feat)
    return features


# ── gh CLI helpers ───────────────────────────────────────────────────────────

def _repo() -> str:
    global _REPO
    if not _REPO:
        r = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner"],
                           capture_output=True, text=True, encoding="utf-8")
        _REPO = json.loads(r.stdout)["nameWithOwner"]
    return _REPO


def _gh(method: str, path: str, payload: dict | None = None, fail_ok: bool = False) -> dict | list | None:
    cmd = ["gh", "api", "--method", method, path]
    inp = None
    if payload is not None:
        inp = json.dumps(payload)
        cmd += ["--input", "-"]
    r = subprocess.run(cmd, input=inp, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        if not fail_ok:
            try:
                msg = json.loads(r.stdout or "{}").get("message", r.stderr.strip())
            except Exception:
                msg = r.stderr.strip()
            print(f"  ⚠  {method} {path}: {msg}", file=sys.stderr)
        return None
    return json.loads(r.stdout) if r.stdout.strip() else {}


def _gql(query: str, **kw) -> dict:
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in kw.items():
        cmd += ["-f", f"{k}={v}"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(f"  ⚠  GraphQL: {r.stderr.strip()}", file=sys.stderr)
        return {}
    return json.loads(r.stdout).get("data", {})


# ── Labels ───────────────────────────────────────────────────────────────────

_FEAT_COLORS = ["e4e669", "f9c8b8", "c2e0c6", "bfd4f2", "d4c5f9",
                "fef2c0", "b4d8a7", "f4e4c1", "dce8f7", "f0d9eb"]


def ensure_labels(features: list[Feature]) -> None:
    repo = _repo()
    labels = [(SYNC_LABEL, "0075ca", "Managed by sync_github_project.py")]
    for i, f in enumerate(features):
        labels.append((f"feature/{f.num}", _FEAT_COLORS[i % len(_FEAT_COLORS)], f.name))
    for name, color, desc in labels:
        _gh("POST", f"/repos/{repo}/labels",
            {"name": name, "color": color, "description": desc}, fail_ok=True)


# ── Milestones ───────────────────────────────────────────────────────────────

def get_or_create_milestone(feat: Feature) -> int:
    repo    = _repo()
    ms_list = _gh("GET", f"/repos/{repo}/milestones?state=all&per_page=100") or []
    for m in ms_list:
        if m["title"] == feat.ms_title:
            target = "closed" if feat.done else "open"
            if m["state"] != target and not DRY_RUN:
                _gh("PATCH", f"/repos/{repo}/milestones/{m['number']}", {"state": target})
            return m["number"]
    if DRY_RUN:
        print(f"  [dry-run] would create milestone: {feat.ms_title}")
        return -1
    result = _gh("POST", f"/repos/{repo}/milestones", {
        "title":       feat.ms_title,
        "description": f"Feature {feat.num}: {feat.name} — specs/{feat.directory}/",
        "state":       "closed" if feat.done else "open",
    })
    return result["number"] if result else -1


# ── Issues ───────────────────────────────────────────────────────────────────

def load_existing_issues() -> dict[str, dict]:
    """One bulk fetch of all managed issues — avoids N per-task lookups."""
    repo, result, page = _repo(), {}, 1
    while True:
        batch = _gh("GET",
            f"/repos/{repo}/issues?labels={SYNC_LABEL}&state=all&per_page=100&page={page}"
        ) or []
        if not batch:
            break
        for i in batch:
            m = re.match(r"^(\[\d+\]\[T\d+\])", i["title"])
            if m:
                result[m.group(1)] = {
                    "number":  i["number"],
                    "node_id": i["node_id"],
                    "state":   i["state"],
                }
        if len(batch) < 100:
            break
        page += 1
    return result


def create_issue(task: Task, ms_num: int) -> tuple[int, str]:
    if DRY_RUN:
        print(f"    [dry-run] would create {task.prefix}")
        return -1, ""
    repo   = _repo()
    result = _gh("POST", f"/repos/{repo}/issues", {
        "title":     f"{task.prefix} {task.title}",
        "body":      (
            f"> **Feature:** `{task.feat_num}` &nbsp;|&nbsp; "
            f"**Phase:** {task.phase} &nbsp;|&nbsp; **Task:** `{task.task_id}`\n\n"
            f"{task.body}\n\n---\n"
            f"_Auto-synced from `specs/{task.feat_num}-*/tasks.md`_"
        ),
        "milestone": ms_num,
        "labels":    [SYNC_LABEL, f"feature/{task.feat_num}"],
    })
    return (result["number"], result["node_id"]) if result else (-1, "")


def sync_state(number: int, should_close: bool, current: str) -> None:
    if should_close and current == "open":
        if not DRY_RUN:
            _gh("PATCH", f"/repos/{_repo()}/issues/{number}", {"state": "closed"})
        print(f"    ✓ closed  #{number}")
    elif not should_close and current == "closed":
        if not DRY_RUN:
            _gh("PATCH", f"/repos/{_repo()}/issues/{number}", {"state": "open"})
        print(f"    ↑ reopened #{number}")


# ── Project v2 ───────────────────────────────────────────────────────────────

def get_or_create_project() -> str:
    data = _gql("query { viewer { id projectsV2(first:50) { nodes { id title } } } }")
    if not data:
        return ""
    for p in data.get("viewer", {}).get("projectsV2", {}).get("nodes", []):
        if p["title"] == PROJECT_TITLE:
            print(f"  Found existing project: {PROJECT_TITLE}")
            return p["id"]
    owner_id = data.get("viewer", {}).get("id", "")
    if not owner_id:
        return ""
    if DRY_RUN:
        print(f"  [dry-run] would create project: {PROJECT_TITLE}")
        return ""
    result = _gql(
        "mutation($o:ID!,$t:String!){createProjectV2(input:{ownerId:$o,title:$t}){projectV2{id url}}}",
        o=owner_id, t=PROJECT_TITLE,
    )
    proj = result.get("createProjectV2", {}).get("projectV2", {})
    if proj:
        print(f"  Created project: {proj.get('url', PROJECT_TITLE)}")
        return proj["id"]
    return ""


def add_to_project(project_id: str, node_id: str) -> None:
    if not project_id or not node_id or DRY_RUN:
        return
    _gql(
        "mutation($p:ID!,$c:ID!){addProjectV2ItemById(input:{projectId:$p,contentId:$c}){item{id}}}",
        p=project_id, c=node_id,
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    specs_dir = Path("specs")
    if not specs_dir.exists():
        print("Error: specs/ not found", file=sys.stderr); sys.exit(1)

    if DRY_RUN:
        print("=== DRY RUN — no GitHub changes will be made ===\n")

    print("Parsing features…")
    features = parse_features(specs_dir)
    print(f"  {len(features)} features · {sum(len(f.tasks) for f in features)} tasks\n")

    if not features:
        print("Nothing to sync."); return

    print("Ensuring labels…")
    if not DRY_RUN:
        ensure_labels(features)
    print("  done\n")

    print("Loading existing managed issues…")
    existing = load_existing_issues()
    print(f"  {len(existing)} found\n")

    print("Setting up GitHub Project v2…")
    project_id = get_or_create_project()
    if not project_id:
        print("  ⚠  Project skipped — set PROJECT_TOKEN secret for project write access")
    print()

    for feat in features:
        flag = "✅ done" if feat.done else "🔄 active"
        print(f"[{feat.num}] {feat.name}  ({flag})")

        ms_num = get_or_create_milestone(feat)

        for task in feat.tasks:
            info    = existing.get(task.prefix)
            node_id = ""

            if info:
                node_id = info["node_id"]
                sync_state(info["number"], task.done, info["state"])
            else:
                num, node_id = create_issue(task, ms_num)
                if num > 0:
                    print(f"    + created {task.prefix} → #{num}")
                    if task.done and not DRY_RUN:
                        _gh("PATCH", f"/repos/{_repo()}/issues/{num}", {"state": "closed"})
                    existing[task.prefix] = {
                        "number": num, "node_id": node_id,
                        "state": "closed" if task.done else "open",
                    }

            add_to_project(project_id, node_id)

        print()

    print("✅ Sync complete.")


if __name__ == "__main__":
    main()
