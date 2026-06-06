# Exploration Captcha Auth State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exploration-environment captcha strategy and auth-state reuse configuration, with backend validation and frontend form rules matching the approved design.

**Architecture:** Environment configuration remains the source of truth. Backend normalizes and validates login/captcha fields, exposes auth-state status as a derived field, and keeps secrets out of responses. Frontend shows login-related controls only for account-password environments and hides manual captcha when auth-state reuse is disabled.

**Tech Stack:** FastAPI/Pydantic backend, SQLite schema bootstrap in `init_db.py`, React/Next frontend, existing animated select component, pytest backend tests, Biome frontend lint.

---

### Task 1: Backend Environment Contract

**Files:**
- Modify: `apps/backend/app/schemas/environment.py`
- Modify: `apps/backend/app/seed/init_db.py`
- Modify: `apps/backend/app/repositories/environment_repo.py`
- Modify: `apps/backend/app/presentation/serializers.py`
- Modify: `apps/backend/app/services/environment_service.py`
- Test: `apps/backend/tests/test_environment_service.py`

- [x] **Step 1: Write failing backend tests**

Create `apps/backend/tests/test_environment_service.py` with tests for:

```python
def test_create_skip_login_normalizes_captcha_and_auth_state(...)
def test_create_account_password_defaults_reuse_auth_state(...)
def test_manual_captcha_requires_reuse_auth_state(...)
def test_legacy_manual_login_strategy_maps_to_account_password_manual(...)
```

- [x] **Step 2: Run backend tests and verify red**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests\test_environment_service.py -q
```

Expected: fail because `captcha_strategy` and `reuse_auth_state` fields are missing.

- [x] **Step 3: Add schema fields and DB columns**

Add `captcha_strategy` and `reuse_auth_state` to Pydantic schemas, `project_environments`, migration guards, repository create/update fields, and serializer output.

- [x] **Step 4: Add normalization and validation**

Implement:

```text
skip_login -> captcha_strategy=none, reuse_auth_state=false, username/password cleared
account_password -> username required, password required on create
manual + reuse_auth_state=false -> 400
legacy reuse_state -> account_password + reuse_auth_state=true + captcha_strategy=none
legacy manual -> account_password + reuse_auth_state=true + captcha_strategy=manual
```

- [x] **Step 5: Run backend tests and verify green**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests\test_environment_service.py -q
```

Expected: all tests pass.

### Task 2: Frontend Environment Form Rules

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/exploration-workspace.tsx`

- [x] **Step 1: Update environment types and defaults**

Add `captcha_strategy` and `reuse_auth_state` to environment DTO/form state. Defaults:

```text
loginStrategy=skip_login
captchaStrategy=none
reuseAuthState=true
```

- [x] **Step 2: Update UI visibility**

Implement:

```text
skip_login -> hide username/password/reuse-auth-state/captcha-strategy
account_password -> show username/password/reuse-auth-state/captcha-strategy
reuseAuthState=false -> hide manual captcha option and reset manual to none
```

- [x] **Step 3: Update create/update payloads**

Submit `captcha_strategy` and `reuse_auth_state`; for skip login submit normalized empty username/password, `captcha_strategy=none`, `reuse_auth_state=false`.

- [x] **Step 4: Run frontend lint**

Run:

```powershell
cd apps/frontend
pnpm biome check src/components/ai-testing/exploration-workspace.tsx
```

Expected: no lint errors.

### Task 3: Regression Verification

**Files:**
- Verify backend and frontend touched files.

- [x] **Step 1: Run related backend regression**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests\test_environment_service.py tests\test_site_exploration_agent_integration.py tests\test_exploration_artifact_v2.py tests\test_exploration_service_artifact_v2.py -q
```

Expected: all tests pass.

- [x] **Step 2: Confirm runner boundary remains unchanged**

Search:

```powershell
rg -n "AI_TESTING_LOGIN_PASSWORD|AI_TESTING_LOGIN_USERNAME|password_secret|cookie|storageState|storage_state" apps/backend/app/agents apps/backend/runners/playwright
```

Expected: no sensitive login execution inputs are introduced in model-facing agent code or the Playwright runner. Non-sensitive `login_strategy` / `captcha_strategy` / `reuse_auth_state` summaries may appear in the planning prompt.

- [x] **Step 3: Report remaining phases**

Manual login browser session, encrypted password storage, and AI letter captcha solving remain as planned follow-up implementation phases.
