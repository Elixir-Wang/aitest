import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const detailPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/automation/api/cases/[caseId]/page.tsx", import.meta.url),
  "utf8",
);
const listPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/automation/api/page.tsx", import.meta.url),
  "utf8",
);
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const apiTestCaseTypeSource = apiClientSource.match(/export type ApiAutomationTestCase = \{[\s\S]*?\n\};/)?.[0];

test("api automation case detail removes the generated-source tag", () => {
  assert.doesNotMatch(detailPageSource, /testCase\.source/);
  assert.doesNotMatch(detailPageSource, /AI 生成/);
  assert.ok(apiTestCaseTypeSource);
  assert.doesNotMatch(apiTestCaseTypeSource, /source: string;/);
  assert.doesNotMatch(listPageSource, /testCase\.source/);
});

test("api automation case title shares the tag row", () => {
  assert.match(
    detailPageSource,
    /<div className="flex min-w-0 flex-wrap items-center gap-2">[\s\S]*?<h1[^>]*>\{testCase\.title\}<\/h1>[\s\S]*?<Badge/,
  );
});

test("api automation case detail names JSON field type assertions", () => {
  assert.match(detailPageSource, /jsonpath_type: "校验 JSON 字段类型"/);
  assert.match(detailPageSource, /\$\{path\} 类型 = \$\{expected\}/);
});
