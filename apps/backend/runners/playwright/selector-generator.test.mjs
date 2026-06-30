import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { buildElementSelectors } from "./selector-generator.mjs";

describe("buildElementSelectors", () => {
  it("keeps only primary and fallback selectors using resilient priority", () => {
    const selectors = buildElementSelectors({
      role: "button",
      name: "新建用户",
      label: "新建用户",
      testId: "create-user",
      text: "新建用户",
      css: "#create-user",
      xpath: "//button[1]",
    });

    assert.equal(selectors.primary_selector.kind, "role");
    assert.equal(selectors.primary_selector.code, "page.getByRole('button', { name: '新建用户' })");
    assert.equal(selectors.fallback_selector.kind, "testid");
    assert.equal(selectors.fallback_selector.code, "page.getByTestId('create-user')");
    assert.deepEqual(Object.keys(selectors).sort(), ["fallback_selector", "primary_selector"]);
    assert.doesNotMatch(JSON.stringify(selectors), /xpath|\/\/button/i);
  });

  it("uses test id before visible text and css when role or label are unavailable", () => {
    const selectors = buildElementSelectors({
      name: "搜索",
      testId: "search-submit",
      text: "搜索",
      css: "button.search-submit",
    });

    assert.equal(selectors.primary_selector.kind, "testid");
    assert.equal(selectors.primary_selector.code, "page.getByTestId('search-submit')");
    assert.equal(selectors.fallback_selector.kind, "text");
    assert.equal(selectors.fallback_selector.code, "page.getByText('搜索')");
  });

  it("builds contextual selectors before css for repeated card actions", () => {
    const candidates = buildElementSelectors({
      role: "button",
      name: "对话历史",
      text: "对话历史",
      css: "div:nth-of-type(2) > span:nth-of-type(3)",
      context: {
        container_name: "测试_自主规划智能体",
      },
    });

    assert.equal(candidates.primary_selector.kind, "role");
    assert.equal(candidates.fallback_selector.kind, "contextual");
    assert.match(candidates.fallback_selector.code, /测试_自主规划智能体/);
    assert.doesNotMatch(candidates.fallback_selector.code, /nth-of-type/);
  });

  it("does not create fake selectors for unnamed elements", () => {
    const selectors = buildElementSelectors({
      role: "button",
      name: "",
    });

    assert.deepEqual(selectors, {});
  });
});
