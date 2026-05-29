# Site Exploration YAML Source Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor site exploration so new runs use YAML artifacts as the only exploration fact source, with DB rows kept only as status/index/summary data.

**Architecture:** Add a focused artifact layer that writes and reads `run.yaml`, `summary.yaml`, `graph.yaml`, `blockers.yaml`, `logs/run.log`, and `pages/page-001-<slug>.yaml`. Update the Playwright runner to emit accessibility-first page facts without screenshots or HTML snapshots, and update backend/frontend detail APIs to read derived summaries from YAML artifacts. Old exploration artifact formats are not supported after this refactor.

**Tech Stack:** FastAPI, SQLite, Python services/tests, Node Playwright runner, Next.js App Router, React, shadcn/ui, Biome.

---

## File Map

- Create: `apps/backend/app/services/exploration_artifact_service.py`
  - Owns artifact paths, YAML serialization, slug generation, summary derivation, and `run.log` reads.
- Modify: `apps/backend/app/services/site_exploration_orchestrator.py`
  - Stops writing screenshots/HTML/Markdown as facts; persists YAML artifact package and DB indexes.
- Modify: `apps/backend/runners/playwright/site-explorer.mjs`
  - Emits accessibility-tree page facts, actions, edges, blockers, and log lines; no screenshots or HTML snapshots.
- Modify: `apps/backend/app/schemas/exploration.py`
  - Adds YAML-source detail fields needed by the frontend, without exposing screenshot/snapshot fields.
- Modify: `apps/backend/app/services/exploration_service.py`
  - Reads detail/report/log from YAML artifact package and `summary.yaml`.
- Modify: `apps/backend/app/presentation/serializers.py`
  - Keeps run serialization aligned with YAML fact source and existing run status actions.
- Modify: `apps/backend/app/seed/init_db.py`
  - Keeps existing tables as index tables; no `exploration_edges` table.
- Modify: `apps/backend/tests/test_site_exploration_orchestrator.py`
  - Replaces screenshot/snapshot expectations with YAML package expectations.
- Modify: `apps/backend/tests/test_exploration_service.py`
  - Covers detail/report/log behavior from YAML artifacts.
- Modify: `apps/backend/tests/test_exploration_artifact_service.py`
  - New focused tests for YAML writing/reading and summary derivation.
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
  - Uses `summary.yaml`-derived module progress and removes screenshot/snapshot assumptions.

## Task 1: Artifact Service

**Files:**
- Create: `apps/backend/app/services/exploration_artifact_service.py`
- Test: `apps/backend/tests/test_exploration_artifact_service.py`

- [ ] **Step 1: Write failing tests for artifact package creation**

Create `apps/backend/tests/test_exploration_artifact_service.py`:

```python
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from app.services import exploration_artifact_service as artifacts


class ExplorationArtifactServiceTest(unittest.TestCase):
    def test_write_artifact_package_creates_yaml_fact_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "projects" / "project-1" / "exploration" / "run-1"
            package = artifacts.ExplorationArtifactPackage(
                run={
                    "id": "run-1",
                    "project": "测试项目",
                    "environment": "测试环境",
                    "site_url": "https://example.test",
                    "scope": {"include": ["/users"], "exclude": ["/users/delete"]},
                    "goal": {"text": "探索用户管理"},
                    "limits": {"max_pages": 50, "max_actions": 1000, "timeout_minutes": 120},
                    "modules": {"source": "manual", "items": []},
                },
                pages=[
                    {
                        "page": {
                            "id": "page-001",
                            "title": "用户列表",
                            "url": "https://example.test/users",
                            "normalized_url": "https://example.test/users",
                            "module": "用户管理",
                            "page_type": "list",
                            "depth": 0,
                            "status": "explored",
                        },
                        "accessibility_tree": [{"role": "button", "name": "新建用户", "locator_hint": "getByRole('button', { name: '新建用户' })"}],
                        "actions": [{"id": "action-001", "role": "button", "name": "新建用户", "locator_hint": "getByRole('button', { name: '新建用户' })"}],
                        "relations": {"incoming_edges": [], "outgoing_edges": []},
                        "quality": {"confidence": "observed", "needs_confirmation": False, "blockers": []},
                    }
                ],
                graph={"nodes": [{"id": "page-001", "title": "用户列表", "url": "https://example.test/users", "type": "list", "module": "用户管理"}], "edges": []},
                blockers={"blockers": []},
                log_lines=["INFO run_started run-1", "INFO page_visited page-001"],
            )

            written = artifacts.write_artifact_package(root, package)

            self.assertTrue((root / "run.yaml").exists())
            self.assertTrue((root / "summary.yaml").exists())
            self.assertTrue((root / "graph.yaml").exists())
            self.assertTrue((root / "blockers.yaml").exists())
            self.assertTrue((root / "logs" / "run.log").exists())
            self.assertTrue((root / "pages" / "page-001-user-list.yaml").exists())
            self.assertEqual(written.page_paths, ["pages/page-001-user-list.yaml"])

            summary = yaml.safe_load((root / "summary.yaml").read_text(encoding="utf-8"))
            self.assertEqual(summary["run_id"], "run-1")
            self.assertEqual(summary["modules"][0]["module_name"], "用户管理")

    def test_slug_filename_removes_unsafe_characters(self):
        self.assertEqual(artifacts.page_filename("page-012", "用户/编辑:详情"), "page-012-user-edit-detail.yaml")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\project\test_project\apps\backend
python -m pytest tests/test_exploration_artifact_service.py -q
```

Expected: fails because `exploration_artifact_service` does not exist.

- [ ] **Step 3: Implement artifact service**

Create `apps/backend/app/services/exploration_artifact_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ExplorationArtifactPackage:
    run: dict[str, Any]
    pages: list[dict[str, Any]]
    graph: dict[str, Any]
    blockers: dict[str, Any]
    log_lines: list[str]


@dataclass(frozen=True)
class WrittenExplorationArtifacts:
    root: Path
    page_paths: list[str]
    run_path: str
    summary_path: str
    graph_path: str
    blockers_path: str
    log_path: str


def write_artifact_package(root: Path, package: ExplorationArtifactPackage) -> WrittenExplorationArtifacts:
    (root / "pages").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)

    _write_yaml(root / "run.yaml", package.run)
    _write_yaml(root / "graph.yaml", package.graph)
    _write_yaml(root / "blockers.yaml", package.blockers)
    page_paths = _write_pages(root, package.pages)
    _write_yaml(root / "summary.yaml", build_summary(package.run, package.pages, package.graph, package.blockers))
    (root / "logs" / "run.log").write_text("\n".join(package.log_lines).strip() + "\n", encoding="utf-8")

    return WrittenExplorationArtifacts(
        root=root,
        page_paths=page_paths,
        run_path="run.yaml",
        summary_path="summary.yaml",
        graph_path="graph.yaml",
        blockers_path="blockers.yaml",
        log_path="logs/run.log",
    )


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def read_log(root: Path) -> str:
    path = root / "logs" / "run.log"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def page_filename(page_id: str, title: str) -> str:
    slug = _slugify(title) or "page"
    return f"{page_id}-{slug}.yaml"


def build_summary(
    run: dict[str, Any],
    pages: list[dict[str, Any]],
    graph: dict[str, Any],
    blockers: dict[str, Any],
) -> dict[str, Any]:
    modules: dict[str, dict[str, Any]] = {}
    for page_doc in pages:
        page = page_doc.get("page", {})
        module_name = str(page.get("module") or "未分组模块")
        module = modules.setdefault(
            module_name,
            {
                "module_key": _slugify(module_name) or "ungrouped",
                "module_name": module_name,
                "status": "completed",
                "explored_pages": 0,
                "planned_pages": 0,
                "latest_page": "",
                "blocker_summary": "无",
                "progress_percent": 100,
            },
        )
        module["explored_pages"] += 1
        module["planned_pages"] = max(int(module["planned_pages"]), int(module["explored_pages"]))
        module["latest_page"] = str(page.get("title") or page.get("url") or module["latest_page"])

    blocker_items = blockers.get("blockers") if isinstance(blockers.get("blockers"), list) else []
    for blocker in blocker_items:
        module_name = str(blocker.get("module") or blocker.get("module_name") or "未分组模块")
        module = modules.setdefault(
            module_name,
            {
                "module_key": _slugify(module_name) or "ungrouped",
                "module_name": module_name,
                "status": "blocked",
                "explored_pages": 0,
                "planned_pages": 1,
                "latest_page": str(blocker.get("page") or ""),
                "blocker_summary": str(blocker.get("reason") or "存在阻塞"),
                "progress_percent": 0,
            },
        )
        module["status"] = "blocked" if blocker.get("severity") == "blocking" else "partial"
        module["blocker_summary"] = str(blocker.get("reason") or "存在阻塞")

    module_list = []
    for module in modules.values():
        explored = int(module["explored_pages"])
        planned = max(int(module["planned_pages"]), explored, 1)
        if module["status"] != "blocked":
            module["progress_percent"] = round((explored / planned) * 100)
        module["page_progress"] = f"{explored}/{planned}"
        module_list.append(module)

    edge_count = len(graph.get("edges") or [])
    return {
        "run_id": run.get("id", ""),
        "status": run.get("status", "completed"),
        "summary": f"已探索 {len(pages)} 个页面，记录 {edge_count} 条页面关系。",
        "modules": module_list,
    }


def _write_pages(root: Path, pages: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    for index, page_doc in enumerate(pages, start=1):
        page = page_doc.setdefault("page", {})
        page_id = str(page.get("id") or f"page-{index:03d}")
        page["id"] = page_id
        filename = page_filename(page_id, str(page.get("title") or page.get("url") or "page"))
        relative = f"pages/{filename}"
        _write_yaml(root / relative, page_doc)
        paths.append(relative)
    return paths


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _slugify(value: str) -> str:
    text = value.strip().lower()
    replacements = {
        "用户": "user",
        "列表": "list",
        "详情": "detail",
        "编辑": "edit",
        "新建": "create",
        "角色": "role",
        "权限": "permission",
        "首页": "home",
    }
    for source, target in replacements.items():
        text = text.replace(source, f" {target} ")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:80]
```

- [ ] **Step 4: Add PyYAML dependency if missing**

Run:

```powershell
cd D:\project\test_project\apps\backend
python - <<'PY'
import yaml
print(yaml.__version__)
PY
```

Expected: prints a version. If it fails, add `PyYAML` to the backend dependency file used by this repo, then rerun the command.

- [ ] **Step 5: Verify artifact service tests pass**

Run:

```powershell
cd D:\project\test_project\apps\backend
python -m pytest tests/test_exploration_artifact_service.py -q
```

Expected: PASS.

## Task 2: Runner Output Contract

**Files:**
- Modify: `apps/backend/runners/playwright/site-explorer.mjs`
- Test: existing orchestrator tests will consume the new runner contract through mocked output.

- [ ] **Step 1: Change runner directories**

Remove `screenshots` and `snapshots` directories from `dirs`. Keep only `logs` if needed by future local debugging, but the runner should return log lines in JSON output.

Replace:

```js
const dirs = {
  screenshots: path.join(artifactRoot, "screenshots"),
  snapshots: path.join(artifactRoot, "snapshots"),
};
```

With:

```js
const dirs = {};
```

- [ ] **Step 2: Replace DOM-only facts with accessibility-first facts**

Add a function:

```js
async function collectAccessibilityFacts() {
  const snapshot = await page.accessibility.snapshot({ interestingOnly: false }).catch(() => null);
  const domFacts = await collectDomFacts();
  const nodes = flattenAccessibility(snapshot).slice(0, 300);
  const actionable = nodes
    .filter((node) => ["button", "link", "textbox", "combobox", "checkbox", "radio", "tab", "menuitem"].includes(node.role))
    .map((node, index) => ({
      id: `action-${String(index + 1).padStart(3, "0")}`,
      role: node.role,
      name: node.name || "",
      locator_hint: locatorHint(node.role, node.name),
      action_type: node.role === "textbox" ? "fill" : "click",
      enabled: !node.disabled,
      visible: true,
    }));
  return {
    title: documentTitleFromNodes(nodes) || domFacts.title,
    url: page.url(),
    accessibility_tree: nodes.map((node) => ({
      role: node.role,
      name: node.name || "",
      locator_hint: locatorHint(node.role, node.name),
      enabled: !node.disabled,
      visible: true,
      source: node.source || "accessibility",
    })),
    actions: actionable.length ? actionable : domFacts.actions,
    links: domFacts.links,
  };
}
```

Also add helper functions in the same file:

```js
function flattenAccessibility(node, output = []) {
  if (!node) return output;
  output.push({
    role: node.role || "generic",
    name: node.name || "",
    disabled: Boolean(node.disabled),
    source: "accessibility",
  });
  for (const child of node.children || []) flattenAccessibility(child, output);
  return output;
}

function locatorHint(role, name) {
  if (!role || !name) return "";
  return `getByRole('${role}', { name: ${JSON.stringify(name)} })`;
}

function documentTitleFromNodes(nodes) {
  const heading = nodes.find((node) => node.role === "heading" && node.name);
  return heading?.name || "";
}
```

- [ ] **Step 3: Keep DOM fallback without saving HTML**

Rename current `collectFacts` to `collectDomFacts` and return only actions/links:

```js
async function collectDomFacts() {
  return page.evaluate(() => {
    const visible = (el) => {
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
    };
    const labelOf = (el) => {
      const aria = el.getAttribute("aria-label");
      const title = el.getAttribute("title");
      const placeholder = el.getAttribute("placeholder");
      const text = el.innerText || el.textContent;
      const value = el.getAttribute("value");
      return (aria || title || placeholder || text || value || el.name || el.id || el.tagName).trim().replace(/\s+/g, " ").slice(0, 120);
    };
    const elements = Array.from(document.querySelectorAll("a,button,input,textarea,select,[role='button'],[role='link'],[role='tab'],[role='menuitem']"))
      .filter(visible)
      .slice(0, 120)
      .map((el, index) => {
        const role = el.tagName.toLowerCase() === "a" ? "link" : (el.getAttribute("role") || el.tagName.toLowerCase());
        const name = labelOf(el);
        return {
          index,
          role,
          name,
          action_type: ["input", "textarea"].includes(el.tagName.toLowerCase()) ? "fill" : "click",
          locator_hint: role && name ? `getByRole('${role}', { name: ${JSON.stringify(name)} })` : "",
          href: el.href || "",
          source: "dom_fallback",
        };
      });
    return {
      title: document.title || location.pathname || location.href,
      actions: elements.filter((item) => item.role !== "link" || !item.href),
      links: elements.filter((item) => item.href),
    };
  });
}
```

- [ ] **Step 4: Emit new JSON payload**

At completion, `console.log(JSON.stringify(...))` should include:

```js
{
  status,
  summary,
  pages,
  graph: { nodes, edges, paths },
  blockers,
  log_lines,
  action_count,
  field_count,
  state_transition_count,
  discovery
}
```

Do not include `screenshot_path` or `snapshot_path`.

- [ ] **Step 5: Verify runner has no screenshot/snapshot writes**

Run:

```powershell
cd D:\project\test_project
rg -n "screenshot|snapshot|page\\.content|screenshots|snapshots" apps\backend\runners\playwright\site-explorer.mjs
```

Expected: no matches except `accessibility.snapshot`.

## Task 3: Orchestrator Writes YAML Fact Package

**Files:**
- Modify: `apps/backend/app/services/site_exploration_orchestrator.py`
- Modify: `apps/backend/tests/test_site_exploration_orchestrator.py`

- [ ] **Step 1: Update completed-result test expectations**

In `test_run_exploration_records_completed_result_with_pages_and_elements`, remove screenshot/snapshot fake writes and expect YAML files:

```python
def fake_run_site_explorer(_page_url: str, target_root: Path, _forbidden_paths: str = "") -> dict:
    return {
        "status": "completed",
        "summary": "已探索 1 个页面，识别 2 个可交互元素，记录 0 个阻塞项。",
        "log": "INFO run_started explore-1\nINFO page_visited page-001\n",
        "pages": [
            {
                "page": {
                    "id": "page-001",
                    "title": "用户管理",
                    "url": "https://example.test/users",
                    "normalized_url": "https://example.test/users",
                    "module": "用户管理",
                    "page_type": "list",
                    "depth": 0,
                    "status": "explored",
                },
                "accessibility_tree": [{"role": "button", "name": "新增用户", "locator_hint": "getByRole('button', { name: '新增用户' })"}],
                "actions": [{"id": "action-001", "role": "button", "name": "新增用户", "locator_hint": "getByRole('button', { name: '新增用户' })"}],
                "relations": {"incoming_edges": [], "outgoing_edges": []},
                "quality": {"confidence": "observed", "needs_confirmation": False, "blockers": []},
            }
        ],
        "graph": {"nodes": [{"id": "page-001", "title": "用户管理", "url": "https://example.test/users", "type": "list", "module": "用户管理"}], "edges": [], "paths": []},
        "blockers": [],
        "action_count": 1,
        "field_count": 1,
        "state_transition_count": 0,
    }
```

Assert:

```python
artifact_root = Path(temp_dir) / "projects" / "project-1" / "exploration" / "explore-1"
self.assertTrue((artifact_root / "run.yaml").exists())
self.assertTrue((artifact_root / "summary.yaml").exists())
self.assertTrue((artifact_root / "graph.yaml").exists())
self.assertTrue((artifact_root / "blockers.yaml").exists())
self.assertTrue((artifact_root / "pages" / "page-001-user-management.yaml").exists())
self.assertFalse((artifact_root / "screenshots").exists())
self.assertFalse((artifact_root / "snapshots").exists())
```

- [ ] **Step 2: Run updated orchestrator test to verify failure**

Run:

```powershell
cd D:\project\test_project\apps\backend
python -m pytest tests/test_site_exploration_orchestrator.py::SiteExplorationOrchestratorTest::test_run_exploration_records_completed_result_with_pages_and_elements -q
```

Expected: fails because orchestrator still expects old payload and writes screenshot artifacts.

- [ ] **Step 3: Stop creating obsolete artifact directories**

In `_ensure_artifact_dirs`, replace:

```python
for name in ("storage", "traces", "screenshots", "snapshots", "videos", "documents", "outputs", "logs"):
```

With:

```python
for name in ("pages", "logs"):
```

- [ ] **Step 4: Build run.yaml input from DB run**

Add helper in `site_exploration_orchestrator.py`:

```python
def _run_yaml(run) -> dict:
    return {
        "run": {
            "id": run["id"],
            "project": run["project_name"],
            "environment": run["environment_name"],
            "site_url": _safe_site_url(run),
            "status": run["status"],
            "started_at": str(run["started_at"] or ""),
        },
        "scope": _scope_yaml(run),
        "goal": {"text": str(run["description"] or "")},
        "modules": _modules_yaml(run),
        "limits": {
            "max_pages": int(run["max_pages"] or 50),
            "max_actions": int(run["max_actions"] or 1000),
            "timeout_minutes": int(run["timeout_minutes"] or 120),
        },
    }
```

Add:

```python
def _scope_yaml(run) -> dict:
    return {
        "include": [line.strip() for line in str(run["scope"] or "").splitlines() if line.strip()],
        "exclude": [line.strip() for line in str(run["forbidden_paths"] or "").splitlines() if line.strip()],
    }


def _modules_yaml(run) -> dict:
    return {"source": "scope", "items": []}
```

- [ ] **Step 5: Use artifact service in completed and blocked persistence**

Import:

```python
from app.services import exploration_artifact_service
```

In `_persist_completed_result`, build:

```python
package = exploration_artifact_service.ExplorationArtifactPackage(
    run=_run_yaml(run),
    pages=_result_page_docs(result, run),
    graph=result.get("graph") or _graph_from_pages(result, run),
    blockers={"blockers": _result_blockers(result, run)},
    log_lines=str(result.get("log") or "").splitlines() or ["INFO run_completed"],
)
written = exploration_artifact_service.write_artifact_package(artifact_root, package)
```

Then create DB index rows from `package.pages`, `package.graph`, and `package.blockers`. Do not create screenshot artifact rows.

- [ ] **Step 6: Implement page/blocker normalization helpers**

Add:

```python
def _result_page_docs(result: dict, run) -> list[dict]:
    page_docs = result.get("pages") or []
    normalized = []
    for index, page_doc in enumerate(page_docs, start=1):
        if "page" in page_doc:
            normalized.append(page_doc)
            continue
        page_id = f"page-{index:03d}"
        normalized.append(
            {
                "page": {
                    "id": page_id,
                    "title": str(page_doc.get("title") or page_doc.get("url") or "未命名页面"),
                    "url": str(page_doc.get("url") or ""),
                    "normalized_url": str(page_doc.get("normalized_url") or page_doc.get("url") or ""),
                    "module": _module_name(run),
                    "page_type": str(page_doc.get("page_type") or "unknown"),
                    "depth": int(page_doc.get("depth") or 0),
                    "status": "explored",
                },
                "accessibility_tree": page_doc.get("accessibility_tree") or [],
                "actions": page_doc.get("actions") or [],
                "relations": page_doc.get("relations") or {"incoming_edges": [], "outgoing_edges": []},
                "quality": page_doc.get("quality") or {"confidence": "observed", "needs_confirmation": False, "blockers": []},
            }
        )
    return normalized
```

Add `_result_blockers` returning blocker dictionaries with `id`, `type`, `page`, `reason`, `severity`, `suggested_action`.

- [ ] **Step 7: Update DB artifact rows**

`_persist_common_artifacts` should create only:

```python
("yaml", store_path(artifact_root / "run.yaml") or "", "探索运行配置"),
("yaml", store_path(artifact_root / "summary.yaml") or "", "探索概览摘要"),
("yaml", store_path(artifact_root / "graph.yaml") or "", "探索页面关系"),
("yaml", store_path(artifact_root / "blockers.yaml") or "", "探索阻塞清单"),
("log", store_path(artifact_root / "logs" / "run.log") or "", "探索执行日志"),
```

Do not create `document`, `json`, `screenshot`, `snapshot`, `trace`, or `video` artifact rows.

- [ ] **Step 8: Run orchestrator tests**

Run:

```powershell
cd D:\project\test_project\apps\backend
python -m pytest tests/test_site_exploration_orchestrator.py -q
```

Expected: PASS after updating all old screenshot/snapshot assertions to YAML assertions.

## Task 4: Service/API Reads YAML Source

**Files:**
- Modify: `apps/backend/app/schemas/exploration.py`
- Modify: `apps/backend/app/services/exploration_service.py`
- Modify: `apps/backend/tests/test_exploration_service.py`

- [ ] **Step 1: Update schemas to remove screenshot/snapshot from public page model**

In `ExplorationPageOut`, remove:

```python
screenshot_path: str = ""
snapshot_path: str = ""
trace_path: str = ""
```

Add:

```python
yaml_path: str = ""
page_type: str = "unknown"
status: str = "explored"
```

- [ ] **Step 2: Add detail test for summary.yaml**

In `test_exploration_service.py`, add a test that writes a minimal YAML package using `exploration_artifact_service.write_artifact_package`, updates `exploration_runs.artifact_root`, then calls `get_project_run_detail`. Assert `modules[0]["module_name"]`, `explored_page_count`, and page `yaml_path`.

- [ ] **Step 3: Implement detail read fallback removal**

In `exploration_service.get_project_run_detail`, when `artifact_root` is present:

```python
artifact_root = PROJECT_FILE_STORAGE_ROOT / run["project_id"] / "exploration" / run_id
summary = exploration_artifact_service.read_yaml(artifact_root / "summary.yaml")
```

Build modules from `summary["modules"]`. Do not synthesize old plan modules for missing outputs after this refactor; missing YAML should return an empty module list plus `result_summary` explaining artifacts are missing.

- [ ] **Step 4: Update report generation**

`get_project_run_report` should generate Markdown from YAML files:

```markdown
# {run.title} 探索报告

## 摘要
{summary.summary}

## 模块覆盖
| 模块 | 状态 | 页面进度 | 最近页面 | 阻塞 |
...
```

Do not read `exploration_document_versions` as the fact source.

- [ ] **Step 5: Update log endpoint**

`get_project_run_log` should read only `logs/run.log` through `exploration_artifact_service.read_log(root)`.

- [ ] **Step 6: Run backend service tests**

Run:

```powershell
cd D:\project\test_project\apps\backend
python -m pytest tests/test_exploration_service.py tests/test_exploration_artifact_service.py -q
```

Expected: PASS.

## Task 5: Frontend Exploration Detail

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

- [ ] **Step 1: Update frontend types**

In `ExplorationRunDetail["modules"][number]["pages"][number]`, add:

```ts
yaml_path: string;
page_type: string;
status: string;
```

Remove any assumptions around `screenshot_path` and `snapshot_path`.

- [ ] **Step 2: Keep four tabs and update module progress content only**

Keep tab order:

```ts
tabs={["探索计划", "探索概览", "探索日志", "探索报告"]}
```

In the `探索模块进度` heading description, change:

```tsx
<p className="text-muted-foreground text-xs">展示当前模块、子页面、元素和阻塞项探索状态</p>
```

To:

```tsx
<p className="text-muted-foreground text-xs">按探索计划展示模块页面进度、最近页面和阻塞说明</p>
```

- [ ] **Step 3: Remove element-heavy subtasks from module progress**

In `toPlanTasks`, remove `elementSubtasks` from `subtasks`. Module progress should show pages and blockers, not element lists.

Use:

```ts
subtasks: [...pageSubtasks, ...blockerSubtasks, ...pendingSubtask],
```

- [ ] **Step 4: Update page subtask meta to point to YAML**

For page subtasks:

```ts
meta: [page.page_type, page.yaml_path || page.url || page.entry_path].filter(Boolean),
```

- [ ] **Step 5: Verify frontend check**

Run:

```powershell
cd D:\project\test_project\apps\frontend
npm run check -- 'src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx'
```

Expected: PASS.

## Task 6: Full Verification

**Files:**
- No new files unless previous tasks reveal missing tests.

- [ ] **Step 1: Search for forbidden artifact writes**

Run:

```powershell
cd D:\project\test_project
rg -n "screenshots|snapshots|screenshot_path|snapshot_path|trace_path|video|page\\.screenshot|page\\.content" apps\backend apps\frontend
```

Expected: no matches in active exploration code, except historical docs/tests intentionally updated or unrelated generic strings.

- [ ] **Step 2: Run backend exploration tests**

Run:

```powershell
cd D:\project\test_project\apps\backend
python -m pytest tests/test_exploration_artifact_service.py tests/test_site_exploration_orchestrator.py tests/test_exploration_service.py -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend check**

Run:

```powershell
cd D:\project\test_project\apps\frontend
npm run check -- 'src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx'
```

Expected: PASS.

- [ ] **Step 4: Manual smoke run**

Start backend/frontend using the repo’s normal commands, create a new exploration run, start it, and verify the artifact directory contains:

```text
run.yaml
summary.yaml
graph.yaml
blockers.yaml
logs/run.log
pages/page-001-<slug>.yaml
```

Verify it does not contain:

```text
screenshots/
snapshots/
traces/
videos/
documents/exploration-v1.md
outputs/result.json
```

## Self-Review Notes

- Spec coverage: YAML fact source, no screenshots/HTML, no `events.jsonl`, no `locators.yaml`, no `exploration_edges`, `summary.yaml`, page slug names, log-only logging, modal/tab as in-page edges, and DB-as-index are covered.
- Execution risk: runner accessibility snapshot support and locator hint quality are the highest-risk areas; Task 2 keeps DOM fallback to reduce blank pages.
- Scope control: this plan intentionally does not add graph visualization or downstream test-case generation implementation.
