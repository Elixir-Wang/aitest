# API Response Example Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在接口详情的每个响应媒体类型下展示 OpenAPI 响应示例，并在没有显式示例时生成 Schema 兜底示例。

**Architecture:** 前端从已返回的 `responses[status].content[contentType]` 读取示例数据。新增纯函数将 `examples`、`example` 和 `schema.example` 规范为统一列表，并由 `ResponseSummary` 渲染 JSON 代码块；只有该列表为空时才调用现有 `exampleFromSchema`。

**Tech Stack:** Next.js、React、TypeScript、Tailwind CSS、Node.js `node:test` 源码契约测试、Biome。

## Global Constraints

- 不修改后端 OpenAPI 解析、数据库持久化或 API DTO。
- 不新增依赖。
- `undefined` 以外的任意示例值均为有效示例。
- 不处理响应状态码切换的既有测试不一致问题。

---

### Task 1: 锁定响应示例渲染契约

**Files:**
- Modify: `apps/frontend/tests/api-automation-interface-set-copy-contract.test.mjs:378-395`

**Interfaces:**
- Consumes: 页面源文件中的 `ResponseSummary`、`getResponseExamples`、`ResponseExampleBlock`。
- Produces: 对显式示例优先级与 Schema 兜底的回归约束。

- [ ] **Step 1: 写入失败的源码契约测试**

```js
test("project api automation endpoint responses render OpenAPI examples with schema fallback", () => {
  assert.match(projectPageSource, /function getResponseExamples/);
  assert.match(projectPageSource, /Object\.entries\(asRecord\(content\.examples\)\)/);
  assert.match(projectPageSource, /content\.example !== undefined/);
  assert.match(projectPageSource, /schema\.example !== undefined/);
  assert.match(projectPageSource, /exampleFromSchema\(schema\)/);
  assert.match(projectPageSource, /<ResponseExampleBlock examples=\{getResponseExamples\(content\)\} \/>/);
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `node --test tests/api-automation-interface-set-copy-contract.test.mjs`

Expected: 新增测试失败，提示未找到 `getResponseExamples`。

### Task 2: 规范化并渲染响应示例

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx:3008-3058`

**Interfaces:**
- Consumes: `content: unknown`，其结构符合 OpenAPI `Media Type Object`。
- Produces: `getResponseExamples(content): ApiResponseExample[]` 和 `ResponseExampleBlock`。

- [ ] **Step 1: 定义统一示例类型和解析函数**

```ts
type ApiResponseExample = { label: string; value: unknown };

function getResponseExamples(content: unknown): ApiResponseExample[] {
  const media = asRecord(content);
  const namedExamples = Object.entries(asRecord(media.examples)).flatMap(([name, value]) => {
    const example = asRecord(value);
    return example.value === undefined
      ? []
      : [{ label: asString(example.summary) || asString(example.description) || name, value: example.value }];
  });
  if (namedExamples.length > 0) return namedExamples;
  if (media.example !== undefined) return [{ label: "示例", value: media.example }];
  const schema = asRecord(media.schema);
  if (schema.example !== undefined) return [{ label: "示例", value: schema.example }];
  return Object.keys(schema).length > 0 ? [{ label: "示例", value: exampleFromSchema(schema) }] : [];
}
```

- [ ] **Step 2: 在每个媒体类型下渲染示例块**

```tsx
<ResponseExampleBlock examples={getResponseExamples(content)} />
```

`ResponseExampleBlock` 对每条示例输出标题和 `JSON.stringify(value, null, 2)` 形成的只读代码块；当 `examples` 为空时返回 `null`。

- [ ] **Step 3: 运行测试确认通过**

Run: `node --test tests/api-automation-interface-set-copy-contract.test.mjs`

Expected: 所有测试通过。

### Task 3: 代码质量验证

**Files:**
- Verify: `apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx`
- Verify: `apps/frontend/tests/api-automation-interface-set-copy-contract.test.mjs`

**Interfaces:**
- Consumes: 已完成的响应示例实现与契约测试。
- Produces: 可复现的测试和静态检查证据。

- [ ] **Step 1: 运行目标测试**

Run: `node --test tests/api-automation-interface-set-copy-contract.test.mjs`

Expected: 退出码为 `0`。

- [ ] **Step 2: 运行 Biome 静态检查**

Run: `npx biome check "src/app/(main)/projects/[projectId]/automation/api/page.tsx" "tests/api-automation-interface-set-copy-contract.test.mjs"`

Expected: 退出码为 `0`，无格式或 lint 错误。
