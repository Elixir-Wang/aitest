import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const viewSource = readFileSync(
  new URL("../src/components/ai-testing/operation-logs/operation-log-view.tsx", import.meta.url),
  "utf8",
);
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("operation log rows truncate long requirement analysis actions inside fixed table cells", () => {
  assert.match(viewSource, /<Table className="min-w-\[1080px\] table-fixed">/);
  assert.match(viewSource, /const actionLabel = operationLogActionToLabel\(row\.action\);/);
  assert.match(
    viewSource,
    /<TableCell className="overflow-hidden" title=\{actionLabel\}>\s*<span className="block truncate">\{actionLabel\}<\/span>\s*<\/TableCell>/,
  );
  assert.match(
    viewSource,
    /<TableCell className="overflow-hidden" title=\{objectLabel\}>\s*<span className="block truncate">\{objectLabel\}<\/span>\s*<\/TableCell>/,
  );
});

test("operation log action labels cover requirement analysis lifecycle actions", () => {
  assert.match(apiClientSource, /submit_requirement_analysis: "提交需求分析"/);
  assert.match(apiClientSource, /start_requirement_analysis: "开始需求分析"/);
  assert.match(apiClientSource, /fail_requirement_analysis: "需求分析失败"/);
  assert.match(apiClientSource, /finish_requirement_analysis: "完成需求分析"/);
});
