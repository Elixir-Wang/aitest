import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const errorFeedbackSource = readFileSync(new URL("../src/lib/error-feedback.ts", import.meta.url), "utf8");

test("error feedback opens operation log list instead of direct detail route", () => {
  assert.match(errorFeedbackSource, /function operationLogListUrl\(/);
  assert.match(errorFeedbackSource, /window\.location\.assign\(operationLogListUrl\(/);
  assert.doesNotMatch(
    errorFeedbackSource,
    /window\.location\.assign\(`\/settings\/logs\/\$\{encodeURIComponent\(result\.log_id\)\}`\)/,
  );
});
