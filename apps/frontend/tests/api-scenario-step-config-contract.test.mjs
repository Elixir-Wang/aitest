import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../src/components/ai-testing/api-automation/api-scenario-step-config.tsx", import.meta.url),
  "utf8",
);

test("scenario step editor follows the request lifecycle", () => {
  assert.match(source, /value="request"[\s\S]*请求/);
  assert.match(source, /value="pre-request"[\s\S]*前置处理/);
  assert.match(source, /value="response"[\s\S]*响应处理/);
  assert.match(source, /value="assertions"[\s\S]*断言/);
  assert.match(source, /value="control"[\s\S]*执行控制/);
});

test("request editor exposes the compact Postman-like sections", () => {
  assert.match(source, /URL \/ Params/);
  assert.match(source, /Authorization/);
  assert.match(source, /Headers/);
  assert.match(source, /Body/);
  assert.match(source, /Cookies/);
});

test("lifecycle editor preserves structured response extraction and scripts", () => {
  assert.match(source, /响应提取/);
  assert.match(source, /前置脚本/);
  assert.match(source, /后置脚本/);
  assert.match(source, /变量动作/);
});
