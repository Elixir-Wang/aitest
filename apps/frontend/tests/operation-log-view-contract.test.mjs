import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const viewSource = readFileSync(
  new URL("../src/components/ai-testing/operation-logs/operation-log-view.tsx", import.meta.url),
  "utf8",
);
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("operation log rows truncate long requirement analysis actions inside fixed table cells", () => {
  assert.match(viewSource, /<Table className="min-w-\[1080px\] table-fixed">/);
  assert.match(viewSource, /const actionLabel = operationLogActionToLabel\(row\.action\);/);
  assert.match(
    viewSource,
    /<TableCell className="overflow-hidden" title=\{actionLabel\}>\s*<span className="block truncate">\{actionLabel\}<\/span>\s*<\/TableCell>/,
  );
  assert.match(
    viewSource,
    /<TableCell className="overflow-hidden" title=\{objectLabel\}>\s*<span className="block truncate">\{objectLabel\}<\/span>\s*<\/TableCell>/,
  );
});

test("operation log action labels cover requirement analysis lifecycle actions", () => {
  assert.match(apiClientSource, /submit_requirement_analysis: "提交需求分析"/);
  assert.match(apiClientSource, /start_requirement_analysis: "开始需求分析"/);
  assert.match(apiClientSource, /fail_requirement_analysis: "需求分析失败"/);
  assert.match(apiClientSource, /finish_requirement_analysis: "完成需求分析"/);
});

test("operation log filters load dynamic options from the backend with static fallback", () => {
  assert.match(apiClientSource, /export type ApiOperationLogFilterOptions = \{/);
  assert.match(viewSource, /apiRequest<ApiOperationLogFilterOptions>\(`\$\{endpoint\}\/filter-options\$\{suffix\}`\)/);
  assert.match(viewSource, /params\.set\("project_id", projectId\);/);
  assert.match(viewSource, /setProjects\(await apiRequest<ApiProject\[\]>\("\/projects"\)\);/);
  assert.match(viewSource, /function mergeOptions\(fallback: string\[\], dynamicOptions: string\[\] \| undefined\)/);
  assert.match(viewSource, /const moduleOptions = useMemo\(/);
  assert.match(viewSource, /const actionOptions = useMemo\(/);
  assert.match(viewSource, /const resultOptions = useMemo\(/);
});

test("operation log view exports the current filters as a csv download", () => {
  assert.match(viewSource, /apiBlobRequest\(`\$\{endpoint\}\/export\$\{exportQuery\}`\)/);
  assert.match(viewSource, /function queryForExport\(query: string\)/);
  assert.match(viewSource, /params\.delete\("page"\);/);
  assert.match(viewSource, /params\.delete\("page_size"\);/);
  assert.match(viewSource, /function downloadBlob\(blob: Blob, filename: string\)/);
  assert.match(viewSource, /<Download className="size-4" \/>/);
});

test("operation log labels cover persisted system actions and modules", () => {
  assert.match(apiClientSource, /auto_auth_login: "自动登录"/);
  assert.match(apiClientSource, /query: "查询"/);
  assert.match(apiClientSource, /delete_conversation: "删除会话"/);
  assert.match(apiClientSource, /api_error: "接口错误"/);
  assert.match(apiClientSource, /cancel_requirement_analysis: "取消需求分析"/);
  assert.match(apiClientSource, /interrupt_exploration: "中断探索"/);
  assert.match(apiClientSource, /stop_stale_test_case_generation: "停止过期用例生成"/);
  assert.match(apiClientSource, /test_case: "测试用例"/);
  assert.match(apiClientSource, /api: "接口"/);
});
