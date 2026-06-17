# Quickstart Validation Guide: Config Page Enhancements

Use this guide to validate that the feature works end-to-end after implementation.

## Prerequisites

- PostgreSQL running and `DATABASE_URL` set in `.env`
- Alembic migration `003_add_app_config` applied: `alembic upgrade head`
- Backend running: `uvicorn backend.main:app --reload`
- Frontend accessible at `http://localhost:8000`

---

## Scenario 1: No credentials configured (fresh state)

**Setup**: Start with an empty `app_config` table (just-migrated DB).

**Steps**:
1. Open `http://localhost:8000` in a browser
2. Click the "Config" tab

**Expected**:
- Both "AWS Credentials" and "GitHub MCP Settings" cards display a "Not Configured" badge
- All input fields are empty

**API check** (optional):
```bash
curl http://localhost:8000/api/config
```
Expected response:
```json
{"aws": {"configured": false, ...}, "github_mcp": {"configured": false, ...}}
```

---

## Scenario 2: Save AWS credentials

**Steps**:
1. On the Config page, fill in the AWS card:
   - Access Key ID: `AKIATESTKEY123456789`
   - Secret Access Key: `testSecretKey/EXAMPLE+notreal`
   - Region: `us-east-1`
2. Click "Save AWS Config"

**Expected**:
- Success message appears in the AWS card feedback area
- AWS card badge changes to "Configured"
- Refreshing the page: Access Key ID shows `AKIATESTKEY123456789`, Secret field shows `••••••••`

**API check**:
```bash
curl http://localhost:8000/api/config
```
Expected: `"aws": {"configured": true, "access_key_id": "AKIATESTKEY123456789", "secret_access_key": "••••••••", ...}`

---

## Scenario 3: Save GitHub MCP settings

**Steps**:
1. Fill in the GitHub MCP card:
   - Repo: `acme-corp/my-service`
   - Token: `ghp_testtoken123456`
   - Default Branch: `main`
2. Click "Save GitHub MCP Config"

**Expected**:
- Success message in GitHub MCP card feedback area
- GitHub MCP badge changes to "Configured"
- Page refresh: Repo shows `acme-corp/my-service`, Token shows `••••••••`

---

## Scenario 4: Update secret without changing access key ID

**Steps**:
1. Config page loads — AWS card shows `AKIATESTKEY123456789` and `••••••••`
2. Leave Access Key ID unchanged
3. Change Secret Access Key to a new value: `newSecret/EXAMPLE+updated`
4. Click "Save AWS Config"

**Expected**:
- Success message appears
- `GET /api/config` still returns `access_key_id: "AKIATESTKEY123456789"` with `secret_access_key: "••••••••"` (new value stored but masked)

---

## Scenario 5: Required field validation

**Steps**:
1. Clear the Access Key ID field on the AWS card (leave Secret filled)
2. Click "Save AWS Config"

**Expected**:
- No PATCH request is sent (check browser Network tab)
- Inline error shown under the Access Key ID field
- The page does not navigate away

---

## Scenario 6: Masked secret is not overwritten when unchanged

**Steps**:
1. Config page loads — GitHub MCP card shows repo and `••••••••`
2. Change only the repo field (leave token field as `••••••••`)
3. Click "Save GitHub MCP Config"

**Expected**:
- Success message appears
- `GET /api/config` returns the same token as before (not cleared)

---

## Scenario 7: Clear a credential

**Steps**:
1. Load Config page with AWS credentials already set
2. Clear the Secret Access Key field (leave it empty)
3. Click "Save AWS Config"

**Expected**:
- A confirmation dialog appears: "This will remove the stored Secret Access Key. Are you sure?"
- On confirmation: PATCH is sent; success message shown; AWS badge changes to "Not Configured" after status refresh

---

## Running the Test Suite

```bash
# All backend tests with coverage
pytest --cov=backend --cov-fail-under=80 -v

# Config-specific tests only
pytest backend/tests/repositories/test_config_repo.py backend/tests/routers/test_config.py -v
```

All tests must pass and overall coverage must remain ≥80%.

---

## References

- API contract: [contracts/api.md](contracts/api.md)
- UI contract: [contracts/ui-contract.md](contracts/ui-contract.md)
- Data model: [data-model.md](data-model.md)
