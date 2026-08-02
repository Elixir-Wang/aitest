import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const sidebarSource = readFileSync(new URL("../src/navigation/sidebar/sidebar-items.ts", import.meta.url), "utf8");

test("sidebar enables UI automation and keeps model evaluation coming soon", () => {
  assert.match(sidebarSource, /title: "UI 自动化",\s*url: "\/automation\/ui",\s*icon: PlaySquare,/);
  assert.doesNotMatch(
    sidebarSource,
    /title: "UI 自动化",[\s\S]*?comingSoon: true,[\s\S]*?disabled: true,[\s\S]*?title: "接口自动化"/,
  );
  assert.match(
    sidebarSource,
    /title: "模型评测",\s*url: "\/projects\/:projectId\/model-evaluations",\s*icon: BrainCircuit,\s*comingSoon: true,\s*disabled: true,\s*projectScoped: true,/,
  );
});

test("sidebar places model evaluation immediately after performance testing", () => {
  assert.match(sidebarSource, /title: "性能测试",[\s\S]*?title: "模型评测",[\s\S]*?title: "报告中心",/);
});
