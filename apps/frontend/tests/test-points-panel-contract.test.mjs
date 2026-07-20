import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const panelSource = readFileSync(
  new URL("../src/components/ai-testing/test-points-panel.tsx", import.meta.url),
  "utf8",
);

test("test points prerequisite empty state reuses the illustrated empty-state treatment", () => {
  assert.match(
    panelSource,
    /import \{ IllustratedEmptyState \} from "@\/components\/ai-testing\/illustrated-empty-state"/,
  );
  assert.equal((panelSource.match(/<IllustratedEmptyState/g) ?? []).length, 2);
  assert.match(panelSource, /title="暂无测试点"/);
  assert.match(panelSource, /请先在需求分析中点击“转为最终需求”。/);
});
