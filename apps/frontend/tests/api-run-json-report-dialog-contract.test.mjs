import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const runDetailSource = readFileSync(
  new URL("../src/components/ai-testing/api-automation/api-run-detail.tsx", import.meta.url),
  "utf8",
);

test("API run JSON report opens in a large dialog instead of rendering below the logs", () => {
  assert.match(runDetailSource, /const \[reportOpen, setReportOpen\] = useState\(false\)/);
  assert.match(runDetailSource, /<Dialog onOpenChange={setReportOpen} open={reportOpen}>/);
  assert.match(runDetailSource, /<DialogTitle>JSON 报告<\/DialogTitle>/);
  assert.match(runDetailSource, /h-\[min\(52rem,calc\(100vh-2rem\)\)\]/);
  assert.match(runDetailSource, /w-\[calc\(100vw-2rem\)\]/);
  assert.match(runDetailSource, /sm:max-w-6xl/);
  assert.match(runDetailSource, /whitespace-pre/);
  assert.match(runDetailSource, /JSON\.stringify\(report, null, 2\)/);
  assert.doesNotMatch(runDetailSource, /\{report \? <div><div className="mb-2 font-semibold text-sm">JSON 报告<\/div>/);
});

test("API run detail localizes observed status and hides internal identity metadata", () => {
  assert.match(runDetailSource, /observed: "已观察"/);
  assert.doesNotMatch(
    runDetailSource,
    /<p className="mt-2 break-all font-mono text-muted-foreground text-sm">\{runId\}<\/p>/,
  );
  assert.doesNotMatch(runDetailSource, /<RunDetailValue label="执行人"/);
});
