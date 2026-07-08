import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const workspaceSource = readFileSync(
  new URL("../src/components/ai-testing/exploration-workspace.tsx", import.meta.url),
  "utf8",
);
const pageExplorationApiSource = readFileSync(
  new URL("../../backend/app/api/v1/page_exploration/pages.py", import.meta.url),
  "utf8",
);
const pageExplorationServiceSource = [
  "../../backend/app/services/page_exploration/service.py",
  "../../backend/app/services/page_exploration/output_registry.py",
]
  .map((path) => readFileSync(new URL(path, import.meta.url), "utf8"))
  .join("\n");

test("exploration artifacts tab reads project-level page artifacts directly", () => {
  assert.match(workspaceSource, /\/page-exploration\/projects\/\$\{project\.project_id\}\/pages/);
  assert.doesNotMatch(workspaceSource, /\/page-exploration\/artifacts\$\{queryString/);
  assert.doesNotMatch(workspaceSource, /\/page-exploration\/runs\/\$\{project\.latest_run_id\}\/pages/);
});

test("backend exposes project-level page artifact listing", () => {
  assert.match(pageExplorationApiSource, /@router\.get\("\/projects\/\{project_id\}\/pages"/);
  assert.match(pageExplorationApiSource, /list_project_pages/);
  assert.match(pageExplorationServiceSource, /ProjectPagesService/);
  assert.match(pageExplorationServiceSource, /def list_project_pages/);
});

test("snapshot checkpoints write project-level page artifacts", () => {
  assert.match(
    pageExplorationServiceSource,
    /base_dir = .* \/ project_id \/ "page_exploration"[\s\S]*pages_dir = base_dir \/ "pages"/,
  );
  assert.doesNotMatch(pageExplorationServiceSource, /def _next_snapshot_page_id/);
});
