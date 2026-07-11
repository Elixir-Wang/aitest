import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const listPageSource = readFileSync(new URL("../src/app/(main)/test-cases/page.tsx", import.meta.url), "utf8");
const reviewPageSource = readFileSync(
  new URL("../src/app/(main)/test-cases/[setId]/review/page.tsx", import.meta.url),
  "utf8",
);
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const pageShellSource = readFileSync(new URL("../src/components/ai-testing/page-shell.tsx", import.meta.url), "utf8");

test("test case set list exposes the dedicated review entry", () => {
  assert.match(listPageSource, /label: "查看"/);
  assert.match(listPageSource, /icon: ClipboardCheck/);
  assert.match(listPageSource, /href: `\/test-cases\/\$\{item\.id\}\/review\?project=\$\{item\.project_id\}`/);
  assert.match(listPageSource, /disabled: item\.case_count === 0 \|\| isTestCaseSetGenerating\(item\)/);
});

test("api client exposes review feedback contracts", () => {
  assert.match(apiClientSource, /review_feedback: string/);
  assert.match(apiClientSource, /preconditions\?: string/);
  assert.match(apiClientSource, /export type ApiTestCaseStep =/);
  assert.match(apiClientSource, /steps: ApiTestCaseStep\[\]/);
  assert.match(apiClientSource, /steps\?: ApiTestCaseStep\[\]/);
  assert.match(apiClientSource, /expected_result\?: string/);
  assert.match(apiClientSource, /reviewed_by: string/);
  assert.match(apiClientSource, /reviewed_at: string \| null/);
  assert.match(apiClientSource, /export type ApiTestCaseReviewStats =/);
  assert.match(apiClientSource, /export type ApiTestCaseReviewUpdate =/);
  assert.match(apiClientSource, /export type ApiTestCaseReviewResult =/);
  assert.match(apiClientSource, /review_stats: ApiTestCaseReviewStats/);
});

test("review page includes adoption metrics and review filters", () => {
  assert.match(reviewPageSource, /<ReviewSummaryStrip/);
  assert.match(reviewPageSource, /stats=\{stats\}/);
  assert.match(reviewPageSource, /SlidingNumber/);
  assert.match(reviewPageSource, /采纳率/);
  assert.match(reviewPageSource, /评审进度/);
  assert.match(reviewPageSource, /用例数量/);
  assert.doesNotMatch(reviewPageSource, /用例总数/);
  assert.match(reviewPageSource, /lg:flex-row lg:items-center lg:justify-between/);
  assert.match(reviewPageSource, /lg:max-w-2xl/);
  assert.match(reviewPageSource, /type ReviewFilter = "all" \| "ready_for_review" \| "approved" \| "rejected"/);
  assert.match(
    reviewPageSource,
    /const visibleReviewFilters: Exclude<ReviewFilter, "all">\[\] = \["ready_for_review", "approved", "rejected"\]/,
  );
  assert.match(reviewPageSource, /useState<ReviewFilter>\("ready_for_review"\)/);
});

test("review page uses the test case set name as the final breadcrumb", () => {
  assert.match(reviewPageSource, /\.\.\.\(testCaseSet \? \[\{ label: testCaseSet\.name \}\] : \[\]\)/);
  assert.doesNotMatch(reviewPageSource, /\{ label: testCaseSet\?\.name \?\? "用例评审" \}/);
});

test("review filters show status counts", () => {
  assert.match(reviewPageSource, /const filterCounts: Record<ReviewFilter, number> =/);
  assert.match(reviewPageSource, /all: stats\.case_count/);
  assert.match(reviewPageSource, /ready_for_review: stats\.pending_count/);
  assert.match(reviewPageSource, /approved: stats\.approved_count/);
  assert.match(reviewPageSource, /rejected: stats\.rejected_count/);
  assert.match(reviewPageSource, /filterCounts\[item\]/);
});

test("review page calls the case review endpoint", () => {
  assert.match(
    reviewPageSource,
    /`\/projects\/\$\{testCaseSet\.project_id\}\/test-case-sets\/\$\{testCaseSet\.id\}\/cases\/\$\{caseId\}\/review`/,
  );
  assert.match(reviewPageSource, /method: "PATCH"/);
  assert.match(reviewPageSource, /type ApiTestCaseReviewUpdate/);
  assert.match(reviewPageSource, /type ApiTestCaseReviewResult/);
});

test("review page exports the current test case set as xmind", () => {
  assert.match(reviewPageSource, /导出测试用例/);
  assert.match(reviewPageSource, /Download/);
  assert.match(reviewPageSource, /apiBlobRequest/);
  assert.match(reviewPageSource, /`\/projects\/\$\{projectId\}\/test-case-sets\/\$\{testCaseSet\.id\}\/export\/xmind`/);
  assert.match(reviewPageSource, /function exportTestCases\(\)/);
  assert.match(reviewPageSource, /function downloadBlob\(blob: Blob, filename: string\)/);
  assert.match(reviewPageSource, /function safeDownloadName\(value: string\)/);
  assert.match(reviewPageSource, /测试用例已导出/);
  assert.match(reviewPageSource, /测试用例导出失败/);
});

test("review page supports approve reject and reset actions", () => {
  assert.match(reviewPageSource, /采纳/);
  assert.match(reviewPageSource, /不采纳/);
  assert.match(reviewPageSource, /修改/);
  assert.doesNotMatch(reviewPageSource, /回到待评审/);
  assert.doesNotMatch(reviewPageSource, /onReset/);
  assert.match(reviewPageSource, /status: "approved"/);
  assert.match(reviewPageSource, /status: "rejected"/);
});

test("review page can edit case content from the review actions", () => {
  assert.match(reviewPageSource, /type InlineEditState =/);
  assert.match(reviewPageSource, /function startInlineEdit\(testCase: ApiTestCase\)/);
  assert.match(reviewPageSource, /onEdit=\{\(\) => startInlineEdit\(selectedCase\)\}/);
  assert.match(reviewPageSource, /selectedCaseIsEditing/);
  assert.match(reviewPageSource, /<InlineCaseEditor editState=\{inlineEdit\} onChange=\{setInlineEdit\} \/>/);
  assert.match(reviewPageSource, /function InlineCaseEditor/);
  assert.match(reviewPageSource, /<Pencil className="size-4" \/>/);
  assert.match(reviewPageSource, /保存修改/);
  assert.match(reviewPageSource, /onSaveEdit=\{saveCaseContent\}/);
  assert.match(reviewPageSource, /onCancelEdit=\{\(\) =>/);
  assert.match(reviewPageSource, /type InlineEditStep = ApiTestCaseStep &/);
  assert.match(reviewPageSource, /testCase\.steps\.map\(\(step, index\) => \(\{/);
  assert.match(reviewPageSource, /action: stepActionText\(step\)/);
  assert.match(reviewPageSource, /expected_result: step\.expected_result \|\| testCase\.expected_result/);
  assert.match(reviewPageSource, /\{ action: "", expected_result: "", editKey:/);
  assert.match(reviewPageSource, /function EditableStepTable/);
  assert.match(reviewPageSource, /min-h-\[72px\] resize-y bg-white py-2 leading-5/);
  assert.match(reviewPageSource, /min-h-\[52px\] resize-y bg-white py-2 leading-5/);
  assert.match(reviewPageSource, /新增步骤/);
  assert.match(reviewPageSource, /删除/);
  assert.match(
    reviewPageSource,
    /expected_result: steps\[steps\.length - 1\]\?\.expected_result \|\| inlineEdit\.expectedResult/,
  );
  assert.match(reviewPageSource, /successMessage: "测试用例已修改"/);
  assert.doesNotMatch(reviewPageSource, /修改测试用例<\/DialogTitle>/);
  assert.doesNotMatch(reviewPageSource, /<ReviewBlock title="预期结果">/);
});

test("review page aligns the list toolbar and detail header separators", () => {
  assert.match(reviewPageSource, /<div className="flex flex-col gap-3 border-b p-4">/);
  assert.match(reviewPageSource, /<div className="border-b p-4">/);
  assert.doesNotMatch(reviewPageSource, /min-h-\[124px\]/);
});

test("fill viewport pages keep browser scrolling inside the page", () => {
  assert.match(pageShellSource, /document\.documentElement\.style\.overflow/);
  assert.match(pageShellSource, /document\.body\.style\.overflow/);
  assert.match(pageShellSource, /return \(\) =>/);
});

test("review page shows steps and expected result as a table", () => {
  assert.match(reviewPageSource, /测试步骤与预期结果/);
  assert.match(reviewPageSource, /<table className="w-full border-collapse text-left text-sm">/);
  assert.match(reviewPageSource, /<th className="[^"]*">测试步骤<\/th>/);
  assert.match(reviewPageSource, /<th className="[^"]*">预期结果<\/th>/);
  assert.match(reviewPageSource, /stepActionText\(step\) \|\| "-"/);
  assert.match(reviewPageSource, /return step\.action \|\| step\.step \|\| step\.description \|\| ""/);
  assert.match(reviewPageSource, /\{step\.expected_result \|\| testCase\.expected_result \|\| "-"\}/);
  assert.doesNotMatch(reviewPageSource, /rowSpan=\{testCase\.steps\.length\}/);
});

test("review page gives duplicate or sparse steps unique row keys", () => {
  assert.match(reviewPageSource, /const stepKeyCounts = new Map<string, number>\(\)/);
  assert.match(reviewPageSource, /rowKey: `\$\{keyBase\}-\$\{keyCount\}`/);
  assert.match(reviewPageSource, /key=\{rowKey\}/);
  assert.doesNotMatch(reviewPageSource, /key=\{`\$\{testCase\.id\}-\$\{step\.action\}-\$\{step\.expected_result\}`\}/);
});

test("review page keeps rejected reason in rejected state information", () => {
  assert.match(reviewPageSource, /<RejectedReasonButton/);
  assert.match(reviewPageSource, /feedback=\{selectedCase\.review_feedback\}/);
  assert.match(reviewPageSource, /onClick=\{\(\) => openRejectDialog\(selectedCase\)\}/);
  assert.match(reviewPageSource, /function RejectedReasonButton/);
  assert.match(reviewPageSource, /feedback \|\| "未填写原因"/);
  assert.doesNotMatch(reviewPageSource, /ReviewBlock title="不采纳反馈"/);
  assert.doesNotMatch(reviewPageSource, /此用例尚未标记为不采纳。/);
  assert.doesNotMatch(reviewPageSource, /item\.review_feedback \|\| "未填写原因"/);
  assert.doesNotMatch(reviewPageSource, /\{item\.module \|\| "未分模块"\} \/ \{item\.priority \|\| "-"\}/);
  assert.doesNotMatch(
    reviewPageSource,
    /<ModulePath className="mt-2" moduleName=\{item\.module\} variant="compact" \/>/,
  );
  assert.match(reviewPageSource, /\{item\.priority\}/);
  assert.match(reviewPageSource, /priorityTone\(item\.priority\)/);
  assert.doesNotMatch(reviewPageSource, /statusTone\(item\.status\)/);
});

test("review detail header shows module path without status priority or time", () => {
  assert.match(reviewPageSource, /<ModulePath moduleName=\{selectedCase\.module\} \/>/);
  assert.match(reviewPageSource, /function ModulePath/);
  assert.match(reviewPageSource, /moduleSegments\(moduleName \|\| "未分模块"\)/);
  assert.doesNotMatch(reviewPageSource, /statusLabel\(selectedCase\.status\)/);
  assert.doesNotMatch(reviewPageSource, /statusTone\(selectedCase\.status\)/);
  assert.doesNotMatch(reviewPageSource, /selectedCase\.priority/);
  assert.doesNotMatch(reviewPageSource, /selectedCase\.updated_at/);
  assert.doesNotMatch(reviewPageSource, /formatDateTime/);
});

test("reject dialog collects optional feedback", () => {
  assert.match(reviewPageSource, /<DialogTitle(?: className="[^"]+")?>不采纳此用例<\/DialogTitle>/);
  assert.match(reviewPageSource, /不采纳原因/);
  assert.match(reviewPageSource, /跳过说明并不采纳/);
  assert.match(reviewPageSource, /保存不采纳/);
  assert.match(reviewPageSource, /placeholder="例如：步骤缺少异常分支、预期结果不可验证、与需求不一致"/);
});
