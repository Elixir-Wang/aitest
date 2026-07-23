import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const listPageSource = readFileSync(new URL("../src/app/(main)/test-cases/page.tsx", import.meta.url), "utf8");
const detailPageSource = readFileSync(
  new URL("../src/app/(main)/test-cases/manual/[caseId]/page.tsx", import.meta.url),
  "utf8",
);
const backendRouteSource = readFileSync(new URL("../../backend/app/api/v1/test_cases.py", import.meta.url), "utf8");

test("manual test cases expose detail navigation from name and actions", () => {
  assert.match(listPageSource, /href={`\/test-cases\/manual\/\$\{item\.id\}\?project=\$\{item\.project_id\}`}/);
  assert.match(
    listPageSource,
    /label: "查看"[\s\S]*href: `\/test-cases\/manual\/\$\{item\.id\}\?project=\$\{item\.project_id\}`/,
  );
});

test("manual test case detail page loads and renders the complete case", () => {
  assert.match(detailPageSource, /useParams<\{ caseId: string \}>/);
  assert.match(detailPageSource, /`\/projects\/\$\{projectId\}\/test-cases\/\$\{params\.caseId\}`/);
  assert.match(detailPageSource, /用例信息/);
  assert.match(detailPageSource, /前置条件/);
  assert.match(detailPageSource, /操作步骤/);
  assert.match(detailPageSource, /预期结果/);
  assert.match(detailPageSource, /备注/);
  assert.match(detailPageSource, /rowKey: `\$\{testCase\.id\}-step-\$\{index\}`/);
  assert.match(detailPageSource, /key=\{step\.rowKey\}/);
});

test("manual test case detail keeps the return action in the content header", () => {
  assert.doesNotMatch(detailPageSource, /actions=\{/);
  assert.doesNotMatch(detailPageSource, />手动测试用例</);
  assert.doesNotMatch(detailPageSource, />已创建</);
  assert.match(
    detailPageSource,
    /flex flex-wrap items-start justify-between gap-3[\s\S]*testCase\.title[\s\S]*返回测试用例/,
  );
});

test("backend exposes a project-scoped manual test case detail endpoint", () => {
  assert.match(backendRouteSource, /@manual_router\.get\("\/\{case_id\}"/);
  assert.match(backendRouteSource, /test_case_service\.get_manual_test_case\(project_id, case_id, actor\)/);
});
