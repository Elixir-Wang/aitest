import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const errorFeedbackSource = readFileSync(new URL("../src/lib/error-feedback.ts", import.meta.url), "utf8");

test("error feedback detail action opens the operation log detail page when a log id exists", () => {
  assert.match(errorFeedbackSource, /window\.location\.assign\(operationLogUrl\(result\?\.log_id, result\?\.trace_id \|\| traceId\)\)/);
  assert.match(errorFeedbackSource, /return `\/settings\/logs\/\$\{encodeURIComponent\(logId\)\}`/);
  assert.match(errorFeedbackSource, /return operationLogListUrl\(keyword\)/);
});
