# Pytest Requests Executable Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fake pytest Requests agent wrapper with a runtime-loaded executable Skill while preserving deterministic rendering, storage isolation, and existing generated script behavior.

**Architecture:** Introduce a shared Skill definition loader used by both prompt-based `SkillMiddleware` and deterministic executable skills. Register pytest Requests generation as an `ExecutableSkill` whose implementation remains the deterministic renderer; the business service invokes the Skill and includes its definition fingerprint in script source hashes so Skill changes trigger regeneration.

**Tech Stack:** Python 3.13, Pydantic 2, pytest 9, LangChain middleware, deterministic pytest + Requests renderer.

## Global Constraints

- Preserve all unrelated uncommitted changes in the current workspace.
- Do not migrate the default generator to DeepAgents.
- Do not allow an Agent or Skill to write project files directly.
- Keep physical paths, atomic writes, locks, rollback, and pytest collection in `services/api_automation`.
- Preserve the existing `PytestRequestsGenerationInput` and generated logical file contract.
- Do not create commits unless explicitly requested.

---

### Task 1: Add Shared Skill Runtime Contract

**Files:**
- Create: `apps/backend/app/agents/shared/skill_runtime.py`
- Modify: `apps/backend/app/agents/shared/skill_middleware.py`
- Modify: `apps/backend/app/agents/shared/__init__.py`
- Test: `apps/backend/tests/test_skill_middleware.py`
- Create: `apps/backend/tests/test_executable_skill.py`

**Interfaces:**
- Produces: `SkillDefinition.load(path: Path)`, `SkillDefinition.fingerprint`, and `ExecutableSkill.invoke(input_data)`.
- Consumes: a Skill directory containing `SKILL.md` and optional `references/*.md`.

- [ ] **Step 1: Write failing Skill definition tests**

Add tests proving frontmatter name/description parsing, deterministic reference ordering, fingerprint changes when Skill content changes, and clear errors for missing metadata.

- [ ] **Step 2: Run tests and verify RED**

Run: `rtk pytest tests/test_executable_skill.py tests/test_skill_middleware.py -q`

Expected: FAIL because `skill_runtime` and the shared definition loader do not exist.

- [ ] **Step 3: Implement the minimal shared runtime**

Implement immutable `SkillDefinition` and generic `ExecutableSkill`. Parse the simple YAML-style frontmatter without adding dependencies, load references in sorted order, and hash relative file names plus bytes with SHA-256.

- [ ] **Step 4: Reuse SkillDefinition in SkillMiddleware**

Keep the existing middleware output format, but delegate `SKILL.md` and reference loading to `SkillDefinition` so prompt Skills and executable Skills use one contract.

- [ ] **Step 5: Run tests and verify GREEN**

Run: `rtk pytest tests/test_executable_skill.py tests/test_skill_middleware.py -q`

Expected: PASS.

### Task 2: Replace Fake Agent With Executable Skill

**Files:**
- Create: `apps/backend/app/agents/api_automation/pytest_requests/skill.py`
- Create: `apps/backend/app/agents/api_automation/pytest_requests/generator.py`
- Delete: `apps/backend/app/agents/api_automation/pytest_requests/agent.py`
- Delete: `apps/backend/app/agents/api_automation/pytest_requests/service.py`
- Modify: `apps/backend/app/agents/api_automation/pytest_requests/__init__.py`
- Modify: `apps/backend/tests/test_api_automation_pytest_requests_agent.py`
- Modify: `apps/backend/tests/test_agent_architecture_boundaries.py`

**Interfaces:**
- Produces: `PYTEST_REQUESTS_CODE_GENERATION_SKILL`, `generate_pytest_requests_code(input_data)`, and `pytest_requests_skill_fingerprint()`.
- Consumes: `render_pytest_requests_files()` and existing generation schemas.

- [ ] **Step 1: Write failing executable Skill architecture tests**

Require `skill.py` and `generator.py`, forbid the fake `agent.py` and pass-through `service.py`, assert runtime metadata comes from `SKILL.md`, and preserve stable logical file output.

- [ ] **Step 2: Run tests and verify RED**

Run: `rtk pytest tests/test_api_automation_pytest_requests_agent.py tests/test_agent_architecture_boundaries.py -q`

Expected: FAIL because the old fake Agent structure still exists.

- [ ] **Step 3: Implement the executable Skill**

Register a deterministic runner that computes the endpoint key and returns `PytestRequestsGenerationResult`; expose the public generator function through the registered Skill.

- [ ] **Step 4: Remove fake Agent files and update exports**

Delete the two pass-through modules and update imports without changing renderer behavior.

- [ ] **Step 5: Run tests and verify GREEN**

Run: `rtk pytest tests/test_api_automation_pytest_requests_agent.py tests/test_agent_architecture_boundaries.py -q`

Expected: PASS.

### Task 3: Make Skill Changes Invalidate Generated Scripts

**Files:**
- Modify: `apps/backend/app/services/api_automation/service.py`
- Modify: `apps/backend/tests/test_api_automation_script_generator.py`

**Interfaces:**
- Consumes: `pytest_requests_skill_fingerprint()`.
- Produces: source hashes that change whenever endpoint data, cases, or the executable Skill definition changes.

- [ ] **Step 1: Write failing source-hash test**

Patch the Skill fingerprint to two different values and assert `_script_source_hash()` returns different hashes for identical endpoint/case input.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `rtk pytest tests/test_api_automation_script_generator.py -q`

Expected: FAIL because source hashing currently ignores the Skill definition.

- [ ] **Step 3: Include the Skill fingerprint in source hashing**

Import the fingerprint accessor from the pytest Requests package and add it to the canonical hash payload.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `rtk pytest tests/test_api_automation_script_generator.py -q`

Expected: PASS.

### Task 4: Validate The Integrated Boundary

**Files:**
- Verify: `apps/backend/app/agents/shared/skill_runtime.py`
- Verify: `apps/backend/app/agents/api_automation/pytest_requests/skill.py`
- Verify: `apps/backend/app/agents/api_automation/pytest_requests/generator.py`
- Verify: `apps/backend/app/services/api_automation/artifact_storage.py`

**Interfaces:**
- Consumes: completed shared Skill runtime and executable pytest Requests Skill.
- Produces: a verified deterministic generation path with no Agent-owned file writes.

- [ ] **Step 1: Search for stale fake-Agent imports**

Run: `rtk proxy rg -n "pytest_requests_generation_agent|pytest_requests\.service|pytest_requests\.agent" apps/backend/app apps/backend/tests`

Expected: no matches.

- [ ] **Step 2: Run focused regression tests**

Run: `rtk pytest tests/test_executable_skill.py tests/test_skill_middleware.py tests/test_api_automation_pytest_requests_agent.py tests/test_agent_architecture_boundaries.py tests/test_api_automation_script_generator.py -q`

Expected: PASS.

- [ ] **Step 3: Run API automation runner regression**

Run: `rtk pytest tests/test_api_automation_runner.py tests/test_api_automation_schema_repo.py -q`

Expected: PASS.

- [ ] **Step 4: Inspect the final scoped diff**

Run: `rtk proxy git diff -- apps/backend/app/agents/shared apps/backend/app/agents/api_automation/pytest_requests apps/backend/app/services/api_automation/service.py apps/backend/tests/test_skill_middleware.py apps/backend/tests/test_executable_skill.py apps/backend/tests/test_api_automation_pytest_requests_agent.py apps/backend/tests/test_agent_architecture_boundaries.py apps/backend/tests/test_api_automation_script_generator.py`

Expected: only the executable Skill runtime, fake-Agent removal, hash invalidation, and tests described above.
