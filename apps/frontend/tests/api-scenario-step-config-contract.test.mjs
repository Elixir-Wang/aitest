import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../src/components/ai-testing/api-automation/api-scenario-step-config.tsx", import.meta.url),
  "utf8",
);
const editorSource = readFileSync(
  new URL("../src/components/ai-testing/api-automation/api-scenario-editor.tsx", import.meta.url),
  "utf8",
);
const assetPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/automation/api/page.tsx", import.meta.url),
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
  assert.doesNotMatch(source, /<RequestBlock title="Authorization">/);
  assert.match(source, /Headers/);
  assert.match(source, /Body/);
  assert.match(source, /Cookies/);
  assert.doesNotMatch(source, /固定值沿用接口资产；当前节点只配置动态引用/);
  assert.match(source, /displayBindingValue/);
});

test("view endpoint asset navigates to and selects the current endpoint", () => {
  assert.match(source, /automation\/api\?endpoint=\$\{encodeURIComponent\(endpoint\.id\)\}/);
  assert.match(editorSource, /projectId=\{projectId\}/);
  assert.match(assetPageSource, /searchParams\.get\("endpoint"\)/);
  assert.match(assetPageSource, /endpoint\.id === requestedEndpointId/);
});

test("switching a dynamic source back to literal persists the resolved override value", () => {
  assert.match(source, /fallbackValue !== undefined/);
  assert.match(source, /resolveRequestFieldValue\(requestOverrides, field\.target, field\.defaultValue\)/);
  assert.match(source, /onBindingChange\(field\.target, value, literalValue\)/);
});

test("lifecycle editor preserves structured response extraction and scripts", () => {
  assert.match(source, /响应提取/);
  assert.match(source, /前置脚本/);
  assert.match(source, /后置脚本/);
  assert.match(source, /变量动作/);
});

test("response extractors use a two-row labeled card layout", () => {
  assert.match(source, /保存为/);
  assert.match(source, /来源/);
  assert.match(source, /提取路径/);
  assert.match(source, /grid-cols-\[minmax\(0,1fr\)_minmax\(0,1fr\)_36px\]/);
  assert.match(source, /col-span-2/);
});

test("response extractor path control adapts to its source", () => {
  assert.match(source, /response\.status/);
  assert.match(source, /自动取 HTTP 状态码/);
  assert.match(source, /\$\.data\.id/);
  assert.match(source, /Header 名称/);
});

test("response extractor exposes SSE event JSON configuration", () => {
  assert.match(source, /sse_event_json/);
  assert.match(source, /SSE 事件 JSON/);
  assert.match(source, /事件名称/);
  assert.match(source, /首次匹配/);
  assert.match(source, /最后匹配/);
  assert.match(source, /全部匹配/);
});

test("response extractor exposes required behavior", () => {
  assert.match(source, /extractor\.required \?\? true/);
  assert.match(source, /未提取到时终止步骤/);
});

test("assertion rows use stable identity and explicit field labels", () => {
  assert.match(source, /key=\{assertion\.id \?\? assertion\.type\}/);
  assert.match(source, /crypto\.randomUUID\(\)/);
  assert.match(source, /响应来源/);
  assert.match(source, /目标路径/);
  assert.match(source, /判断条件/);
  assert.match(source, /期望值/);
});

test("existence assertions do not render a disabled expectation input", () => {
  assert.doesNotMatch(source, /<Input disabled placeholder="无需期望值" \/>/);
  assert.match(source, /无需设置期望值/);
});
