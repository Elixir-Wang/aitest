import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const frontendRoot = path.resolve(import.meta.dirname, "..");
const orchestrationSelectPath = path.join(
  frontendRoot,
  "src/components/ai-testing/api-automation/api-orchestration-select.tsx",
);
const orchestrationFiles = [
  "src/app/(main)/projects/[projectId]/automation/api/page.tsx",
  "src/components/ai-testing/api-automation/api-scenario-ai-review-field.tsx",
  "src/components/ai-testing/api-automation/api-scenario-editor.tsx",
  "src/components/ai-testing/api-automation/api-scenario-step-config.tsx",
];

test("interface orchestration uses one role-style select entry", () => {
  for (const relativePath of orchestrationFiles) {
    const source = fs.readFileSync(path.join(frontendRoot, relativePath), "utf8");
    assert.doesNotMatch(source, /@\/components\/ui\/select/);
    assert.match(source, /api-orchestration-select/);
  }
});

test("orchestration select preserves Radix behavior with role dropdown styling", () => {
  const source = fs.readFileSync(orchestrationSelectPath, "utf8");
  assert.match(source, /from "@\/components\/ui\/select"/);
  assert.match(source, /h-8 w-full min-w-44/);
  assert.match(source, /rounded-lg/);
  assert.match(source, /hover:bg-muted/);
  assert.match(source, /z-\[100\]/);
  assert.match(source, /sideOffset = 8/);
  assert.match(source, /sideOffset=\{sideOffset\}/);
  assert.match(source, /py-0\.5/);
});
