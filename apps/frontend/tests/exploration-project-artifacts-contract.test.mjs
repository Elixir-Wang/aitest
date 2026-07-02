import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const workspaceSource = readFileSync(
  new URL("../src/components/ai-testing/exploration-workspace.tsx", import.meta.url),
  "utf8",
);
const pageExplorationApiSource = readFileSync(
  new URL("../../backend/app/api/v1/page_exploration.py", import.meta.url),
  "utf8",
);
const pageExplorationServiceSource = readFileSync(
  new URL("../../backend/app/services/exploration/page_exploration_service.py", import.meta.url),
  "utf8",
);

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
    /settings\.PROJECT_FILE_STORAGE_ROOT \/ project_id \/ "page_exploration" \/ "pages"/,
  );
  assert.doesNotMatch(pageExplorationServiceSource, /def _next_snapshot_page_id/);
});
