import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const taskPageSource = readFileSync(new URL("../src/app/(main)/tasks/page.tsx", import.meta.url), "utf8");
const statusBadgeSource = readFileSync(new URL("../src/components/ui/status-badge.tsx", import.meta.url), "utf8");

test("interrupted task status uses destructive badge tone even when backend groups it as completed", () => {
  assert.match(statusBadgeSource, /export function taskStatusTone\(statusGroup: string, status: string\): StatusBadgeTone/);
  assert.match(statusBadgeSource, /\["blocked", "failed", "interrupted"\]\.includes\(status\)/);
  assert.match(statusBadgeSource, /return taskStatusGroupTone\(statusGroup\);/);
  assert.match(taskPageSource, /import \{ StatusBadge, taskStatusTone \} from "@\/components\/ui\/status-badge";/);
  assert.match(taskPageSource, /<StatusBadge tone=\{taskStatusTone\(task\.status_group, task\.status\)\}>/);
});
