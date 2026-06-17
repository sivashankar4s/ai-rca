# Build Validation

## Commands

```bash
# Run tests with coverage
pytest

# Run tests with explicit fail-under threshold
pytest --cov --cov-fail-under=90

# Lint
ruff check .

# Format check (no auto-fix)
ruff format --check .

# Fix lint issues
ruff check . --fix

# Apply formatting
ruff format .
```

## Validation Sequence

Orchestrator agents MUST run this sequence before marking a task complete or creating a PR:

1. `ruff check .` — zero lint errors required
2. `ruff format --check .` — zero formatting issues required
3. `pytest` — all tests pass, coverage ≥ 90% on lines, branches, functions, statements

If any step fails, the task is NOT complete. Fix the issue and re-run.

## Coverage Source of Truth

`.coverage-thresholds.json` is the single source of truth. The `pyproject.toml` `--cov-fail-under` value must match. If you update the threshold, update both files.

Current thresholds: **90%** across lines, branches, functions, statements.

## Pre-commit Hooks

`.pre-commit-config.yaml` runs ruff on every commit. Do NOT bypass with `--no-verify`.

## CI Pipeline

GitHub Actions runs the full validation sequence on every push and PR. Failing CI blocks merge.
