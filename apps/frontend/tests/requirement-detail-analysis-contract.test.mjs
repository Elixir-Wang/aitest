import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx", import.meta.url),
  "utf8",
);
const alertDialogSource = readFileSync(new URL("../src/components/ui/alert-dialog.tsx", import.meta.url), "utf8");

test("requirement detail exposes requirement understanding and clarification subtabs", () => {
  assert.match(pageSource, /<TabsTrigger value="analysis">需求分析<\/TabsTrigger>/);
  assert.match(pageSource, /<TabsTrigger value="final">最终需求<\/TabsTrigger>/);
  assert.match(pageSource, /<TabsTrigger value="analysis-report">需求分析<\/TabsTrigger>/);
  assert.match(pageSource, /<TabsTrigger value="clarification">待澄清<\/TabsTrigger>/);
  assert.doesNotMatch(pageSource, /<TabsTrigger value="quality">质量保障<\/TabsTrigger>/);
  assert.doesNotMatch(pageSource, /<TabsTrigger value="enhanced">初步需求<\/TabsTrigger>/);
  assert.doesNotMatch(pageSource, /<TabsTrigger value="preliminary">初步需求<\/TabsTrigger>/);
  assert.doesNotMatch(pageSource, /<TabsTrigger value="pending">待确认问题<\/TabsTrigger>/);
  assert.doesNotMatch(pageSource, /<TabsTrigger value="report">分析报告<\/TabsTrigger>/);
  assert.doesNotMatch(pageSource, />需求澄清</);
});

test("requirement analysis page consumes the canonical backend output fields", () => {
  assert.match(pageSource, /understanding_markdown: string/);
  assert.match(pageSource, /clarification_markdown: string/);
  assert.match(pageSource, /clarification_items: RequirementAnalysisQuestion\[\]/);
  assert.match(pageSource, /const analysisReportMarkdown = analysisResult\?\.output\.understanding_markdown \?\? ""/);
  assert.match(pageSource, /const clarificationMarkdown = analysisResult\?\.output\.clarification_markdown \?\? ""/);
  assert.match(
    pageSource,
    /const pendingAnalysisItems: RequirementAnalysisPendingItem\[\] = analysisResult\?\.output\.clarification_items \?\? \[\]/,
  );
  assert.doesNotMatch(pageSource, /analysis_report_markdown/);
  assert.doesNotMatch(pageSource, /preliminary_requirement_markdown/);
  assert.doesNotMatch(pageSource, /quality_assurance_report_markdown/);
  assert.doesNotMatch(pageSource, /clarification_questions/);
  assert.doesNotMatch(pageSource, /conflicts/);
  assert.doesNotMatch(pageSource, /quality_gate/);
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

test("primary source file row does not show an already-primary action", () => {
  assert.doesNotMatch(pageSource, /已是主需求/);
  assert.match(pageSource, /\.\.\.\(file\.file_role !== "primary"[\s\S]*\? \[[\s\S]*label: "设为主需求"/);
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

test("review action is presented inside the requirement analysis tab", () => {
  assert.match(pageSource, /toast\.success\("需求分析已提交，正在分析中"\)/);
  assert.match(pageSource, /<TabsContent value="analysis">[\s\S]*reviewLoading \? "分析中" : "需求分析"/);
  assert.match(pageSource, /function reviewPrimaryRequirement\(\) \{[\s\S]*if \(!currentPrimaryFile\)/);
  assert.match(pageSource, /currentPrimaryFile\.conversion_status/);
  assert.doesNotMatch(pageSource, /if \(selectedFile\?\.file_role !== "primary"\)/);
  assert.doesNotMatch(
    pageSource,
    /<TabsContent value="standard">[\s\S]*reviewLoading \? "分析中" : "需求分析"[\s\S]*<TabsContent value="analysis">/,
  );
  assert.match(pageSource, /setActiveTab\("analysis"\)/);
});

test("starting requirement analysis clears analysis and final tabs with confirmation when needed", () => {
  assert.match(pageSource, /hasFinalRequirementContent[\s\S]*setReviewClearConfirmOpen\(true\)/);
  assert.match(pageSource, /function clearRequirementAnalysisTabs\(\)/);
  assert.match(pageSource, /setAnalysisResult\(null\)/);
  assert.match(pageSource, /initial_markdown_content: ""/);
  assert.match(pageSource, /当前已有最终需求内容。重新执行需求分析会清空需求分析和最终需求\s+tab\s+内容/);
  assert.match(pageSource, /需求分析中，分析完成后会在这里展示需求分析报告。/);
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
  assert.match(pageSource, /toast\.success\("已转为最终需求"\)/);
  assert.match(pageSource, /setActiveTab\("final"\)/);
  assert.match(pageSource, /const canFinalizeRequirement = Boolean\(/);
  assert.match(pageSource, /\{canFinalizeRequirement \? \([\s\S]*转为最终需求[\s\S]*\) : null\}/);
  assert.match(pageSource, /尚未生成最终需求，请先在初步需求中点击“转为最终需求”。/);
});

test("clarification tab keeps the clickable answer structure", () => {
  assert.match(pageSource, /value="clarification"/);
  assert.match(pageSource, /isPendingItemOpen\(item\) \|\| Boolean\(pendingAnswerDrafts\[item\.id\]\)/);
  assert.match(pageSource, /saveClarificationAnswer\(item\)/);
  assert.match(pageSource, /saveClarificationAnswer\(item, "defer"\)/);
  assert.match(pageSource, /已处理项/);
  assert.match(
    pageSource,
    /<Dialog onOpenChange=\{setHandledClarificationDialogOpen\} open=\{handledClarificationDialogOpen\}>/,
  );
  assert.match(pageSource, /<DialogTitle>管理已处理<\/DialogTitle>/);
  assert.doesNotMatch(pageSource, /将条目移回待澄清列表后，在本页重新编辑并保存/);
  assert.match(pageSource, /setHandledClarificationFilter/);
  assert.match(pageSource, /filteredHandledPendingAnalysisItems\.map/);
  assert.match(pageSource, /setActiveRestoredPendingItemId\(item\.id\)/);
  assert.doesNotMatch(pageSource, /scrollIntoView/);
  assert.match(pageSource, />\s*移回编辑\s*</);
  assert.doesNotMatch(pageSource, /撤回已写入初步需求的补充内容/);
  assert.match(pageSource, /澄清：/);
  assert.doesNotMatch(pageSource, /暂未写入初步需求，移回后可选择推荐口径或填写自定义答复/);
  assert.match(pageSource, /保存答复/);
  assert.match(pageSource, /待澄清/);
  assert.doesNotMatch(pageSource, /待确认问题/);
  assert.doesNotMatch(pageSource, /修改中/);
});

test("clarification questions do not render prompt prefixes or guessed fallback answers", () => {
  assert.match(pageSource, /function normalizePendingQuestionText\(question: string\)/);
  assert.match(pageSource, /function normalizePendingDisplayText\(text: string\)/);
  assert.match(pageSource, /\.replace\(\/\^以下细节需要确认/);
  assert.match(pageSource, /const questionBody = normalizePendingQuestionText\(pendingItemQuestion\(item\)\)/);
  assert.match(
    pageSource,
    /const shouldShowQuestionBody =\s*Boolean\(questionBody\) &&\s*normalizePendingDisplayText\(questionBody\) !== normalizePendingDisplayText\(itemHeading\)/,
  );
  assert.match(pageSource, /\{shouldShowQuestionBody \? \(/);
  assert.doesNotMatch(pageSource, /<Badge variant="outline">\{pendingIssueTypeLabels\[issueType\]\}<\/Badge>/);
  assert.doesNotMatch(pageSource, /className="inline"[\s\S]*content=\{itemImpact\}/);
  assert.doesNotMatch(pageSource, /<MarkdownPreview[\s\S]*content=\{itemImpact\}/);
  assert.match(pageSource, /<span className="font-medium">影响：<\/span>/);
  assert.doesNotMatch(pageSource, /<span>影响<\/span>/);
  assert.match(pageSource, /return \[\];\s*\}/);
  assert.doesNotMatch(pageSource, /function inferPendingLikelyAnswers/);
  assert.doesNotMatch(pageSource, /候选答案 A/);
  assert.doesNotMatch(pageSource, /候选答案 B/);
  assert.doesNotMatch(pageSource, /安全指标：所有接口必须经过身份认证/);
});

test("handled clarification answers move behind the managed handled menu", () => {
  assert.match(
    pageSource,
    /const pendingAnalysisItems: RequirementAnalysisPendingItem\[\] = analysisResult\?\.output\.clarification_items \?\? \[\]/,
  );
  assert.match(pageSource, /const visiblePendingAnalysisItems = pendingAnalysisItems\.filter\(isPendingItemOpen\)/);
  assert.match(pageSource, /isPendingItemHandled\(item\) && !pendingAnswerDrafts\[item\.id\]/);
  assert.match(pageSource, /const filteredHandledPendingAnalysisItems = handledPendingAnalysisItems\.filter/);
  assert.match(
    pageSource,
    /function isPendingItemOpen\(item: RequirementAnalysisPendingItem\)[\s\S]*!\["applied", "not_applicable"\]\.includes\(pendingItemAnswerStatus\(item\)\)/,
  );
  assert.match(
    pageSource,
    /function isPendingItemHandled\(item: RequirementAnalysisPendingItem\)[\s\S]*\["applied", "not_applicable"\]\.includes\(pendingItemAnswerStatus\(item\)\)/,
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

test("handled clarification item heading stays aligned under the number column", () => {
  assert.match(pageSource, /className="absolute flex h-7 w-\[10\.5rem\] items-center gap-2"/);
  assert.match(pageSource, /className="block min-w-0 break-words text-foreground text-sm leading-6 indent-\[10\.5rem\]"/);
});

test("legacy query tabs route into requirement analysis", () => {
  assert.match(pageSource, /queryTab === "initial"[\s\S]*setActiveTab\("analysis"\)/);
  assert.match(pageSource, /queryTab === "clarification"[\s\S]*setActiveTab\("analysis"\)/);
});

test("requirement detail no longer accepts the removed source-files query tab", () => {
  assert.doesNotMatch(pageSource, /queryTab === "source-files"/);
});
