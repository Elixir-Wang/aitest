import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const sidebarSource = readFileSync(new URL("../src/navigation/sidebar/sidebar-items.ts", import.meta.url), "utf8");
const formSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/performance-test-form.tsx", import.meta.url),
  "utf8",
);
const listPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/performance-tests/page.tsx", import.meta.url),
  "utf8",
);
const allListPageSource = readFileSync(
  new URL("../src/app/(main)/performance-tests/page.tsx", import.meta.url),
  "utf8",
);

test("performance testing sidebar entry is enabled and project scoped", () => {
  assert.match(
    sidebarSource,
    /title: "性能测试",\s*url: "\/projects\/:projectId\/performance-tests",\s*icon: Gauge,\s*projectScoped: true,/,
  );
  assert.doesNotMatch(sidebarSource, /title: "性能测试",[\s\S]{0,160}?comingSoon: true/);
});

test("performance testing API client exposes preview and CRUD contracts", () => {
  assert.match(apiClientSource, /export function previewPerformanceRequest/);
  assert.match(apiClientSource, /performance-tests\/request-preview/);
  assert.match(apiClientSource, /export function listPerformanceTests/);
  assert.match(apiClientSource, /export function createPerformanceTest/);
  assert.match(apiClientSource, /export function deletePerformanceTest/);
});

test("performance create form reuses endpoint and environment assets without secret fields", () => {
  assert.match(formSource, /listApiAutomationEndpoints\(projectId\)/);
  assert.match(formSource, /listApiAutomationEnvironments\(projectId\)/);
  assert.match(formSource, /previewPerformanceRequest\(projectId/);
  assert.match(formSource, /measurement_duration_seconds/);
  assert.doesNotMatch(formSource, /password|token|cookie|api_key/i);
});

test("performance list route renders the project-scoped list component", () => {
  assert.match(listPageSource, /<PerformanceTestList projectId=\{params\.projectId\} \/>/);
});

test("global performance route renders the cross-project task list", () => {
  assert.match(allListPageSource, /projectScope="all"/);
  assert.match(allListPageSource, /<AllPerformanceTestList \/>/);
});
