# Coding Standards

## Language & Runtime

- Python 3.13+
- FastAPI for HTTP API layer
- Pydantic v2 for data validation and schemas
- SQLAlchemy (async) for database access

## Style Rules

- Line length: **100 characters** (enforced by ruff)
- Target: `py313`
- Enabled ruff rules: `E` (pycodestyle), `F` (pyflakes), `I` (isort), `UP` (pyupgrade)
- No formatter configuration overrides — `ruff format` is the formatter

## File Organization

```
backend/
  routers/       # FastAPI route handlers — thin, delegate to services
  services/      # Business logic — no DB access, calls repositories
  repositories/  # DB queries — no business logic
  models/        # Pydantic schemas (request/response)
  db/            # SQLAlchemy models and session management
  providers/     # Pluggable implementations (LLM, data source)
  strategies/    # Strategy pattern implementations
```

## Comments

Default to writing **no comments**. Add a comment only when the WHY is non-obvious: a hidden constraint, a workaround, a subtle invariant. Never document WHAT the code does — well-named identifiers do that.

## Error Handling

- Validate only at system boundaries (user input, external APIs)
- Do not add fallbacks for scenarios that can't happen
- Trust FastAPI and SQLAlchemy framework guarantees internally

## Security

- Never log secrets, tokens, or credentials
- Validate all external inputs with Pydantic models at the router layer
- Use parameterized queries (SQLAlchemy ORM) — never string-format SQL
- No hardcoded secrets — use environment variables via `backend/config.py`
