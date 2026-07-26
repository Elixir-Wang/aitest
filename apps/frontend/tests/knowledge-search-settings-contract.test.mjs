import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/knowledge/page.tsx", import.meta.url), "utf8");
const settingsSource = readFileSync(
  new URL("../src/components/ai-testing/knowledge-search-settings.tsx", import.meta.url),
  "utf8",
);

test("knowledge page adds search settings after company knowledge", () => {
  assert.match(pageSource, /value: "company", label: "公司知识库"/);
  assert.match(pageSource, /value: "settings", label: "检索设置"/);
  assert.match(pageSource, /<KnowledgeSearchSettings/);
  assert.match(pageSource, /projectName=\{effectiveProjectName\}/);
  assert.match(settingsSource, /projectName \?\? "当前项目"/);
});

test("search settings supports global and project endpoints", () => {
  assert.match(settingsSource, /"\/knowledge\/search-settings"/);
  assert.match(settingsSource, /`\/projects\/\$\{projectId\}\/knowledge\/search-settings`/);
  assert.match(settingsSource, /method: "PUT"/);
  assert.match(settingsSource, /method: "DELETE"/);
});

test("search settings renders all five source toggles", () => {
  assert.match(settingsSource, /import \{ Switch \} from "@\/components\/ui\/switch"/);
  for (const label of ["最终需求", "探索产物", "已采纳测试用例", "接口信息", "公司知识库"]) {
    assert.match(settingsSource, new RegExp(label));
  }
});
