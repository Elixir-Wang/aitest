import { parsePlaywrightLocatorString, isParseableLocatorString } from "./locator-parser.mjs";
import { test } from "node:test";
import assert from "node:assert/strict";

function makeFakePage() {
  const chain = (kind, args, calls = []) => ({
    __kind: kind,
    args,
    calls,
    filter(options) {
      return chain(kind, args, [...calls, ["filter", options]]);
    },
    getByRole(...roleArgs) {
      return chain("role", roleArgs, [...calls, ["getByRole", roleArgs]]);
    },
  });
  return {
    getByRole: (...args) => chain("role", args),
    getByLabel: (...args) => ({ __kind: "label", args }),
    getByTestId: (...args) => chain("testid", args),
    getByText: (...args) => ({ __kind: "text", args }),
    getByPlaceholder: (...args) => ({ __kind: "placeholder", args }),
    locator: (...args) => ({ __kind: "css", args }),
  };
}

test("parses getByRole with name", () => {
  const page = makeFakePage();
  const locator = parsePlaywrightLocatorString(page, "getByRole('treeitem', { name: '自主规划 Agent' })");
  assert.equal(locator.__kind, "role");
  assert.deepEqual(locator.args, ["treeitem", { name: "自主规划 Agent" }]);
});

test("parses page-prefixed getByRole with name", () => {
  const page = makeFakePage();
  const locator = parsePlaywrightLocatorString(page, "page.getByRole('button', { name: '使用' })");
  assert.equal(locator.__kind, "role");
  assert.deepEqual(locator.args, ["button", { name: "使用" }]);
});

test("parses getByRole with name + exact", () => {
  const page = makeFakePage();
  const locator = parsePlaywrightLocatorString(page, "getByRole('button', { name: 'Save', exact: true })");
  assert.equal(locator.__kind, "role");
  assert.equal(locator.args[1].exact, true);
});

test("parses getByRole with level (heading)", () => {
  const page = makeFakePage();
  const locator = parsePlaywrightLocatorString(page, "getByRole('heading', { level: 2 })");
  assert.equal(locator.__kind, "role");
  assert.equal(locator.args[1].level, 2);
});

test("parses getByRole without options", () => {
  const page = makeFakePage();
  const locator = parsePlaywrightLocatorString(page, "getByRole('main')");
  assert.equal(locator.__kind, "role");
  assert.deepEqual(locator.args, ["main", {}]);
});

test("parses getByLabel", () => {
  const page = makeFakePage();
  const locator = parsePlaywrightLocatorString(page, "getByLabel('用户名')");
  assert.equal(locator.__kind, "label");
  assert.equal(locator.args[0], "用户名");
});

test("parses getByTestId", () => {
  const page = makeFakePage();
  const locator = parsePlaywrightLocatorString(page, "getByTestId('user-avatar')");
  assert.equal(locator.__kind, "testid");
  assert.equal(locator.args[0], "user-avatar");
});

test("parses getByText with exact", () => {
  const page = makeFakePage();
  const locator = parsePlaywrightLocatorString(page, "getByText('提交订单', { exact: true })");
  assert.equal(locator.__kind, "text");
  assert.equal(locator.args[1].exact, true);
});

test("parses getByPlaceholder", () => {
  const page = makeFakePage();
  const locator = parsePlaywrightLocatorString(page, "getByPlaceholder('请输入手机号')");
  assert.equal(locator.__kind, "placeholder");
  assert.equal(locator.args[0], "请输入手机号");
});

test("parses CSS locator expressions", () => {
  const page = makeFakePage();
  const locator = parsePlaywrightLocatorString(page, "page.locator('[data-testid=\"workspace-nav\"]')");
  assert.equal(locator.__kind, "css");
  assert.equal(locator.args[0], "[data-testid=\"workspace-nav\"]");
});

test("parses contextual test id + role locator expressions", () => {
  const page = makeFakePage();
  const locator = parsePlaywrightLocatorString(
    page,
    "page.getByTestId('agent-card').filter({ hasText: '测试_自主规划智能体' }).getByRole('button', { name: '对话历史' })",
  );
  assert.equal(locator.__kind, "role");
  assert.deepEqual(locator.args, ["button", { name: "对话历史" }]);
  assert.deepEqual(locator.calls, [
    ["filter", { hasText: "测试_自主规划智能体" }],
    ["getByRole", ["button", { name: "对话历史" }]],
  ]);
});

test("parses contextual role + role locator expressions", () => {
  const page = makeFakePage();
  const locator = parsePlaywrightLocatorString(
    page,
    "page.getByRole('listitem').filter({ hasText: '测试_自主规划智能体' }).getByRole('button', { name: '对话历史' })",
  );
  assert.equal(locator.__kind, "role");
  assert.deepEqual(locator.args, ["button", { name: "对话历史" }]);
  assert.deepEqual(locator.calls[0], ["filter", { hasText: "测试_自主规划智能体" }]);
});

test("returns null for unknown locator forms", () => {
  const page = makeFakePage();
  assert.equal(parsePlaywrightLocatorString(page, "button-create-agent-001"), null);
  assert.equal(parsePlaywrightLocatorString(page, "e15"), null);
  assert.equal(parsePlaywrightLocatorString(page, ""), null);
  assert.equal(parsePlaywrightLocatorString(page, null), null);
  assert.equal(parsePlaywrightLocatorString(page, undefined), null);
  assert.equal(parsePlaywrightLocatorString(page, "#button"), null);
});

test("isParseableLocatorString detects locator strings", () => {
  assert.equal(isParseableLocatorString("getByRole('button')"), true);
  assert.equal(isParseableLocatorString("page.getByRole('button')"), true);
  assert.equal(isParseableLocatorString("getByLabel('X')"), true);
  assert.equal(isParseableLocatorString("getByTestId('x')"), true);
  assert.equal(isParseableLocatorString("getByText('x')"), true);
  assert.equal(isParseableLocatorString("getByPlaceholder('x')"), true);
  assert.equal(isParseableLocatorString("page.locator('[data-testid=\"x\"]')"), true);
  assert.equal(isParseableLocatorString("locator('#x')"), true);
  assert.equal(isParseableLocatorString("page.getByRole('listitem').filter({ hasText: 'x' }).getByRole('button', { name: 'y' })"), true);
  assert.equal(isParseableLocatorString("button-x-001"), false);
  assert.equal(isParseableLocatorString("e15"), false);
  assert.equal(isParseableLocatorString(""), false);
});

test("handles mixed quotes", () => {
  const page = makeFakePage();
  const locator = parsePlaywrightLocatorString(page, "getByRole(\"button\", { name: \"Submit\" })");
  assert.equal(locator.__kind, "role");
  assert.equal(locator.args[0], "button");
  assert.equal(locator.args[1].name, "Submit");
});
