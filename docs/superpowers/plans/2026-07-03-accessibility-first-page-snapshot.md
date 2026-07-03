# Accessibility-First Page Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make page exploration snapshots show current page and popover content through a compact accessibility tree, while keeping existing verified `elements` for executable actions.

**Architecture:** Browser snapshots become semantic snapshots: `accessibility_tree` is the primary model-readable page state, `visible_text_blocks` is the compact text fallback, and `elements` remains the high-confidence executable target list. The old `raw_output` field is removed from the public snapshot contract because it is ambiguous debug text and is already treated as unsafe for timeline display.

**Tech Stack:** Playwright Node runner, Python Pydantic schemas/tools, page artifact persistence, pytest, and Node test runner.

---

## File Structure

- Modify: `apps/backend/runners/playwright/browser-session.mjs`
  - Add compact accessibility snapshot collection to `observePage()`.
  - Add visible text block extraction with token-safe limits.
  - Keep existing `elements` extraction as the executable target list.
- Modify: `apps/backend/runners/playwright/browser-session.test.mjs`
  - Add regression for popover content represented in `accessibility_tree` and `visible_text_blocks`.
- Modify: `apps/backend/app/agents/page_exploration/playwright/schemas.py`
  - Add `AccessibilityNodeInfo`.
  - Add `accessibility_tree` and `visible_text_blocks` to `SnapshotResult`.
  - Remove `raw_output` from the public snapshot schema.
- Modify: `apps/backend/app/agents/page_exploration/tools/runtime_context.py`
  - Map Node `accessibility_tree` and `visible_text_blocks` into `SnapshotResult`.
  - Stop mapping `raw_output`.
- Modify: `apps/backend/app/agents/page_exploration/tools/extraction_tools.py`
  - Return `accessibility_tree` and `visible_text_blocks`.
  - Remove `raw_output` from return payload and docs.
- Modify: `apps/backend/app/services/exploration/page_exploration_service.py`
  - Persist `accessibility_tree` and `visible_text_blocks` into page YAML.
  - Remove `states[].raw_output` from checkpoint YAML.
- Modify tests:
  - `apps/backend/tests/agents/page_exploration/tools/test_extraction_tools.py`
  - `apps/backend/tests/test_page_exploration_artifact_snapshot.py`

---

### Task 1: Browser Session Semantic Snapshot

**Files:**
- Modify: `apps/backend/runners/playwright/browser-session.mjs`
- Test: `apps/backend/runners/playwright/browser-session.test.mjs`

- [ ] **Step 1: Write failing Node regression for popover semantic visibility**

Add a test that renders a `创建` button plus a visible popover containing plain `div` options: `创建智能体`, `自主规划 Agent`, `Multi-Agent`, `写作 Agent`, and `任务流 Agent`. Assert `observe` returns those labels in `accessibility_tree` and `visible_text_blocks`.

Run:

```powershell
node --test browser-session.test.mjs
```

Expected: fail because `accessibility_tree` and `visible_text_blocks` are not returned yet.

- [ ] **Step 2: Add accessibility collection**

In `browser-session.mjs`, add helpers:

```js
async function collectAccessibilityTree(browserPage) {
  const snapshot = await browserPage.accessibility?.snapshot?.({ interestingOnly: false }).catch(() => null) || null;
  return flattenAccessibility(snapshot).slice(0, 500);
}

function flattenAccessibility(node, path = "ax", output = []) {
  if (!node || typeof node !== "object") return output;
  const name = cleanText(node.name, 100);
  const role = cleanText(node.role, 40);
  const children = Array.isArray(node.children) ? node.children : [];
  if (name || role) {
    output.push({
      id: path,
      role,
      name,
      level: Number.isFinite(node.level) ? node.level : null,
      checked: typeof node.checked === "boolean" ? node.checked : null,
      disabled: typeof node.disabled === "boolean" ? node.disabled : null,
      expanded: typeof node.expanded === "boolean" ? node.expanded : null,
    });
  }
  for (const [index, child] of children.entries()) {
    if (output.length >= 500) break;
    flattenAccessibility(child, `${path}-${index + 1}`, output);
  }
  return output;
}

function cleanText(value, limit = 160) {
  return String(value || "").trim().replace(/\s+/g, " ").slice(0, limit);
}
```

- [ ] **Step 3: Add visible text blocks**

Add:

```js
async function collectVisibleTextBlocks(browserPage) {
  return browserPage.evaluate(() => {
    const clean = (value, limit = 120) => String(value || "").trim().replace(/\s+/g, " ").slice(0, limit);
    const visible = (el) => {
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
    };
    const seen = new Set();
    const blocks = [];
    for (const el of Array.from(document.body?.querySelectorAll("h1,h2,h3,h4,h5,h6,button,label,input,textarea,select,[role],p,span,strong,b,li") || [])) {
      if (!visible(el)) continue;
      const text = clean(el.innerText || el.getAttribute("aria-label") || el.getAttribute("placeholder") || el.textContent);
      if (!text || seen.has(text)) continue;
      seen.add(text);
      blocks.push(text);
      if (blocks.length >= 200) break;
    }
    return blocks;
  }).catch(() => []);
}
```

- [ ] **Step 4: Return new fields from `observePage()`**

In `observePage()`, collect and return:

```js
const accessibilityTree = await collectAccessibilityTree(page);
const visibleTextBlocks = await collectVisibleTextBlocks(page);
```

and include:

```js
accessibility_tree: accessibilityTree,
visible_text_blocks: visibleTextBlocks,
```

- [ ] **Step 5: Run Node verification**

Run:

```powershell
node --test browser-session.test.mjs
```

Expected: pass.

---

### Task 2: Snapshot Tool Contract Cleanup

**Files:**
- Modify: `apps/backend/app/agents/page_exploration/playwright/schemas.py`
- Modify: `apps/backend/app/agents/page_exploration/tools/runtime_context.py`
- Modify: `apps/backend/app/agents/page_exploration/tools/extraction_tools.py`
- Test: `apps/backend/tests/agents/page_exploration/tools/test_extraction_tools.py`

- [ ] **Step 1: Update tests first**

Update fakes to return:

```python
{
    "url": "https://test.com/authed",
    "title": "Authed",
    "elements": [{"id": "button-save", "role": "button", "name": "Save", "visible": True}],
    "accessibility_tree": [{"id": "ax-1", "role": "button", "name": "Save"}],
    "visible_text_blocks": ["Save"],
}
```

Assert:

```python
assert result["accessibility_tree"][0]["name"] == "Save"
assert result["visible_text_blocks"] == ["Save"]
assert "raw_output" not in result
```

Run:

```powershell
uv run pytest tests\agents\page_exploration\tools\test_extraction_tools.py -q
```

Expected: fail until schema/tool mapping is updated.

- [ ] **Step 2: Update schemas**

Add:

```python
class AccessibilityNodeInfo(BaseModel):
    """Compact accessibility node for model-readable page state."""

    id: str = ""
    role: str = ""
    name: str = ""
    level: int | None = None
    checked: bool | None = None
    disabled: bool | None = None
    expanded: bool | None = None
```

Change `SnapshotResult` to:

```python
class SnapshotResult(BaseModel):
    """Result from a browser page snapshot."""

    url: str
    title: str
    elements: list[ElementInfo]
    accessibility_tree: list[AccessibilityNodeInfo] = []
    visible_text_blocks: list[str] = []
    error: str | None = None
```

Remove `raw_output`.

- [ ] **Step 3: Update runtime mapping**

Map `accessibility_tree` and `visible_text_blocks` in `snapshot_with_runtime_context()`. Do not read `text` or `raw_output` into `SnapshotResult`.

- [ ] **Step 4: Update tool output**

Return:

```python
{
    "url": result.url,
    "title": result.title,
    "elements": [...],
    "accessibility_tree": [node.model_dump() for node in result.accessibility_tree],
    "visible_text_blocks": result.visible_text_blocks,
    "error": result.error,
}
```

Remove `raw_output` from the docstring and return payload.

- [ ] **Step 5: Run Python verification**

Run:

```powershell
uv run pytest tests\agents\page_exploration\tools\test_extraction_tools.py -q
```

Expected: pass.

---

### Task 3: Persist Semantic Snapshot Into YAML

**Files:**
- Modify: `apps/backend/app/services/exploration/page_exploration_service.py`
- Test: `apps/backend/tests/test_page_exploration_artifact_snapshot.py`

- [ ] **Step 1: Update artifact test fixture**

In the snapshot fixture, replace `raw_output` with:

```python
"accessibility_tree": [
    {"id": "ax-1", "role": "button", "name": "创建智能体"},
    {"id": "ax-2", "role": "text", "name": "自主规划 Agent"},
    {"id": "ax-3", "role": "text", "name": "Multi-Agent"},
],
"visible_text_blocks": ["创建智能体", "自主规划 Agent", "Multi-Agent"],
```

Assert generated YAML includes:

```python
assert data["page"]["accessibility_tree"][1]["name"] == "自主规划 Agent"
assert "Multi-Agent" in data["page"]["visible_text_blocks"]
assert "raw_output" not in data["states"][0]
```

- [ ] **Step 2: Run failing artifact test**

Run:

```powershell
uv run pytest tests\test_page_exploration_artifact_snapshot.py::test_invoke_agent_checkpoints_snapshot_as_page_artifact -q
```

Expected: fail until YAML writer is updated.

- [ ] **Step 3: Update checkpoint writer**

In `_checkpoint_snapshot_artifact_from_event()`, read:

```python
accessibility_tree = snapshot.get("accessibility_tree") if isinstance(snapshot.get("accessibility_tree"), list) else []
visible_text_blocks = snapshot.get("visible_text_blocks") if isinstance(snapshot.get("visible_text_blocks"), list) else []
```

Add both fields under `artifact["page"]` and `states[0]`.

Remove:

```python
"raw_output": _string(snapshot.get("raw_output")),
```

- [ ] **Step 4: Run artifact verification**

Run:

```powershell
uv run pytest tests\test_page_exploration_artifact_snapshot.py::test_invoke_agent_checkpoints_snapshot_as_page_artifact -q
```

Expected: pass.

---

### Task 4: Cleanup Verification

**Files:**
- Modify only stale references exposed by tests.

- [ ] **Step 1: Search stale snapshot raw output references**

Run:

```powershell
rg -n "raw_output" apps\backend\app\agents\page_exploration apps\backend\app\services\exploration apps\backend\tests\agents\page_exploration apps\backend\tests\test_page_exploration_artifact_snapshot.py
```

Expected: snapshot tool and checkpoint YAML do not expose `raw_output`. Timeline sanitization tests may still mention it as a forbidden debug key.

- [ ] **Step 2: Run focused backend tests**

Run:

```powershell
uv run pytest tests\agents\page_exploration\tools\test_extraction_tools.py tests\test_page_exploration_artifact_snapshot.py -q
```

Expected: pass.

- [ ] **Step 3: Run Node runner tests**

Run:

```powershell
node --test browser-session.test.mjs
```

Expected: pass.

---

## Self-Review

**Spec coverage:** Covers accessibility tree as default model-readable snapshot, keeps `elements`, adds visible text fallback, avoids full DOM/styles, and removes `raw_output` from the public snapshot contract.

**Placeholder scan:** No TBD or open-ended implementation placeholders remain.

**Type consistency:** Node fields are `accessibility_tree` and `visible_text_blocks`; Python schema, tool return, and YAML writer use the same names.

