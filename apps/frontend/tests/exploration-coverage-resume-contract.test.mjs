import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const pageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx", import.meta.url),
  "utf8",
);

test("exploration detail exposes coverage and true checkpoint resume", () => {
  assert.match(
    pageSource,
    /\/page-exploration\/projects\/\$\{params\.projectId\}\/coverage\?run_id=\$\{params\.runId\}/,
  );
  assert.match(pageSource, /\/page-exploration\/runs\/\$\{run\.id\}\/resume/);
  assert.match(pageSource, /探索覆盖/);
  assert.match(pageSource, /已探索动作/);
  assert.match(pageSource, /待探索动作/);
  assert.match(pageSource, /从检查点继续/);
});
