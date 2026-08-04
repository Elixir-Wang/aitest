import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/tasks/page.tsx", import.meta.url), "utf8");

test("task center opens directly on the complete task list without local tabs", () => {
  assert.doesNotMatch(pageSource, /tabs=\{\["全部任务", "等待人工", "失败任务"\]\}/);
  assert.match(pageSource, /apiRequest<ApiTaskList>\(`\/tasks\?\$\{params\.toString\(\)\}`\)/);
});
