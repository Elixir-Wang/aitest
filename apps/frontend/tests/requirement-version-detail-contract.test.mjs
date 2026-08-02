import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(
  new URL(
    "../src/app/(main)/projects/[projectId]/requirements/[documentId]/versions/[versionId]/page.tsx",
    import.meta.url,
  ),
  "utf8",
);

test("requirement version detail back action returns to the requirement overview version tab", () => {
  assert.match(
    pageSource,
    /const versionHistoryTabPath = `\/projects\/\$\{projectId\}\/requirements\/\$\{documentId\}\?tab=versions`/,
  );
  assert.match(pageSource, /router\.push\(versionHistoryTabPath\)/);
  assert.doesNotMatch(pageSource, /\/requirements\/\$\{documentId\}\/versions`/);
  assert.doesNotMatch(pageSource, /router\.back\(\)/);
});

test("requirement version breadcrumb uses the loaded document name without fallback", () => {
  assert.match(pageSource, /\.\.\.\(documentName \? \[\{ label: documentName, href:/);
  assert.match(pageSource, /moduleBreadcrumbs\(\s*"requirements"/);
  assert.doesNotMatch(pageSource, /\{ label: documentName \|\| "需求文档"/);
});
