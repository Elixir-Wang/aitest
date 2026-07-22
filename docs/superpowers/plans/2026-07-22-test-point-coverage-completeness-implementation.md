# 最终需求测试点完整覆盖 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将测试点生成改为“最终需求义务提取、完整生成、覆盖校验、缺口补齐”的闭环，确保最终需求中的所有明确可验证内容均有测试点覆盖，未完整覆盖时禁止任务完成。

**Architecture:** 在现有测试点生成能力前增加结构化需求义务提取，生成结果必须声明覆盖的义务 ID。后端使用确定性覆盖校验判断缺口，并最多执行 3 轮定向补齐；义务、测试点映射和覆盖状态持久化，Markdown 编辑与删除后重新计算覆盖，前端展示覆盖摘要和缺口。

**Tech Stack:** Python 3.12、FastAPI、Pydantic、LangChain structured output、SQLite、pytest、Next.js 16、React 19、TypeScript、Biome、Node contract tests。

## Global Constraints

- 测试点生成唯一事实源是当前最终需求版本，不读取初始需求、历史版本、原始上传文件或需求分析待澄清项。
- 只覆盖最终需求明确描述的内容和由明确阈值直接推导的边界，不添加 PRD 未提及的权限、异常、并发、安全、性能或日志场景。
- 最终需求未定义具体处理结果时，不生成猜测性预期。
- 每条 `test_required=true` 的需求义务至少关联一个测试点，否则生成任务不能进入 `completed`。
- 缺口补齐最多执行 3 轮，仍不完整时任务失败并返回具体义务 ID 和来源章节。
- 义务清单绑定 `requirement_version_id`，最终需求版本变化时重新提取。
- 保持现有测试点列表、详情、Markdown 编辑、删除和下游测试用例生成接口兼容。
- 工作区当前存在未提交修改，实施时不得覆盖或回退用户在 `test_point_service.py`、`test_point_repo.py`、`test-points-list.tsx` 等文件中的现有改动。

---

### Task 1: 持久化需求义务和覆盖状态

**Files:**
- Modify: `apps/backend/app/seed/schema.py:242`
- Modify: `apps/backend/app/seed/seeds.py`
- Modify: `apps/backend/app/repositories/test_point_repo.py`
- Test: `apps/backend/tests/test_test_point_coverage_repo.py`

**Interfaces:**
- Produces: `replace_obligations(db, *, project_id, document_id, version_id, obligations)`
- Produces: `list_obligations(db, document_id, version_id)`
- Produces: `replace_point_obligation_links(db, *, version_id, links)`
- Produces: `list_point_obligation_links(db, version_id)`
- Produces: extended `update_run()` support for coverage fields

- [ ] **Step 1: Write failing repository tests**

Create tests that seed one project/document/final version and assert:

```python
def test_replace_obligations_and_links_round_trip():
    obligations = [
        {
            "obligation_key": "REQ-001",
            "source_section": "改造方案一",
            "statement": "超过10000字符时完整文本存入数据库",
            "obligation_type": "business_rule",
            "modules": ["输出节点"],
            "thresholds": ["10000"],
            "explicit": True,
            "test_required": True,
        }
    ]
    test_point_repo.replace_obligations(
        db,
        project_id="project-1",
        document_id="doc-1",
        version_id="version-1",
        obligations=obligations,
    )
    assert test_point_repo.list_obligations(db, "doc-1", "version-1")[0]["obligation_key"] == "REQ-001"


def test_requeue_clears_coverage_artifacts_for_same_version():
    test_point_repo.requeue_run(db, "run-1")
    assert test_point_repo.list_obligations(db, "doc-1", "version-1") == []
    assert test_point_repo.list_point_obligation_links(db, "version-1") == []
```

- [ ] **Step 2: Run repository tests and verify failure**

Run: `cd apps/backend; uv run pytest tests/test_test_point_coverage_repo.py -q`

Expected: FAIL because obligation tables and repository functions do not exist.

- [ ] **Step 3: Add schema and forward-compatible migration**

Add run columns:

```sql
coverage_status TEXT NOT NULL DEFAULT 'pending',
obligation_count INTEGER NOT NULL DEFAULT 0,
covered_obligation_count INTEGER NOT NULL DEFAULT 0,
missing_obligations_json TEXT NOT NULL DEFAULT '[]',
unsupported_assumptions_json TEXT NOT NULL DEFAULT '[]',
supplement_round INTEGER NOT NULL DEFAULT 0
```

Add tables:

```sql
CREATE TABLE IF NOT EXISTS test_point_requirement_obligations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  requirement_version_id TEXT NOT NULL,
  obligation_key TEXT NOT NULL,
  source_section TEXT NOT NULL,
  statement TEXT NOT NULL,
  obligation_type TEXT NOT NULL,
  modules_json TEXT NOT NULL DEFAULT '[]',
  thresholds_json TEXT NOT NULL DEFAULT '[]',
  explicit INTEGER NOT NULL DEFAULT 1,
  test_required INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(requirement_version_id, obligation_key)
);

CREATE TABLE IF NOT EXISTS test_point_obligations (
  test_point_id TEXT NOT NULL,
  obligation_id TEXT NOT NULL,
  requirement_version_id TEXT NOT NULL,
  PRIMARY KEY(test_point_id, obligation_id)
);
```

Extend `seeds.py` with idempotent `ALTER TABLE` checks following the existing column-migration pattern.

- [ ] **Step 4: Implement repository functions**

Serialize `modules` and `thresholds` as JSON, resolve `obligation_key` to obligation row ID when replacing links, and delete old version-scoped artifacts inside the caller transaction before inserting replacements.

- [ ] **Step 5: Run repository tests**

Run: `cd apps/backend; uv run pytest tests/test_test_point_coverage_repo.py -q`

Expected: PASS.

---

### Task 2: 提取最终需求义务

**Files:**
- Modify: `apps/backend/app/agents/test_point_generation/schemas.py`
- Create: `apps/backend/app/agents/test_point_generation/obligation_agent.py`
- Create: `apps/backend/app/agents/test_point_generation/obligation_service.py`
- Create: `apps/backend/app/agents/test_point_generation/skills/test-point-obligation-extraction/SKILL.md`
- Modify: `apps/backend/app/agents/test_point_generation/__init__.py`
- Test: `apps/backend/tests/test_test_point_obligation_extraction.py`

**Interfaces:**
- Produces: `RequirementObligation`
- Produces: `RequirementObligationExtractionResult`
- Produces: `extract_requirement_obligations(input_data: TestPointGenerationInput) -> RequirementObligationExtractionResult`
- Consumes: existing `build_agent_model()` and `SkillMiddleware`

- [ ] **Step 1: Write failing schema and service tests**

Cover:

```python
def test_obligation_schema_requires_source_and_statement():
    with pytest.raises(ValidationError):
        RequirementObligation(
            obligation_key="REQ-001",
            source_section="",
            statement="",
            obligation_type="business_rule",
        )


@pytest.mark.asyncio
async def test_extraction_uses_only_final_requirement_content(monkeypatch):
    captured = {}

    async def fake_invoke(payload):
        captured["content"] = payload["messages"][0]["content"]
        return {
            "structured_response": RequirementObligationExtractionResult(
                obligations=[sample_obligation("REQ-001")],
                unverifiable_items=[],
            )
        }

    monkeypatch.setattr(obligation_service, "requirement_obligation_agent", lambda model: FakeAgent(fake_invoke))
    result = await obligation_service.extract_requirement_obligations(sample_input())
    assert "最终需求文档" in captured["content"]
    assert "初始需求" not in captured["content"]
    assert len(result.obligations) == 1
```

- [ ] **Step 2: Run tests and verify failure**

Run: `cd apps/backend; uv run pytest tests/test_test_point_obligation_extraction.py -q`

Expected: FAIL because obligation schemas and extraction service do not exist.

- [ ] **Step 3: Add structured obligation schemas**

Define:

```python
class RequirementObligation(BaseModel):
    obligation_key: str = Field(min_length=1, max_length=120)
    source_section: str = Field(min_length=1, max_length=240)
    statement: str = Field(min_length=1)
    obligation_type: Literal[
        "business_rule",
        "module",
        "flow",
        "threshold",
        "compatibility",
        "display",
        "logging",
        "performance",
        "permission",
        "security",
        "exception",
    ]
    modules: list[str] = Field(default_factory=list)
    thresholds: list[str] = Field(default_factory=list)
    explicit: bool = True
    test_required: bool = True


class RequirementObligationExtractionResult(BaseModel):
    obligations: list[RequirementObligation] = Field(min_length=1)
    unverifiable_items: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Implement extraction Agent and skill**

The skill must explicitly state:

```text
唯一输入是“最终需求文档”。
不得使用初始需求、待澄清项、行业惯例或通用测试经验补充义务。
每条义务必须引用最终需求中的 source_section。
最终需求未定义处理结果时，记录到 unverifiable_items，不猜测预期。
明确列出的每个模块、节点和页面分别建立可追踪义务。
```

Use `ToolStrategy(RequirementObligationExtractionResult)` and the same assigned `test_point_generation` model capability.

- [ ] **Step 5: Run extraction tests**

Run: `cd apps/backend; uv run pytest tests/test_test_point_obligation_extraction.py -q`

Expected: PASS.

---

### Task 3: 建立确定性覆盖校验器

**Files:**
- Create: `apps/backend/app/agents/test_point_generation/coverage.py`
- Modify: `apps/backend/app/agents/test_point_generation/schemas.py`
- Test: `apps/backend/tests/test_test_point_coverage.py`

**Interfaces:**
- Produces: `TestPointCoverageResult`
- Produces: `evaluate_test_point_coverage(obligations, points, unsupported_assumptions) -> TestPointCoverageResult`
- Consumes: `GeneratedTestPoint.requirement_obligation_keys`

- [ ] **Step 1: Write failing coverage tests**

Cover complete, missing, unknown and duplicate mappings:

```python
def test_coverage_is_complete_when_every_required_obligation_is_linked():
    result = evaluate_test_point_coverage(
        [obligation("REQ-001"), obligation("REQ-002")],
        [point("point-1", ["REQ-001"]), point("point-2", ["REQ-002"])],
        [],
    )
    assert result.status == "complete"
    assert result.missing_obligation_keys == []


def test_coverage_reports_missing_required_obligations():
    result = evaluate_test_point_coverage(
        [obligation("REQ-001"), obligation("REQ-002")],
        [point("point-1", ["REQ-001"])],
        [],
    )
    assert result.status == "incomplete"
    assert result.missing_obligation_keys == ["REQ-002"]


def test_coverage_rejects_unknown_obligation_links():
    result = evaluate_test_point_coverage(
        [obligation("REQ-001")],
        [point("point-1", ["REQ-999"])],
        [],
    )
    assert result.status == "invalid"
    assert result.unknown_obligation_keys == ["REQ-999"]
```

- [ ] **Step 2: Run tests and verify failure**

Run: `cd apps/backend; uv run pytest tests/test_test_point_coverage.py -q`

Expected: FAIL because coverage evaluator does not exist.

- [ ] **Step 3: Extend generated point schema**

Add:

```python
requirement_obligation_keys: list[str] = Field(min_length=1)
```

Define coverage result fields:

```python
status: Literal["complete", "incomplete", "invalid"]
obligation_count: int
covered_obligation_count: int
missing_obligation_keys: list[str]
unknown_obligation_keys: list[str]
unsupported_assumptions: list[str]
```

- [ ] **Step 4: Implement deterministic evaluator**

Rules:

```python
required_keys = {item.obligation_key for item in obligations if item.test_required}
linked_keys = {
    key
    for point in points
    for key in point.requirement_obligation_keys
}
missing = sorted(required_keys - linked_keys)
unknown = sorted(linked_keys - {item.obligation_key for item in obligations})
```

Return `invalid` for unknown keys or unsupported assumptions, `incomplete` for missing required keys, otherwise `complete`.

- [ ] **Step 5: Run coverage tests**

Run: `cd apps/backend; uv run pytest tests/test_test_point_coverage.py -q`

Expected: PASS.

---

### Task 4: 改造生成和缺口补齐闭环

**Files:**
- Modify: `apps/backend/app/agents/test_point_generation/service.py`
- Modify: `apps/backend/app/agents/test_point_generation/skills/test-point-generation/SKILL.md`
- Modify: `apps/backend/app/agents/test_point_generation/skills/test-point-generation/reference.md`
- Modify: `apps/backend/app/services/test_point_service.py:161`
- Test: `apps/backend/tests/test_test_point_generation_service.py`
- Test: `apps/backend/tests/test_test_point_markdown_service.py`

**Interfaces:**
- Produces: `generate_test_points(input_data, obligations, existing_points=None, missing_obligation_keys=None)`
- Produces: maximum `MAX_SUPPLEMENT_ROUNDS = 3`
- Consumes: `extract_requirement_obligations()` and `evaluate_test_point_coverage()`

- [ ] **Step 1: Write failing orchestration tests**

Cover initial completion, one-round supplement and final failure:

```python
@pytest.mark.asyncio
async def test_generation_supplements_only_missing_obligations(monkeypatch):
    monkeypatch.setattr(test_point_service, "extract_requirement_obligations", AsyncMock(return_value=obligations("REQ-001", "REQ-002")))
    generate = AsyncMock(side_effect=[
        generation(point("p1", ["REQ-001"])),
        generation(point("p2", ["REQ-002"])),
    ])
    monkeypatch.setattr(test_point_service, "generate_test_points", generate)

    await test_point_service.execute_generation_run("run-1")

    assert generate.await_count == 2
    assert generate.await_args_list[1].kwargs["missing_obligation_keys"] == ["REQ-002"]
    assert load_run("run-1")["coverage_status"] == "complete"
    assert load_run("run-1")["status"] == "completed"


@pytest.mark.asyncio
async def test_generation_fails_after_three_incomplete_supplements(monkeypatch):
    monkeypatch.setattr(test_point_service, "generate_test_points", always_returns_only_req_001)
    await test_point_service.execute_generation_run("run-1")
    run = load_run("run-1")
    assert run["status"] == "failed"
    assert run["coverage_status"] == "incomplete"
    assert json.loads(run["missing_obligations_json"]) == ["REQ-002"]
    assert run["supplement_round"] == 3
```

- [ ] **Step 2: Run orchestration tests and verify failure**

Run: `cd apps/backend; uv run pytest tests/test_test_point_generation_service.py tests/test_test_point_markdown_service.py -q`

Expected: FAIL because the current service saves the first model result and marks it completed.

- [ ] **Step 3: Strengthen generation prompt contract**

The generation skill must state:

```text
输入的需求义务清单是必须覆盖全集。
每个 test_required=true 的 obligation_key 至少出现在一个测试点中。
不得用“所有节点均支持”一条笼统测试点替代最终需求明确列出的多个节点。
missing_obligation_keys 非空时只补充这些缺口，不重写已生成测试点。
不得生成无法回指义务 ID 的测试点。
不得添加最终需求未定义的异常、权限、并发、安全、性能和日志行为。
```

- [ ] **Step 4: Implement generation loop**

Use this order inside `execute_generation_run()`:

```python
obligation_result = await extract_requirement_obligations(input_data)
points = []
unsupported_assumptions = []

for supplement_round in range(MAX_SUPPLEMENT_ROUNDS + 1):
    generation = await generate_test_points(
        input_data,
        obligations=obligation_result.obligations,
        existing_points=points,
        missing_obligation_keys=coverage.missing_obligation_keys if points else None,
    )
    points = merge_generated_points(points, generation.points)
    unsupported_assumptions = generation.unsupported_assumptions
    coverage = evaluate_test_point_coverage(
        obligation_result.obligations,
        points,
        unsupported_assumptions,
    )
    if coverage.status == "complete":
        break
```

Persist obligations, points, links and the completed run in one database transaction only after final validation. On failure, persist obligations and run diagnostics, but do not replace the previous complete point set with a partial set.

- [ ] **Step 5: Preserve existing points during regeneration failure**

Change requeue behavior so existing complete points remain visible while regeneration runs. Replace them only after a new complete generation succeeds. This prevents a failed supplement cycle from deleting the last valid result.

- [ ] **Step 6: Run orchestration tests**

Run: `cd apps/backend; uv run pytest tests/test_test_point_generation_service.py tests/test_test_point_markdown_service.py -q`

Expected: PASS.

---

### Task 5: 保持 Markdown 编辑后的义务映射

**Files:**
- Modify: `apps/backend/app/services/test_point_markdown.py`
- Modify: `apps/backend/app/services/test_point_service.py:76`
- Modify: `apps/backend/app/repositories/test_point_repo.py`
- Test: `apps/backend/tests/test_test_point_markdown.py`
- Test: `apps/backend/tests/test_test_point_markdown_service.py`

**Interfaces:**
- Produces: Markdown field `需求义务`
- Produces: `recalculate_persisted_coverage(db, document_id, version_id)`
- Consumes: persisted obligation keys

- [ ] **Step 1: Write failing Markdown round-trip tests**

Expected format:

```markdown
| 需求义务 | REQ-001, REQ-002 |
```

Tests:

```python
def test_markdown_round_trip_preserves_obligation_keys():
    markdown = serialize_test_points([
        sample_point(requirement_obligation_keys=["REQ-001", "REQ-002"])
    ])
    parsed = parse_test_points(markdown)
    assert parsed[0]["requirement_obligation_keys"] == ["REQ-001", "REQ-002"]


def test_markdown_rejects_unknown_obligation_key():
    with pytest.raises(ApiError, match="不存在的需求义务"):
        save_markdown_with_obligation("REQ-999")
```

- [ ] **Step 2: Run Markdown tests and verify failure**

Run: `cd apps/backend; uv run pytest tests/test_test_point_markdown.py tests/test_test_point_markdown_service.py -q`

Expected: FAIL because Markdown does not currently serialize obligation mappings.

- [ ] **Step 3: Extend parser and serializer**

Add a required `需求义务` field for versions that have persisted obligations. For legacy versions without obligations, accept missing mapping and report coverage as `pending` rather than fabricating links.

- [ ] **Step 4: Recalculate coverage after save, update and delete**

After Markdown replacement, point update or point deletion:

```python
coverage = recalculate_persisted_coverage(db, document_id, version_id)
test_point_repo.update_run(
    db,
    run_id,
    coverage_status=coverage.status,
    obligation_count=coverage.obligation_count,
    covered_obligation_count=coverage.covered_obligation_count,
    missing_obligations_json=json.dumps(coverage.missing_obligation_keys, ensure_ascii=False),
)
```

Manual deletion is allowed, but the overview must immediately show `incomplete` and list the newly missing obligations.

- [ ] **Step 5: Run Markdown and service tests**

Run: `cd apps/backend; uv run pytest tests/test_test_point_markdown.py tests/test_test_point_markdown_service.py -q`

Expected: PASS.

---

### Task 6: 暴露覆盖摘要并更新前端

**Files:**
- Modify: `apps/backend/app/schemas/test_point.py:27`
- Modify: `apps/backend/app/services/test_point_service.py:28`
- Modify: `apps/frontend/src/lib/api-client.ts:272`
- Modify: `apps/frontend/src/components/ai-testing/test-points-panel.tsx`
- Create: `apps/frontend/src/components/ai-testing/test-point-coverage-summary.tsx`
- Modify: `apps/frontend/tests/test-points-panel-contract.test.mjs`
- Create: `apps/frontend/tests/test-point-coverage-summary-contract.test.mjs`

**Interfaces:**
- Produces API type: `ApiTestPointCoverageSummary`
- Produces component: `TestPointCoverageSummary`
- Consumes backend overview fields and existing test-points panel loading loop

- [ ] **Step 1: Write failing backend response and frontend contract tests**

Backend response must expose:

```python
class TestPointCoverageSummaryOut(BaseModel):
    status: Literal["pending", "complete", "incomplete", "invalid"]
    obligation_count: int
    covered_obligation_count: int
    missing_obligations: list[RequirementObligationOut]
    unsupported_assumptions: list[str]
    supplement_round: int
```

Frontend contract assertions:

```javascript
assert.match(apiClientSource, /coverage_summary: ApiTestPointCoverageSummary/);
assert.match(panelSource, /<TestPointCoverageSummary/);
assert.match(summarySource, /需求义务/);
assert.match(summarySource, /已覆盖/);
assert.match(summarySource, /未覆盖/);
assert.match(summarySource, /当前测试点未生成完整/);
```

- [ ] **Step 2: Run response and frontend tests and verify failure**

Run: `cd apps/backend; uv run pytest tests/test_test_point_markdown_service.py -q`

Run: `cd apps/frontend; node --test tests/test-points-panel-contract.test.mjs tests/test-point-coverage-summary-contract.test.mjs`

Expected: FAIL because coverage summary is not exposed or rendered.

- [ ] **Step 3: Extend backend overview response**

Return an empty/pending summary when there is no final version or no obligation extraction. For generated versions, return counts, missing obligation detail, unsupported assumptions and supplement round.

- [ ] **Step 4: Extend TypeScript API types**

Add:

```typescript
export type ApiTestPointRequirementObligation = {
  obligation_key: string;
  source_section: string;
  statement: string;
};

export type ApiTestPointCoverageSummary = {
  status: "pending" | "complete" | "incomplete" | "invalid";
  obligation_count: number;
  covered_obligation_count: number;
  missing_obligations: ApiTestPointRequirementObligation[];
  unsupported_assumptions: string[];
  supplement_round: number;
};
```

- [ ] **Step 5: Implement coverage summary UI**

Render:

```text
需求义务：12 条
已覆盖：12 条
未覆盖：0 条
测试点：18 条
```

For incomplete or invalid coverage, display a warning panel with each missing obligation's key, statement and source section. Keep the generated point list visible so users can inspect partial or previous valid results.

- [ ] **Step 6: Run backend and frontend tests**

Run: `cd apps/backend; uv run pytest tests/test_test_point_markdown_service.py -q`

Run: `cd apps/frontend; node --test tests/test-points-panel-contract.test.mjs tests/test-point-coverage-summary-contract.test.mjs`

Expected: PASS.

---

### Task 7: 完整回归和真实 PRD 固定样例验证

**Files:**
- Create: `apps/backend/tests/fixtures/test_point_requirements/long_text_final_requirement.md`
- Create: `apps/backend/tests/test_test_point_coverage_end_to_end.py`
- Modify: `apps/backend/tests/test_test_case_set_service.py`
- Modify: `apps/frontend/tests/test-points-panel-contract.test.mjs`

**Interfaces:**
- Consumes: complete obligation-generation-coverage pipeline
- Verifies: downstream test case generation still reads structured test points without requiring obligation internals

- [ ] **Step 1: Add a deterministic final-requirement fixture**

The fixture must include only final requirements and cover:

```text
- 12 explicitly listed node types
- >10000 character external storage
- <=10000 character compatibility
- runtime chunk reference
- downstream full-content restoration
- chunked display on explicitly listed pages
- 20000 character field limit without inventing unspecified over-limit handling
- historical conversation compatibility
- logging fields
```

- [ ] **Step 2: Write an end-to-end service test with fake structured agents**

Assert:

```python
assert run["status"] == "completed"
assert run["coverage_status"] == "complete"
assert run["obligation_count"] == run["covered_obligation_count"]
assert overview["coverage_summary"]["missing_obligations"] == []
assert all(point["requirement_obligation_keys"] for point in overview["points"])
```

Also assert that the generated test point titles and expectations do not contain invented database-failure, permission, concurrency or security behavior absent from the fixture.

- [ ] **Step 3: Verify downstream compatibility**

Update the test-case-set fixture to include obligation mappings on test points, then assert the existing test-case generation input still contains the same point title, module, category, priority, description, preconditions and verification points.

- [ ] **Step 4: Run focused backend suite**

Run:

```bash
cd apps/backend
uv run pytest \
  tests/test_test_point_coverage_repo.py \
  tests/test_test_point_obligation_extraction.py \
  tests/test_test_point_coverage.py \
  tests/test_test_point_generation_service.py \
  tests/test_test_point_markdown.py \
  tests/test_test_point_markdown_service.py \
  tests/test_test_point_coverage_end_to_end.py \
  tests/test_test_case_set_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Run frontend contracts and static checks**

Run:

```bash
cd apps/frontend
node --test tests/test-points-panel-contract.test.mjs tests/test-point-coverage-summary-contract.test.mjs
npm run check -- src/components/ai-testing/test-points-panel.tsx src/components/ai-testing/test-point-coverage-summary.tsx src/lib/api-client.ts
```

Expected: all contract tests and Biome checks pass.

- [ ] **Step 6: Run broader regression**

Run: `cd apps/backend; uv run pytest tests/test_test_case_set_service.py tests/test_test_point_markdown_service.py -q`

Run: `cd apps/frontend; npm run build`

Expected: PASS. If unrelated pre-existing failures occur, record them without changing unrelated modules.

---

## Delivery Checklist

- [ ] 数据库迁移对已有 SQLite 数据库幂等执行。
- [ ] 重新生成失败时保留上一份完整测试点，不清空有效数据。
- [ ] 模型返回 1 条但存在未覆盖义务时任务不会完成。
- [ ] 缺口补齐请求只包含缺失义务，不重复生成全部测试点。
- [ ] 义务映射能经 Markdown 编辑完整往返。
- [ ] 删除测试点会立即产生可见覆盖缺口。
- [ ] 前端覆盖摘要和后端计数一致。
- [ ] 下游测试用例生成保持兼容。
- [ ] 未引入最终需求外的通用场景。
