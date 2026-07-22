import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const projectPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/automation/api/page.tsx", import.meta.url),
  "utf8",
);

test("endpoint schema rows display imported field examples only when defined", () => {
  assert.match(projectPageSource, /example: formatSchemaExample\(propertySchema\.example\)/);
  assert.match(projectPageSource, /row\.example !== undefined/);
  assert.match(projectPageSource, /示例：[\s\S]*\{row\.example\}/);
  assert.match(projectPageSource, /function formatSchemaExample/);
  assert.match(projectPageSource, /JSON\.stringify\(value\)/);
  assert.match(
    projectPageSource,
    /formatSchemaExample\("example" in parameter \? parameter\.example : schema\.example\)/,
  );
});
