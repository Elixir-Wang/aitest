import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/reports/page.tsx", import.meta.url), "utf8");
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("report center loads generated performance reports from the backend index", () => {
  assert.match(apiClientSource, /export type ReportCenterItem/);
  assert.match(apiClientSource, /export function listReportCenterItems/);
  assert.match(apiClientSource, /\/reports\?\$\{params\.toString\(\)\}/);
  assert.match(pageSource, /listReportCenterItems\(\)/);
  assert.doesNotMatch(pageSource, /const reports:.*= \[\]/);
});

test("report center defaults to performance and opens the frozen report detail", () => {
  assert.match(pageSource, /useState\("性能"\)/);
  assert.match(pageSource, /href: report\.href/);
  assert.match(pageSource, /分析版本 V\{report\.analysis_version\}/);
  assert.match(pageSource, /verdictLabel\(report\.verdict\)/);
  assert.match(pageSource, /qualityLabel\(report\.quality_status\)/);
  assert.doesNotMatch(pageSource, /useLocalTableSelection|deleteSelected|新建报告/);
});
