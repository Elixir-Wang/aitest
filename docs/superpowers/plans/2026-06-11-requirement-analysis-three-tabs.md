# Requirement Analysis Three Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the requirement detail page analysis area to three sub tabs: `需求分析`, `待澄清`, and `质量保证`, while converting clarification Markdown into the existing clickable clarification-question structure.

**Architecture:** Keep the existing `RequirementAnalysisOutput` as the API envelope, but extend it with `clarification_report_markdown` and `quality_assurance_report_markdown`. The agent may write three Markdown reports, but the backend normalizes the clarification report into `clarification_questions` and `conflicts`, so the frontend keeps the current clickable answer flow. The frontend renders `需求分析` from `analysis_report_markdown`, `待澄清` from structured questions/conflicts, and `质量保证` from `quality_gate`, `coverage_audit`, and optional quality Markdown.

**Tech Stack:** FastAPI backend, Pydantic, pytest, Next.js 16, React 19, TypeScript, shadcn/radix tabs, node:test contract tests, Biome.

---

## File Structure

- Modify: `apps/backend/app/agents/requirement_analysis_codex/schemas.py`
  - Add optional Markdown report fields for clarification and quality assurance.
- Modify: `apps/backend/app/agents/requirement_analysis_codex/output_parser.py`
  - Read `output/clarification.md` and `output/quality.md`.
  - Convert constrained clarification Markdown into `clarification_questions` / `conflicts` when structured fields are absent or incomplete.
- Modify: `apps/backend/app/agents/requirement_analysis_codex/prompt.py`
  - Ask Codex to generate three report files and keep clarification content parseable.
- Modify: `apps/backend/app/agents/requirement_analysis_codex/skills/requirement-analysis/references/output-contract.md`
  - Document the three Markdown files and fallback parsing contract.
- Modify: `apps/backend/app/agents/requirement_analysis_codex/skills/requirement-analysis/references/clarification-report.md`
  - Define the exact Markdown syntax that can be parsed into clickable items.
- Modify: `apps/backend/app/agents/requirement_analysis_codex/skills/requirement-analysis/references/quality-assurance-report.md`
  - Define the quality assurance Markdown report.
- Modify: `apps/backend/tests/test_requirement_analysis_agent.py`
  - Add parser and file-reading tests.
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx`
  - Replace current sub tabs with `需求分析`, `待澄清`, `质量保证`.
  - Keep the clickable clarification card flow under `待澄清`.
  - Add a quality assurance view.
- Modify: `apps/frontend/tests/requirement-detail-analysis-contract.test.mjs`
  - Update contract assertions for the three-tab UI and current clickable clarification structure.

---

### Task 1: Backend Schema And Markdown File Contract

**Files:**
- Modify: `apps/backend/app/agents/requirement_analysis_codex/schemas.py`
- Modify: `apps/backend/app/agents/requirement_analysis_codex/output_parser.py`
- Test: `apps/backend/tests/test_requirement_analysis_agent.py`

- [ ] **Step 1: Write the failing backend test for three report files**

Append this test near the existing output parser tests in `apps/backend/tests/test_requirement_analysis_agent.py`:

```python
def test_requirement_analysis_reads_three_markdown_reports(tmp_path):
    from app.agents.requirement_analysis_codex.output_parser import read_analysis_output

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "analysis.json").write_text(
        """
        {
          "status": "needs_clarification",
          "analysis_summary": "已完成主需求分析。",
          "preliminary_requirement_markdown": "# 初步需求",
          "applied_supplements": [],
          "clarification_questions": [],
          "conflicts": [],
          "coverage_audit": [],
          "quality_gate": {
            "result": "warning",
            "testability_score": 70,
            "blocking_issues": [],
            "warning_issues": ["待澄清项影响测试覆盖"],
            "passed_checks": ["主流程已识别"]
          },
          "next_actions": []
        }
        """,
        encoding="utf-8",
    )
    (output_dir / "analysis.md").write_text("# 需求分析\n\n主流程已识别。", encoding="utf-8")
    (output_dir / "clarification.md").write_text(
        """
        # 待澄清

        ## CQ-001 登录
        - 模块Key：login
        - 类型：clarification
        - 维度：validation_rule
        - 严重级别：major
        - 问题：验证码连续输错达到多少次后应锁定登录尝试？
        - 影响：不确认会影响登录异常路径和自动化用例断言。
        - 来源：需求只说明“验证码登录”，未说明错误次数限制。
        - 选项A：3 次后锁定 15 分钟。|登录验证码连续输错 3 次后，系统应锁定该账号的验证码登录尝试 15 分钟。
        - 选项B：5 次后锁定 15 分钟。|登录验证码连续输错 5 次后，系统应锁定该账号的验证码登录尝试 15 分钟。

        ## CF-001 登录
        - 模块Key：login
        - 类型：conflict
        - 严重级别：blocker
        - 问题：短信验证码和邮箱验证码是否都属于本期登录方式？
        - 影响：不确认会导致认证入口、测试数据和通知通道设计分歧。
        - 来源：标题写验证码登录，正文同时出现短信和邮箱。
        """.strip(),
        encoding="utf-8",
    )
    (output_dir / "quality.md").write_text("# 质量保证\n\n可测试性 70 分。", encoding="utf-8")

    output = read_analysis_output(tmp_path)

    assert output.analysis_report_markdown == "# 需求分析\n\n主流程已识别。"
    assert output.clarification_report_markdown.startswith("# 待澄清")
    assert output.quality_assurance_report_markdown == "# 质量保证\n\n可测试性 70 分。"
    assert output.clarification_questions[0].id == "CQ-001"
    assert output.clarification_questions[0].module_key == "login"
    assert output.clarification_questions[0].dimension == "validation_rule"
    assert output.clarification_questions[0].recommended_options[0].answer_markdown.startswith("登录验证码连续输错 3 次")
    assert output.conflicts[0].id == "CF-001"
    assert output.conflicts[0].issue_type == "conflict"
```

- [ ] **Step 2: Run the new backend test and verify it fails**

Run:

```powershell
cd D:\project\test_project\apps\backend
.\.venv\Scripts\python.exe -m pytest tests/test_requirement_analysis_agent.py::test_requirement_analysis_reads_three_markdown_reports -q
```

Expected: FAIL because `RequirementAnalysisOutput` does not yet expose `clarification_report_markdown` and `quality_assurance_report_markdown`.

- [ ] **Step 3: Extend the schema**

In `apps/backend/app/agents/requirement_analysis_codex/schemas.py`, change `RequirementAnalysisOutput`:

```python
class RequirementAnalysisOutput(BaseModel):
    status: Literal["completed", "needs_clarification", "blocked"]
    analysis_summary: str
    preliminary_requirement_markdown: str = ""
    analysis_report_markdown: str = ""
    clarification_report_markdown: str = ""
    quality_assurance_report_markdown: str = ""
    applied_supplements: list[RequirementAppliedSupplement] = Field(default_factory=list)
    maturity_assessment: RequirementMaturityAssessment | None = None
    key_gaps: list[RequirementGapItem] = Field(default_factory=list)
    assumptions: list[RequirementAssumptionItem] = Field(default_factory=list)
    modules: list[RequirementAnalysisModule] = Field(default_factory=list)
    clarification_questions: list[RequirementClarificationQuestion | RequirementUnresolvedFinding] = Field(default_factory=list)
    conflicts: list[RequirementUnresolvedFinding] = Field(default_factory=list)
    coverage_audit: list[RequirementCoverageAuditItem] = Field(default_factory=list)
    quality_gate: RequirementQualityGate
    next_actions: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Read the three Markdown report files**

In `apps/backend/app/agents/requirement_analysis_codex/output_parser.py`, update `read_analysis_output`:

```python
def read_analysis_output(workdir: Path) -> RequirementAnalysisOutput:
    output_path = workdir / "output" / "analysis.json"
    if not output_path.exists():
        raise ValueError("需求分析智能体未生成 output/analysis.json。")
    raw_output = json.loads(output_path.read_text(encoding="utf-8"))

    report_path = workdir / "output" / "analysis.md"
    if report_path.exists():
        report = report_path.read_text(encoding="utf-8").strip()
        if report:
            raw_output["analysis_report_markdown"] = report

    clarification_path = workdir / "output" / "clarification.md"
    if clarification_path.exists():
        clarification_report = clarification_path.read_text(encoding="utf-8").strip()
        if clarification_report:
            raw_output["clarification_report_markdown"] = clarification_report

    quality_path = workdir / "output" / "quality.md"
    if quality_path.exists():
        quality_report = quality_path.read_text(encoding="utf-8").strip()
        if quality_report:
            raw_output["quality_assurance_report_markdown"] = quality_report

    normalized_output = normalize_analysis_output(raw_output)
    return RequirementAnalysisOutput.model_validate(normalized_output)
```

- [ ] **Step 5: Convert clarification Markdown into clickable items**

In `apps/backend/app/agents/requirement_analysis_codex/output_parser.py`, add `import re` and these helpers near the other normalization helpers:

```python
def parse_clarification_markdown(markdown: str) -> tuple[list[dict], list[dict]]:
    questions: list[dict] = []
    conflicts: list[dict] = []
    sections = re.split(r"(?m)^##\s+", markdown or "")
    for raw_section in sections[1:]:
        lines = [line.strip() for line in raw_section.splitlines() if line.strip()]
        if not lines:
            continue
        heading = lines[0]
        heading_match = re.match(r"(?P<id>(?:CQ|CF)-\d+)\s*(?P<module>.*)", heading)
        if not heading_match:
            continue
        item_id = heading_match.group("id")
        default_module_name = heading_match.group("module").strip() or "通用"
        fields = _parse_clarification_markdown_fields(lines[1:])
        module_name = fields.get("模块") or default_module_name
        module_key = fields.get("模块Key") or slug(module_name) or "general"
        severity = normalize_severity(fields.get("严重级别"))
        source_excerpt = fields.get("来源") or fields.get("摘录") or ""
        question = fields.get("问题") or "需要人工确认。"
        impact = fields.get("影响") or "不确认会影响后续设计、开发、测试或验收判断。"
        options = _parse_clarification_markdown_options(fields)
        if item_id.startswith("CF-") or fields.get("类型") == "conflict":
            conflicts.append(
                {
                    "id": item_id,
                    "module_key": module_key,
                    "module_name": module_name,
                    "issue_type": "conflict",
                    "question": question,
                    "impact": impact,
                    "severity": severity,
                    "primary_excerpt": source_excerpt,
                    "recommended_options": options,
                }
            )
        else:
            dimension = fields.get("维度") if fields.get("维度") in _DIMENSIONS else "other"
            questions.append(
                {
                    "id": item_id,
                    "module_key": module_key,
                    "module_name": module_name,
                    "question": question,
                    "impact": impact,
                    "dimension": dimension,
                    "severity": severity,
                    "source_excerpt": source_excerpt,
                    "recommended_options": options,
                }
            )
    return questions, conflicts


def _parse_clarification_markdown_fields(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^[-*]\s*([^：:]+)[：:]\s*(.*)$", line)
        if not match:
            continue
        key = match.group(1).strip()
        value = match.group(2).strip()
        fields[key] = value
    return fields


def _parse_clarification_markdown_options(fields: dict[str, str]) -> list[dict]:
    options: list[dict] = []
    for index, key in enumerate(("选项A", "选项B"), start=1):
        raw = fields.get(key, "").strip()
        if not raw:
            continue
        label, _, answer = raw.partition("|")
        answer_markdown = answer.strip() or label.strip()
        options.append(
            {
                "id": f"OPT-{index:03d}",
                "label": label.strip() or f"选项 {index}",
                "answer_markdown": answer_markdown,
                "rationale": "",
                "confidence": "medium",
            }
        )
    return options
```

Then update `normalize_analysis_output` before normalizing findings:

```python
    clarification_report = str(output.get("clarification_report_markdown") or "").strip()
    parsed_questions: list[dict] = []
    parsed_conflicts: list[dict] = []
    if clarification_report:
        parsed_questions, parsed_conflicts = parse_clarification_markdown(clarification_report)
    if parsed_questions and not output.get("clarification_questions"):
        output["clarification_questions"] = parsed_questions
    if parsed_conflicts and not output.get("conflicts"):
        output["conflicts"] = parsed_conflicts
```

- [ ] **Step 6: Run the backend parser test**

Run:

```powershell
cd D:\project\test_project\apps\backend
.\.venv\Scripts\python.exe -m pytest tests/test_requirement_analysis_agent.py::test_requirement_analysis_reads_three_markdown_reports -q
```

Expected: PASS.

---

### Task 2: Agent Prompt And Skill Contract For Three Reports

**Files:**
- Modify: `apps/backend/app/agents/requirement_analysis_codex/prompt.py`
- Modify: `apps/backend/app/agents/requirement_analysis_codex/skills/requirement-analysis/references/output-contract.md`
- Modify: `apps/backend/app/agents/requirement_analysis_codex/skills/requirement-analysis/references/clarification-report.md`
- Modify: `apps/backend/app/agents/requirement_analysis_codex/skills/requirement-analysis/references/quality-assurance-report.md`
- Test: `apps/backend/tests/test_requirement_analysis_agent.py`

- [ ] **Step 1: Update the prompt contract test**

In `apps/backend/tests/test_requirement_analysis_agent.py`, extend `test_requirement_analysis_codex_prompt_uses_requirement_analysis_with_testability_view`:

```python
    assert "output/analysis.md" in prompt
    assert "output/clarification.md" in prompt
    assert "output/quality.md" in prompt
    assert "clarification_report_markdown" in prompt
    assert "quality_assurance_report_markdown" in prompt
    assert "待澄清 Markdown 必须使用可解析格式" in prompt
```

- [ ] **Step 2: Run the prompt test and verify it fails**

Run:

```powershell
cd D:\project\test_project\apps\backend
.\.venv\Scripts\python.exe -m pytest tests/test_requirement_analysis_agent.py::test_requirement_analysis_codex_prompt_uses_requirement_analysis_with_testability_view -q
```

Expected: FAIL because the prompt only requires `analysis.json` and `analysis.md`.

- [ ] **Step 3: Update `prompt.py`**

In `apps/backend/app/agents/requirement_analysis_codex/prompt.py`, replace the current output file bullet block with:

```python
            "- 必须生成 output/analysis.json，内容必须符合 RequirementAnalysisOutput。",
            "- 必须生成 output/analysis.md，作为“需求分析”子 tab 展示内容。",
            "- 必须生成 output/clarification.md，作为“待澄清”来源文档。",
            "- 必须生成 output/quality.md，作为“质量保证”子 tab 展示内容。",
            "- analysis.json.analysis_report_markdown 必须等于 output/analysis.md 的正文。",
            "- analysis.json.clarification_report_markdown 必须等于 output/clarification.md 的正文。",
            "- analysis.json.quality_assurance_report_markdown 必须等于 output/quality.md 的正文。",
            "- 待澄清 Markdown 必须使用可解析格式：每个条目以 ## CQ-001 或 ## CF-001 开头，并用“- 字段：值”描述模块、维度、严重级别、问题、影响、来源和选项。",
```

Keep these existing behavioral rules:

```python
            "- 需要人工回答或裁决的内容必须进入 clarification_questions/conflicts，由待澄清 tab 展示。",
            "- clarification_questions/conflicts 必须使用 module_key、module_name、question、impact、severity 等结构化字段。",
```

- [ ] **Step 4: Update `output-contract.md`**

In `apps/backend/app/agents/requirement_analysis_codex/skills/requirement-analysis/references/output-contract.md`, change Required Files to:

```markdown
## Required Files

- Write `output/analysis.json`.
- Write `output/analysis.md`.
- Write `output/clarification.md`.
- Write `output/quality.md`.
- Set `analysis.json.analysis_report_markdown` to the exact body of `output/analysis.md`.
- Set `analysis.json.clarification_report_markdown` to the exact body of `output/clarification.md`.
- Set `analysis.json.quality_assurance_report_markdown` to the exact body of `output/quality.md`.
```

Change Runtime Mapping to:

```markdown
| View | Runtime destination |
| --- | --- |
| 需求分析 | `output/analysis.md`, `analysis_report_markdown` |
| 待澄清 | `output/clarification.md`, `clarification_report_markdown`, `clarification_questions`, `conflicts` |
| 质量保证 | `output/quality.md`, `quality_assurance_report_markdown`, `coverage_audit`, `quality_gate` |
```

- [ ] **Step 5: Update `clarification-report.md` parse format**

Add this exact format section:

```markdown
## Parseable Markdown Format

Each clickable item must use this format:

```markdown
## CQ-001 模块名
- 模块Key：module_key
- 类型：clarification
- 维度：validation_rule
- 严重级别：major
- 问题：直接面向人工确认的问题？
- 影响：不确认造成的下游影响。
- 来源：主需求中的证据或缺失说明。
- 选项A：短标签|可直接写入初步需求的 Markdown
- 选项B：短标签|可直接写入初步需求的 Markdown
```

Conflicts use `CF-001` and `类型：conflict`.
```

- [ ] **Step 6: Update `quality-assurance-report.md`**

Add this exact Markdown shape:

```markdown
## Quality Assurance Markdown Shape

```markdown
# 质量保证

## 质量门禁
- 结果：warning
- 可测试性评分：70

## 阻塞问题
- ...

## 风险警告
- ...

## 已通过检查
- ...

## 覆盖审计
| 模块 | 状态 | 原因 |
| --- | --- | --- |
| 登录 | pending_clarification | 缺少验证码错误次数 |

## 下一步建议
- ...
```
```

- [ ] **Step 7: Run backend prompt and parser tests**

Run:

```powershell
cd D:\project\test_project\apps\backend
.\.venv\Scripts\python.exe -m pytest tests/test_requirement_analysis_agent.py::test_requirement_analysis_codex_prompt_uses_requirement_analysis_with_testability_view tests/test_requirement_analysis_agent.py::test_requirement_analysis_reads_three_markdown_reports -q
```

Expected: PASS.

---

### Task 3: Frontend Contract For Three Analysis Sub Tabs

**Files:**
- Modify: `apps/frontend/tests/requirement-detail-analysis-contract.test.mjs`
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx`

- [ ] **Step 1: Write the failing frontend contract test**

Update `apps/frontend/tests/requirement-detail-analysis-contract.test.mjs` first test:

```js
test("requirement detail exposes the three requirement analysis subtabs", () => {
  assert.match(pageSource, /<TabsTrigger value="analysis">需求分析<\/TabsTrigger>/);
  assert.match(pageSource, /<TabsTrigger value="final">最终需求<\/TabsTrigger>/);
  assert.match(pageSource, /<TabsTrigger value="analysis-report">需求分析<\/TabsTrigger>/);
  assert.match(pageSource, /<TabsTrigger value="clarification">待澄清<\/TabsTrigger>/);
  assert.match(pageSource, /<TabsTrigger value="quality">质量保证<\/TabsTrigger>/);
  assert.doesNotMatch(pageSource, /<TabsTrigger value="preliminary">初步需求<\/TabsTrigger>/);
  assert.doesNotMatch(pageSource, /<TabsTrigger value="pending">待确认问题<\/TabsTrigger>/);
  assert.doesNotMatch(pageSource, /<TabsTrigger value="report">分析报告<\/TabsTrigger>/);
});
```

Add a new contract test:

```js
test("clarification tab keeps the clickable answer structure", () => {
  assert.match(pageSource, /value="clarification"/);
  assert.match(pageSource, /visiblePendingAnalysisItems\.map/);
  assert.match(pageSource, /saveClarificationAnswer\(item\)/);
  assert.match(pageSource, /deferPendingItem\(item\.id\)/);
  assert.match(pageSource, /恢复暂不处理/);
  assert.match(pageSource, /保存答复/);
  assert.match(pageSource, /待澄清/);
  assert.doesNotMatch(pageSource, /待确认问题/);
});
```

Add a quality tab contract test:

```js
test("quality assurance tab renders gate and coverage fields", () => {
  assert.match(pageSource, /const qualityGate = analysisResult\?\.output\.quality_gate/);
  assert.match(pageSource, /const coverageAudit = analysisResult\?\.output\.coverage_audit \?\? \[\]/);
  assert.match(pageSource, /quality_assurance_report_markdown/);
  assert.match(pageSource, />质量门禁</);
  assert.match(pageSource, />覆盖审计</);
});
```

- [ ] **Step 2: Run the frontend contract test and verify it fails**

Run:

```powershell
cd D:\project\test_project\apps\frontend
node --test tests/requirement-detail-analysis-contract.test.mjs
```

Expected: FAIL because the page still contains `preliminary`, `pending`, and `report`.

- [ ] **Step 3: Update TypeScript output types**

In `apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx`, update `RequirementAnalysisResult.output`:

```ts
    analysis_report_markdown: string;
    clarification_report_markdown?: string;
    quality_assurance_report_markdown?: string;
```

Add quality status labels near `pendingSeverityLabels`:

```ts
const qualityResultLabels: Record<"passed" | "warning" | "blocked", string> = {
  passed: "通过",
  warning: "警告",
  blocked: "阻塞",
};

const coverageStatusLabels: Record<string, string> = {
  analyzed: "已分析",
  pending_clarification: "待澄清",
  not_testable: "不可测试",
  missing_detail: "缺少细节",
};
```

- [ ] **Step 4: Rename nested analysis tab state**

Change the state default:

```ts
const [analysisTab, setAnalysisTab] = useState("analysis-report");
```

Update any query routing that currently sets `analysisTab`:

```ts
if (queryTab === "initial") {
  setActiveTab("analysis");
  setAnalysisTab("analysis-report");
} else if (queryTab === "clarification") {
  setActiveTab("analysis");
  setAnalysisTab("clarification");
}
```

- [ ] **Step 5: Update derived analysis values**

Near the current `analysisReportMarkdown` constant, add:

```ts
const clarificationReportMarkdown = analysisResult?.output.clarification_report_markdown ?? "";
const qualityAssuranceMarkdown = analysisResult?.output.quality_assurance_report_markdown ?? "";
const qualityGate = analysisResult?.output.quality_gate;
const coverageAudit = analysisResult?.output.coverage_audit ?? [];
```

Keep `preliminaryMarkdown`; it still feeds the `转为最终需求` backend action even though it is no longer a visible sub tab.

- [ ] **Step 6: Update TOC routing**

Replace the analysis part of `showRequirementToc`:

```ts
(activeTab === "analysis" &&
  ((analysisTab === "analysis-report" && Boolean(analysisReportMarkdown.trim())) ||
    (analysisTab === "quality" && Boolean(qualityAssuranceMarkdown.trim())))) ||
```

Replace `requirementTocAnchorSelector` for the analysis branch:

```ts
: activeTab === "analysis"
  ? analysisTab === "quality"
    ? `#quality-assurance-section .requirement-document-preview`
    : `#analysis-report-section .requirement-document-preview`
```

Keep clarification out of the TOC because it is an interactive card list, not a Markdown document.

- [ ] **Step 7: Replace sub tab triggers**

Replace the current nested `TabsList`:

```tsx
<TabsList>
  <TabsTrigger value="analysis-report">需求分析</TabsTrigger>
  <TabsTrigger value="clarification">待澄清</TabsTrigger>
  <TabsTrigger value="quality">质量保证</TabsTrigger>
</TabsList>
```

Change the restore button condition:

```tsx
{analysisTab === "clarification" ? (
```

- [ ] **Step 8: Move the current pending card list under `clarification`**

Change:

```tsx
<TabsContent value="pending">
```

to:

```tsx
<TabsContent value="clarification">
```

Change empty text strings:

```tsx
{analysisResult
  ? deferredPendingAnalysisItems.length
    ? "待澄清事项已暂不处理，可通过右上角恢复。"
    : "暂无待澄清事项。"
  : "尚未执行需求分析，完成分析后会在这里展示待澄清事项。"}
```

Change `toast` and error labels only where the UI says `待确认问题` to `待澄清`:

```ts
toast.error("尚未生成需求分析结果");
actionLabel: "保存待澄清答复";
```

Do not rename backend endpoint paths; they remain `clarification-answers`.

- [ ] **Step 9: Replace report tab with analysis tab**

Change:

```tsx
<TabsContent id="analysis-report-section" value="report">
```

to:

```tsx
<TabsContent id="analysis-report-section" value="analysis-report">
```

Keep the `MarkdownPreview` content as:

```tsx
content={analysisReportMarkdown}
```

Update empty text:

```ts
const analysisReportEmptyText = reviewLoading
  ? "需求分析中，分析完成后会在这里展示需求分析报告。"
  : "尚未生成需求分析报告，请先执行需求分析。";
```

- [ ] **Step 10: Add the quality assurance tab**

After the analysis report tab, add:

```tsx
<TabsContent id="quality-assurance-section" value="quality">
  {analysisResult ? (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-lg border bg-card p-4">
          <div className="text-muted-foreground text-xs">质量门禁</div>
          <div className="mt-2 font-semibold text-lg">
            {qualityGate ? qualityResultLabels[qualityGate.result] : "-"}
          </div>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <div className="text-muted-foreground text-xs">可测试性评分</div>
          <div className="mt-2 font-semibold text-lg">{qualityGate?.testability_score ?? analysisResult.testability_score}</div>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <div className="text-muted-foreground text-xs">覆盖审计</div>
          <div className="mt-2 font-semibold text-lg">{coverageAudit.length}</div>
        </div>
      </div>

      {qualityAssuranceMarkdown.trim() ? (
        <MarkdownPreview className="requirement-document-preview" content={qualityAssuranceMarkdown} />
      ) : null}

      <div className="rounded-lg border bg-card p-4">
        <h3 className="font-medium text-sm">质量门禁</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <QualityIssueList items={qualityGate?.blocking_issues ?? []} title="阻塞问题" />
          <QualityIssueList items={qualityGate?.warning_issues ?? []} title="风险警告" />
          <QualityIssueList items={qualityGate?.passed_checks ?? []} title="已通过检查" />
        </div>
      </div>

      <div className="rounded-lg border bg-card p-4">
        <h3 className="font-medium text-sm">覆盖审计</h3>
        {coverageAudit.length ? (
          <div className="mt-3 overflow-hidden rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>模块</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>原因</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {coverageAudit.map((item) => (
                  <TableRow key={`${item.module_key}-${item.source_excerpt}`}>
                    <TableCell className="font-medium">{item.module_name}</TableCell>
                    <TableCell>{coverageStatusLabels[item.analysis_status] ?? item.analysis_status}</TableCell>
                    <TableCell className="text-muted-foreground">{item.reason}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <div className="mt-3 rounded-md border bg-muted/20 p-4 text-muted-foreground text-sm">暂无覆盖审计结果。</div>
        )}
      </div>
    </div>
  ) : (
    <div className="flex min-h-[280px] items-center justify-center rounded-lg border bg-muted/20 text-center text-muted-foreground text-sm">
      {reviewLoading ? "需求分析中，完成后会在这里展示质量保证结果。" : "尚未生成质量保证结果，请先执行需求分析。"}
    </div>
  )}
</TabsContent>
```

Add this helper near the bottom of the same file:

```tsx
function QualityIssueList({ items, title }: { items: string[]; title: string }) {
  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <div className="font-medium text-xs">{title}</div>
      {items.length ? (
        <ul className="mt-2 space-y-1 text-muted-foreground text-xs">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <div className="mt-2 text-muted-foreground text-xs">无</div>
      )}
    </div>
  );
}
```

- [ ] **Step 11: Run the frontend contract test**

Run:

```powershell
cd D:\project\test_project\apps\frontend
node --test tests/requirement-detail-analysis-contract.test.mjs
```

Expected: PASS.

---

### Task 4: Backend And Frontend Regression Verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused backend tests**

Run:

```powershell
cd D:\project\test_project\apps\backend
.\.venv\Scripts\python.exe -m pytest tests/test_requirement_analysis_agent.py tests/test_requirement_primary_file_service.py -q
```

Expected: PASS. These cover parser normalization, analysis serialization, and clarification answer writeback.

- [ ] **Step 2: Run focused frontend contract tests**

Run:

```powershell
cd D:\project\test_project\apps\frontend
node --test tests/requirement-detail-analysis-contract.test.mjs
```

Expected: PASS.

- [ ] **Step 3: Run frontend Biome check on touched files**

Run:

```powershell
cd D:\project\test_project\apps\frontend
npx biome check "src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx" "tests/requirement-detail-analysis-contract.test.mjs"
```

Expected: PASS with no formatting or lint errors.

- [ ] **Step 4: Manual UI smoke check**

Start the frontend if no dev server is running:

```powershell
cd D:\project\test_project\apps\frontend
npm run dev
```

Open a requirement detail page with an existing analysis result and verify:

- Top-level `需求分析` tab exists.
- Its sub tabs are exactly `需求分析`, `待澄清`, `质量保证`.
- `待澄清` shows clickable recommended options, custom answer textarea, `暂不处理`, and `保存答复`.
- Saving a clarification answer still writes back to the draft/finalization source via the existing backend endpoint.
- `质量保证` shows gate result, testability score, issue lists, and coverage audit.

---

## Self-Review

- Spec coverage:
  - Three sub tabs: Task 3.
  - Clarification Markdown converted to clickable structure: Task 1 parser plus Task 2 prompt/skill contract.
  - Quality assurance report view: Task 3 quality tab and Task 2 quality Markdown contract.
  - Existing answer interaction preserved: Task 3 Step 8 and contract test.
- Placeholder scan:
  - No `TBD`, `TODO`, or unspecified implementation placeholders remain.
- Type consistency:
  - Backend fields are `clarification_report_markdown` and `quality_assurance_report_markdown`.
  - Frontend type names match backend JSON keys.
  - Nested tab values are `analysis-report`, `clarification`, and `quality`.
