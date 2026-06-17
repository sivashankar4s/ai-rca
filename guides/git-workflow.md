# Git Workflow

## Branch Naming

```
feature/<issue-id>-<short-description>    # new features
fix/<issue-id>-<short-description>        # bug fixes
chore/<short-description>                 # maintenance, no code change
```

Examples: `feature/019-config-page-enhancements`, `fix/021-auth-token-expiry`

## Base Branch

All feature branches are cut from **`develop`**, not `main`. PRs target `develop`.

## Commit Messages

Format: `<type>(<scope>): <description>`

Types: `feat`, `fix`, `chore`, `test`, `docs`, `refactor`

Example: `feat(019-config-page-enhancements): add AWS credential config endpoint`

## Before Creating a PR

Mandatory sequence:
1. All tests pass: `pytest`
2. Coverage ≥ 90%: `pytest --cov --cov-fail-under=90`
3. Lint clean: `ruff check .`
4. Run `/self-reflect` and commit knowledge base updates to `.beads/`
5. Create PR targeting `develop`

## PR Body Template

```
## Summary
- <bullet>

## Test plan
- [ ] Unit tests pass
- [ ] Coverage ≥ 90%
- [ ] Lint clean

🤖 Generated with Claude Code
```

## Never

- Force-push to `main` or `develop`
- Skip pre-commit hooks (`--no-verify`)
- Merge without passing CI
