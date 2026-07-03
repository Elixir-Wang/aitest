import { parsePlaywrightLocatorString, isParseableLocatorString } from "./locator-parser.mjs";
import { test } from "node:test";
import assert from "node:assert/strict";

function makeFakePage() {
  return {
    getByRole: (...args) => ({ __kind: "role", args }),
    getByLabel: (...args) => ({ __kind: "label", args }),
    getByTestId: (...args) => ({ __kind: "testid", args }),
    getByText: (...args) => ({ __kind: "text", args }),
    getByPlaceholder: (...args) => ({ __kind: "placeholder", args }),
  };
}

test("parses getByRole with name", () => {
  const page = makeFakePage();
  const locator = parsePlaywrightLocatorString(page, "getByRole('treeitem', { name: '自主规划 Agent' })");
  assert.equal(locator.__kind, "role");
  assert.deepEqual(locator.args, ["treeitem", { name: "自主规划 Agent" }]);
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
  assert.equal(isParseableLocatorString("getByLabel('X')"), true);
  assert.equal(isParseableLocatorString("getByTestId('x')"), true);
  assert.equal(isParseableLocatorString("getByText('x')"), true);
  assert.equal(isParseableLocatorString("getByPlaceholder('x')"), true);
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
