# API Contract: Config Page Enhancements

**Router prefix**: `/api/config`  
**Tags**: `["config"]`  
**Router file**: `backend/routers/config.py`

---

## GET /api/config

**Purpose**: Return the current configuration status for all integration groups.

**Response model**: `AppConfigRead`

### Response (200 OK)
```json
{
  "aws": {
    "configured": true,
    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "secret_access_key": "••••••••",
    "region": "us-east-1"
  },
  "github_mcp": {
    "configured": false,
    "repo": null,
    "token": null,
    "default_branch": null
  }
}
```

**Rules**:
- `configured: true` when both required fields for the group are non-empty (DB or env-var fallback)
- `secret_access_key` and `token` MUST be `"••••••••"` when a value exists, or `null` when absent
- `access_key_id` and `repo` are returned as-is (they are identifiers, not secrets)
- Reads from DB row first; falls back to `settings.*` values as defaults

---

## PATCH /api/config/aws

**Purpose**: Save or update AWS credential configuration.

**Request body**: `AwsConfigUpdate`
```json
{
  "access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  "region": "us-east-1"
}
```

**Secret no-change sentinel**: If `secret_access_key` equals `"••••••••"`, the existing stored value is preserved (not overwritten).

**Response model**: `ConfigSaveResult`

### Response (200 OK — success)
```json
{
  "success": true,
  "message": "AWS configuration saved.",
  "updated_at": "2026-06-16T10:30:00Z"
}
```

### Response (422 Unprocessable Entity — validation failure)
```json
{
  "detail": [
    {
      "loc": ["body", "access_key_id"],
      "msg": "access_key_id must not be empty",
      "type": "value_error"
    }
  ]
}
```

**Validation rules**:
- `access_key_id`: required, non-empty after stripping whitespace
- `secret_access_key`: required unless equal to mask sentinel; non-empty after stripping whitespace
- `region`: optional; if provided, non-empty after stripping whitespace

---

## PATCH /api/config/github-mcp

**Purpose**: Save or update GitHub MCP repository and token configuration.

**Request body**: `GithubMcpConfigUpdate`
```json
{
  "repo": "acme-corp/my-service",
  "token": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "default_branch": "main"
}
```

**Secret no-change sentinel**: If `token` equals `"••••••••"`, the existing stored value is preserved.

**Response model**: `ConfigSaveResult`

### Response (200 OK — success)
```json
{
  "success": true,
  "message": "GitHub MCP configuration saved.",
  "updated_at": "2026-06-16T10:31:00Z"
}
```

### Response (422 Unprocessable Entity — validation failure)
```json
{
  "detail": [
    {
      "loc": ["body", "repo"],
      "msg": "repo must be in owner/repo format",
      "type": "value_error"
    }
  ]
}
```

**Validation rules**:
- `repo`: required, must match `owner/repo` pattern (at least one `/`, non-empty on both sides)
- `token`: required unless equal to mask sentinel; non-empty after stripping whitespace
- `default_branch`: optional

---

## Error Handling

All endpoints follow the project's FastAPI exception handler convention:
- Validation errors → 422 with Pydantic detail array (FastAPI default)
- DB errors → 500 with a structured error response via the global exception handler (not an ad-hoc dict)
- No 404s: GET always returns a response (even if nothing is configured yet — `configured: false`)
