import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const projectPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/automation/api/page.tsx", import.meta.url),
  "utf8",
);

test("api asset field locations render at section headings instead of every row", () => {
  assert.match(projectPageSource, /const locations = Array\.from\(new Set\(rows\.map\(\(row\) => row\.location\)\)\);/);
  assert.match(projectPageSource, /locations\.map\(\(location\) => \(/);
  assert.match(projectPageSource, /md:grid-cols-\[minmax\(220px,1\.1fr\)_64px_56px_minmax\(220px,1\.4fr\)\]/);
  assert.doesNotMatch(projectPageSource, /<Badge className="w-fit" variant="secondary">\s*\{row\.location\}/);
  assert.match(
    projectPageSource,
    /<h3 className="font-semibold text-lg">响应信息<\/h3>[\s\S]*<Badge className="w-fit font-normal" variant="secondary">\s*response\s*<\/Badge>/,
  );
});
