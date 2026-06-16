# Phase 0 Research: Per-Run Provider Selection

All Technical Context items were resolvable from the existing codebase; there are no
open `NEEDS CLARIFICATION` markers. The decisions below record what already exists and
the small additions required.

## Decision 1 — Reuse the existing override parameters (do not rebuild selection)

**Decision**: Carry the operator's choice into the `override` parameters that
`plugin_registry.get_data_source(override=None)` and `get_log_backend(override=None)`
already accept; do not add a new selection layer.

**Rationale**: The registry already implements per-call override with a `match`/`case`
that falls back to `settings.*_provider`. Adding a parallel mechanism would violate
Constitution Principle II (YAGNI). The only gap on the data-source side is that the
request body has no field to carry the choice; the log-backend override field already
exists on `AnalyzeRequest`.

**Alternatives considered**:
- A new `ProviderSelector` service wrapping the registry — rejected: pure indirection
  over machinery that already does the job.

## Decision 2 — `PostgresDataSource` already exists; this feature only exposes it

**Decision**: Treat the stored-history source as already implemented. The
`PostgresDataSource` provider (`backend/providers/data_source/postgres.py`) already
implements `DataSourceStrategy` over `failure_records` and has a contract test. This
feature makes it *selectable per run*, not "new".

**Rationale**: Re-implementing it would duplicate working, tested code. The persistence
side (Step-1 fetch writes every record to `failure_records`) is already in place, so the
source has data to serve.

**Alternatives considered**:
- A bespoke "history reader" distinct from the provider — rejected: the existing
  provider already returns the correct `FailureRecord` shape filtered by window/component.

## Decision 3 — `data_source` request field shape

**Decision**: Add `data_source: Literal["athena", "postgres"] | None = None` to
`FailuresRequest`. `None` means "use the configured default" (FR-001/FR-010). The
`AnalyzeRequest.log_backend` override field already exists and is reused unchanged
(FR-002).

**Rationale**: A closed `Literal` documents the supported set, gives Pydantic-level
rejection of unsupported values, and keeps `None` semantically equal to today's
behavior. `local_data_file` mode still short-circuits in the registry regardless of the
field, preserving local-dev behavior.

**Alternatives considered**:
- A free `str` field — rejected: pushes validation into the service and weakens the
  contract.

## Decision 4 — `GET /api/providers` derives availability from the registry + config

**Decision**: Add a read-only `GET /api/providers` returning the available data sources
and log backends, each with `id`, `label`, and `is_default`. Availability is derived
from the registry's known keys (the `case` arms) intersected with what is actually
configured, and the default is read from `settings.*_provider` (or the
`local_data_file` short-circuit for the data source).

**Rationale**: Satisfies FR-005/FR-006 — the UI populates from real availability, so an
unconfigured provider never appears and a newly configured one appears on reload with no
code change. Keeping this a thin describe endpoint (no I/O, no probing of remote systems)
keeps it fast and side-effect-free.

**Alternatives considered**:
- Health-probing each provider before listing it — rejected for v1: slow, adds external
  calls to a screen-load path, and "configured" is a good enough availability signal;
  run-time failures are still surfaced clearly (Decision 5).
- A hardcoded list in the frontend — rejected: drifts from backend reality, violates
  FR-006.

## Decision 5 — Unknown / unavailable selection fails loudly, never substitutes

**Decision**: An unsupported selection is rejected before any run work: Pydantic
rejects values outside the `Literal`; a value the registry does not know raises
`ValueError` (already its behavior), translated by a FastAPI exception handler to a
clear HTTP 400. A selected-but-unreachable provider fails the run with a message naming
the provider, with no silent fallback to the default.

**Rationale**: Satisfies FR-007/FR-008 and Constitution Principle VI (explicit errors,
no silent swallowing). Silent fallback would make results misleading about their source.

**Alternatives considered**:
- Falling back to the default on a bad selection — rejected: violates FR-007 and hides
  configuration mistakes.

## Decision 6 — Per-run scope only; no write-back to settings

**Decision**: The override lives only for the duration of the request; it is never
written to `settings`. Concurrent users' runs are independent.

**Rationale**: Satisfies FR-003/SC-001 and Constitution Principle V — global defaults
stay in `config.py`; per-run choice is request-scoped state.

**Alternatives considered**:
- Persisting the last selection as the new default — rejected: turns a per-run choice
  into hidden global mutation affecting other users.

## Decision 7 — Neutral header copy

**Decision**: Replace the AWS/vendor-specific tagline in `frontend/index.html` with a
provider-neutral line (e.g. "Powered by pluggable data, log & AI providers").

**Rationale**: Satisfies FR-009/SC-005; matches the pluggable architecture the product
actually has. Pure copy/markup change, reusing existing styles.

**Alternatives considered**:
- Leaving branding as-is — rejected: contradicts the explicit ask and misrepresents the
  tool as AWS-only.
