import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx", import.meta.url),
  "utf8",
);
const alertDialogSource = readFileSync(new URL("../src/components/ui/alert-dialog.tsx", import.meta.url), "utf8");

test("requirement detail exposes the new requirement analysis tab contract", () => {
  assert.match(pageSource, /<TabsTrigger value="analysis">需求分析<\/TabsTrigger>/);
  assert.match(pageSource, /<TabsTrigger value="final">最终需求<\/TabsTrigger>/);
  assert.match(pageSource, /<TabsTrigger value="preliminary">初步需求<\/TabsTrigger>/);
  assert.match(pageSource, /<TabsTrigger value="pending">待确认问题<\/TabsTrigger>/);
  assert.doesNotMatch(pageSource, />需求澄清</);
});

test("file tabs share the selected file and default to primary only when none is selected", () => {
  assert.match(pageSource, /function defaultRequirementFileId\(files: SourceFile\[\]\)/);
  assert.match(pageSource, /file\.file_role === "primary"\)\?\.id \?\? files\[0\]\?\.id \?\? ""/);
  assert.match(
    pageSource,
    /setSelectedFileId\(\(current\) =>[\s\S]*data\.files\.some\(\(file\) => file\.id === current\)[\s\S]*defaultRequirementFileId\(data\.files\)/,
  );
  assert.match(pageSource, /function handleDetailTabChange\(nextTab: string\)/);
  assert.doesNotMatch(pageSource, /setSelectedFileId\(currentPrimaryFile\?\.id/);
  assert.match(pageSource, /<Tabs className="space-y-4" onValueChange=\{handleDetailTabChange\} value=\{activeTab\}>/);
  assert.match(
    pageSource,
    /function selectFileForTab\(fileId: string, tab: string\)[\s\S]*setSelectedFileId\(fileId\)/,
  );
});

test("original and standard file tabs show the selected file role badge", () => {
  assert.match(pageSource, /function FileRoleBadge\(\{ file \}: \{ file: SourceFile \}\)/);
  assert.match(pageSource, /file\.file_role === "primary"[\s\S]*fileRoleLabels\[file\.file_role\]/);
  assert.equal((pageSource.match(/<FileRoleBadge file=\{selectedFile\} \/>/g) ?? []).length, 2);
});

test("overview uses requirement progress steps instead of summary metric cards", () => {
  assert.match(pageSource, /<RequirementProgressSteps steps=\{requirementProgressSteps\} \/>/);
  assert.match(pageSource, /title: "原始需求"/);
  assert.match(pageSource, /title: "标准需求"/);
  assert.match(pageSource, /title: "需求分析"/);
  assert.match(pageSource, /title: "最终需求"/);
  assert.match(pageSource, /status === "running" \? <Loader2 className="size-4 animate-spin" \/> : null/);
  assert.match(
    pageSource,
    /const requirementReviewPassed = Boolean\(\s*analysisResult\?\.status && \["completed", "needs_clarification"\]\.includes\(analysisResult\.status\) && !isBlocked,\s*\)/,
  );
  assert.match(
    pageSource,
    /status: finalizingRequirement \? "running" : isFinalized && hasFinalRequirementContent \? "completed" : "upcoming"/,
  );
  assert.doesNotMatch(
    pageSource,
    /status: finalizingRequirement \? "running" : hasFinalRequirementContent \? "completed" : "upcoming"/,
  );
  assert.doesNotMatch(pageSource, /requirementProgressStatusLabels/);
  assert.doesNotMatch(pageSource, /step\.description/);
  assert.doesNotMatch(pageSource, /<SummaryMetric label="原始文件"/);
  assert.doesNotMatch(pageSource, /<SummaryMetric label="主需求文件"/);
  assert.doesNotMatch(pageSource, /<SummaryMetric label="辅助文件"/);
  assert.doesNotMatch(pageSource, /<SummaryMetric\s+label="最终需求"/);
});

test("review action is presented as requirement analysis", () => {
  assert.match(pageSource, /toast\.success\("需求分析已提交，正在分析中"\)/);
  assert.match(pageSource, /reviewLoading \? "分析中" : "需求分析"/);
  assert.match(pageSource, /setActiveTab\("analysis"\)/);
});

test("starting requirement analysis clears analysis and final tabs with confirmation when needed", () => {
  assert.match(pageSource, /hasFinalRequirementContent[\s\S]*setReviewClearConfirmOpen\(true\)/);
  assert.match(pageSource, /function clearRequirementAnalysisTabs\(\)/);
  assert.match(pageSource, /setAnalysisResult\(null\)/);
  assert.match(pageSource, /initial_markdown_content: ""/);
  assert.match(pageSource, /当前已有最终需求内容。重新执行需求分析会清空需求分析和最终需求\s+tab\s+内容/);
  assert.match(pageSource, /需求分析中，分析完成后会在这里展示初步需求。/);
  assert.match(pageSource, /需求分析中，当前最终需求已清空/);
});

test("requirement analysis confirmation uses the standard alert dialog", () => {
  assert.match(alertDialogSource, /function AlertDialogContent/);
  assert.match(alertDialogSource, /AlertDialogPrimitive\.Action/);
  assert.match(alertDialogSource, /sm:max-w-lg/);
  assert.match(alertDialogSource, /sm:justify-end/);
  assert.ok(pageSource.includes('from "@/components/ui/alert-dialog"'));
  assert.match(pageSource, /<AlertDialog onOpenChange=\{setReviewClearConfirmOpen\} open=\{reviewClearConfirmOpen\}>/);
  assert.match(pageSource, /className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary\/10/);
  assert.match(pageSource, /<FileSearch className="size-5" \/>/);
  assert.match(pageSource, /<AlertDialogFooter className="sm:justify-center">/);
  assert.doesNotMatch(pageSource, /分析任务提交后会在后台执行/);
  assert.match(pageSource, /开始需求分析？/);
});

test("preliminary requirement can be finalized into the final requirement tab", () => {
  assert.match(pageSource, />转为最终需求</);
  assert.match(pageSource, /\/analysis\/finalize/);
  assert.match(pageSource, /REQUIREMENT_ANALYSIS_CONFIRM_REQUIRED/);
  assert.match(pageSource, /toast\.success\("已转为最终需求"\)/);
  assert.match(pageSource, /setActiveTab\("final"\)/);
  assert.match(pageSource, /尚未生成最终需求，请先在初步需求中点击“转为最终需求”。/);
});

test("saved clarification answers stay visible while deferred questions are hidden", () => {
  assert.match(
    pageSource,
    /const pendingAnalysisItems: RequirementAnalysisPendingItem\[\] = \[\.\.\.clarificationQuestions, \.\.\.analysisConflicts\]\.filter\(\s*\(item\) => item\.answer\?\.apply_status !== "not_applicable",\s*\)/,
  );
  assert.doesNotMatch(pageSource, />当前答复</);
  assert.doesNotMatch(pageSource, />已保存答复</);
  assert.match(
    pageSource,
    /const savedCustomAnswer =\s*isAppliedAnswer && item\.answer\?\.answer_type === "custom" \? item\.answer\.answer_markdown : ""/,
  );
  assert.match(pageSource, /customAnswer: savedCustomAnswer/);
  assert.doesNotMatch(pageSource, /Boolean\(savedAnswer\)/);
  assert.doesNotMatch(pageSource, /\{item\.issue_type\}/);
  assert.doesNotMatch(pageSource, /clarificationAnswerStatusLabel/);
});

test("legacy query tabs route into requirement analysis", () => {
  assert.match(pageSource, /queryTab === "initial"[\s\S]*setActiveTab\("analysis"\)/);
  assert.match(pageSource, /queryTab === "clarification"[\s\S]*setActiveTab\("analysis"\)/);
});
