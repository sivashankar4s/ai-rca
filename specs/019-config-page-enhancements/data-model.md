# Data Model: Config Page Enhancements

## Entity: AppConfig

**Table**: `app_config`
**Purpose**: Single-row global configuration store for integration credentials. Acts as a runtime overlay on top of `.env` defaults.

### ORM Model (`backend/db/models.py`)

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | `Integer` | NO | `1` (fixed) | Single-row enforced via `CHECK (id = 1)` |
| `aws_config` | `JSONB` | YES | `NULL` | AWS credential group (see sub-schema) |
| `github_mcp_config` | `JSONB` | YES | `NULL` | GitHub MCP credential group (see sub-schema) |
| `updated_at` | `DateTime(timezone=True)` | NO | `func.now()` | Updated on every upsert |

**Constraint**: `CHECK (id = 1)` — enforces single-row semantics.
**Upsert pattern**: `INSERT … ON CONFLICT (id) DO UPDATE SET …` in the repository.

### JSONB Sub-schemas

#### `aws_config`
```json
{
  "access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "secret_access_key": "<stored value — NEVER returned to client>",
  "region": "us-east-1"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `access_key_id` | YES | AWS Access Key ID — returned as-is on GET (not a secret) |
| `secret_access_key` | YES | Masked as `"••••••••"` in all API responses |
| `region` | NO | Defaults to `settings.aws_region` when absent |

#### `github_mcp_config`
```json
{
  "repo": "owner/repo-name",
  "token": "<stored value — NEVER returned to client>",
  "default_branch": "main"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `repo` | YES | `owner/repo` slug — returned as-is on GET |
| `token` | YES | GitHub PAT — masked as `"••••••••"` in all API responses |
| `default_branch` | NO | Defaults to `"main"` when absent |

---

## Pydantic Schemas (`backend/models/schemas.py`)

### `AwsConfigUpdate` (request body for `PATCH /api/config/aws`)
```python
class AwsConfigUpdate(BaseModel):
    access_key_id: str
    secret_access_key: str   # "••••••••" means "keep existing"
    region: str | None = None
```

**Validation rules**:
- `access_key_id` must be non-empty (strip whitespace, then validate length > 0)
- `secret_access_key` must be non-empty unless it equals the mask sentinel `"••••••••"` (means no-change)

### `GithubMcpConfigUpdate` (request body for `PATCH /api/config/github-mcp`)
```python
class GithubMcpConfigUpdate(BaseModel):
    repo: str               # "owner/repo" format
    token: str              # "••••••••" means "keep existing"
    default_branch: str | None = None
```

**Validation rules**:
- `repo` must match pattern `[^/]+/[^/]+` (owner/repo slug)
- `token` must be non-empty unless it equals the mask sentinel

### `AwsConfigStatus` (part of GET response)
```python
class AwsConfigStatus(BaseModel):
    configured: bool
    access_key_id: str | None = None   # shown on GET; never the secret
    secret_access_key: str | None = None  # always "••••••••" or None
    region: str | None = None
```

### `GithubMcpConfigStatus` (part of GET response)
```python
class GithubMcpConfigStatus(BaseModel):
    configured: bool
    repo: str | None = None
    token: str | None = None        # always "••••••••" or None
    default_branch: str | None = None
```

### `AppConfigRead` (response body for `GET /api/config`)
```python
class AppConfigRead(BaseModel):
    aws: AwsConfigStatus
    github_mcp: GithubMcpConfigStatus
```

### `ConfigSaveResult` (response body for PATCH endpoints)
```python
class ConfigSaveResult(BaseModel):
    success: bool
    message: str
    updated_at: datetime | None = None
```

---

## Masking Sentinel

The string `"••••••••"` (8 bullet characters, U+2022) is the canonical mask sentinel used by the API for all secret fields. It is never stored; it is only emitted in GET responses and recognised on PATCH to mean "preserve existing value".

---

## Fallback / Priority Order

For any config field, the effective value is resolved in this priority order:

1. DB row (`app_config` table) — if non-null and non-empty
2. `backend/config.py` / environment variable — fallback default

The `config_repo.py` repository implements this merge when constructing the GET response.
