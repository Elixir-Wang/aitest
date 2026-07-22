import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const pageSource = readFileSync(new URL("../src/app/(main)/automation/api/page.tsx", import.meta.url), "utf8");
const projectPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/automation/api/page.tsx", import.meta.url),
  "utf8",
);
const caseDetailPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/automation/api/cases/[caseId]/page.tsx", import.meta.url),
  "utf8",
);
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const sidebarSource = readFileSync(new URL("../src/navigation/sidebar/sidebar-items.ts", import.meta.url), "utf8");
const taskRunningIndicatorSource = readFileSync(
  new URL("../src/components/ai-testing/task-running-indicator.tsx", import.meta.url),
  "utf8",
);

test("api automation interface-set list uses requested create and count copy", () => {
  assert.match(pageSource, /createLabel="新建接口集"/);
  assert.match(pageSource, /<DialogTitle>\{editingSet \? "修改接口集" : "新建接口集"\}<\/DialogTitle>/);
  assert.match(pageSource, /<TableHead>接口数量<\/TableHead>/);
  assert.match(pageSource, /<TableCell>\{item\.endpoint_count\}<\/TableCell>/);
  assert.doesNotMatch(pageSource, /<TableCell>\{item\.case_count\}<\/TableCell>/);
  assert.doesNotMatch(pageSource, /createLabel="新建接口用例集"/);
  assert.doesNotMatch(pageSource, /<DialogTitle>新建接口用例集<\/DialogTitle>/);
  assert.doesNotMatch(pageSource, /<TableHead>用例数量<\/TableHead>/);
});

test("api automation interface-set list removes project and status columns", () => {
  assert.doesNotMatch(pageSource, /<TableHead>项目<\/TableHead>/);
  assert.doesNotMatch(pageSource, /<TableHead>状态<\/TableHead>/);
  assert.doesNotMatch(pageSource, /projectNameById\.get\(item\.project_id\) \?\? item\.project_id/);
  assert.doesNotMatch(pageSource, /<Badge variant="secondary">\{statusLabel\(item\.status\)\}<\/Badge>/);
});

test("api automation interface-set name and row actions support entering and editing", () => {
  assert.match(
    pageSource,
    /<Link\s+className="block truncate hover:underline"\s+href=\{`\/projects\/\$\{item\.project_id\}\/automation\/api\?set=\$\{item\.id\}`\}\s+title=\{item\.name\}/,
  );
  assert.match(pageSource, /href: `\/projects\/\$\{item\.project_id\}\/automation\/api\?set=\$\{item\.id\}`/);
  assert.doesNotMatch(pageSource, /router\.push\(`\/projects\/\$\{item\.project_id\}\/automation\/api/);
  assert.match(pageSource, /label: "修改"/);
  assert.match(pageSource, /icon: Pencil/);
  assert.match(pageSource, /onSelect: \(\) => openEditDialog\(item\)/);
  assert.doesNotMatch(pageSource, /label: "删除"/);
  assert.doesNotMatch(pageSource, /icon: Trash2/);
  assert.match(pageSource, /<DialogTitle>\{editingSet \? "修改接口集" : "新建接口集"\}<\/DialogTitle>/);
});

test("api client exposes api automation case-set update contract", () => {
  assert.match(apiClientSource, /export function updateApiAutomationCaseSet/);
  assert.match(apiClientSource, /`\/projects\/\$\{projectId\}\/api-case-sets\/\$\{setId\}`/);
  assert.match(apiClientSource, /method: "PATCH"/);
});

test("sidebar api automation entry opens the aggregate list", () => {
  assert.match(sidebarSource, /title: "接口自动化",\s*url: "\/automation\/api",\s*icon: TestTubeDiagonal,/);
  assert.doesNotMatch(sidebarSource, /title: "接口自动化",\s*url: "\/projects\/:projectId\/automation\/api"/);
});

test("project api automation breadcrumb uses selected interface-set name", () => {
  assert.match(projectPageSource, /const searchParams = useSearchParams\(\);/);
  assert.match(projectPageSource, /const selectedCaseSetId = searchParams\.get\("set"\);/);
  assert.match(projectPageSource, /listApiAutomationCaseSets\(projectId\)/);
  assert.match(projectPageSource, /\.\.\.\(selectedCaseSet \? \[\{ label: selectedCaseSet\.name \}\] : \[\]\)/);
  assert.doesNotMatch(projectPageSource, /\{ label: selectedCaseSet\?\.name \?\? projectName \}/);
});

test("project api automation endpoint detail keeps debug send and removes join-generation action", () => {
  assert.match(projectPageSource, /debugApiAutomationEndpoint/);
  assert.match(projectPageSource, /openEndpointDebugDialog\(activeEndpoint\)/);
  assert.match(projectPageSource, /<DialogTitle>接口调试<\/DialogTitle>/);
  assert.match(projectPageSource, /通过后端代理发送请求/);
  assert.match(projectPageSource, /handleDebugSend/);
  assert.doesNotMatch(projectPageSource, /cookies: \{\}/);
  assert.doesNotMatch(projectPageSource, /toggleEndpoint\(activeEndpoint\.id\)/);
  assert.doesNotMatch(projectPageSource, /加入生成/);
  assert.doesNotMatch(projectPageSource, /deleteEndpoints\(\[activeEndpoint\.id\]\)/);
});

test("project api automation debug dialog keeps results visible with compact request body editor", () => {
  assert.match(
    projectPageSource,
    /grid max-h-\[calc\(100vh-2rem\)\] grid-rows-\[auto_minmax\(0,1fr\)_auto\] overflow-hidden/,
  );
  assert.match(projectPageSource, /className="max-h-64 min-h-0 overflow-y-auto font-mono text-xs"/);
  assert.match(projectPageSource, /rows=\{getTextareaRows\(debugForm\.bodyText, 3, 12\)\}/);
  assert.match(projectPageSource, /function getTextareaRows/);
  assert.doesNotMatch(projectPageSource, /className="min-h-44 font-mono text-xs"/);
});

test("project api automation debug dialog environment select keeps global select styling", () => {
  assert.match(
    projectPageSource,
    /<SelectTrigger className="w-full lg:w-56">\s*<SelectValue placeholder="选择接口环境" \/>/,
  );
  assert.match(projectPageSource, /<SelectContent position="popper">/);
  assert.doesNotMatch(projectPageSource, /<SelectTrigger className="h-9 w-full bg-background lg:w-56">/);
});

test("project api automation endpoint groups are collapsible with count badges", () => {
  assert.match(projectPageSource, /aria-label="搜索 method、path、tag"/);
  assert.match(projectPageSource, /placeholder="搜索"/);
  assert.match(projectPageSource, /className="h-8 bg-background pl-9"/);
  assert.match(
    projectPageSource,
    /删除\{selectedEndpointAssetIds\.length > 0 \? ` \(\$\{selectedEndpointAssetIds\.length\}\)` : ""\}/,
  );
  assert.match(projectPageSource, /expandedEndpointGroups/);
  assert.match(projectPageSource, /toggleEndpointGroup\(group\)/);
  assert.match(projectPageSource, /!\s*expandedEndpointGroups\.includes\(group\)/);
  assert.match(projectPageSource, /searchText\.trim\(\) \? false/);
  assert.match(projectPageSource, /aria-label=\{`\$\{group\} 分组/);
  assert.match(projectPageSource, /ChevronDown/);
  assert.match(projectPageSource, /bg-sky-100[\s\S]*text-sky-700/);
  assert.match(projectPageSource, /\{rows\.length\}/);
});

test("project api automation uses compact filled HTTP method badges", () => {
  assert.match(
    projectPageSource,
    /inline-flex h-5 items-center justify-center rounded-md px-1\.5 font-bold text-\[11px\] leading-none/,
  );
  assert.match(projectPageSource, /POST: "bg-blue-100 text-blue-700/);
  assert.doesNotMatch(projectPageSource, /inline-flex h-6 min-w-14/);
});

test("project api automation exposes interface environment after interface assets", () => {
  assert.match(
    projectPageSource,
    /const tabs = \["接口资产", "接口环境", "接口用例", "测试脚本", "运行记录", "场景编排"\];/,
  );
  assert.match(projectPageSource, /activeTab === "接口环境"/);
  assert.match(projectPageSource, /activeTab === "接口用例"/);
  assert.match(projectPageSource, /<ShellSection>/);
  assert.match(projectPageSource, /<ListToolbar/);
  assert.match(projectPageSource, /<Table>/);
  assert.match(projectPageSource, /<RowActions/);
  assert.match(projectPageSource, /新建接口环境/);
  assert.match(projectPageSource, /authTypeOptions/);
  assert.match(projectPageSource, /默认请求头（JSON）/);
  assert.doesNotMatch(projectPageSource, /<CardTitle className="text-base">环境详情<\/CardTitle>/);
});

test("project api automation case tab shows generated endpoints and case table without status filters", () => {
  assert.doesNotMatch(projectPageSource, /apiCaseDetailOpen/);
  assert.match(
    projectPageSource,
    /const \[selectedApiCaseIds, setSelectedApiCaseIds\] = useState<string\[\]>\(\[\]\);/,
  );
  assert.match(projectPageSource, /const \[activeApiCaseEndpointId, setActiveApiCaseEndpointId\] = useState\(""\);/);
  assert.match(
    projectPageSource,
    /const \[selectedApiCaseEndpointIds, setSelectedApiCaseEndpointIds\] = useState<string\[\]>\(\[\]\);/,
  );
  assert.match(projectPageSource, /const apiCaseCountByEndpointId = useMemo/);
  assert.match(projectPageSource, /const apiCaseEndpoints = useMemo/);
  assert.match(projectPageSource, /const groupedApiCaseEndpoints = useMemo/);
  assert.match(projectPageSource, /testCase\.endpoint_id !== activeApiCaseEndpoint\.id/);
  assert.doesNotMatch(projectPageSource, /ApiCaseSummaryStrip/);
  assert.doesNotMatch(projectPageSource, /apiCaseSummaryCounts/);
  assert.match(projectPageSource, /activeTab === "接口用例" && \(\s*<div className="grid min-h-\[28rem\]/);
  assert.match(projectPageSource, /aria-label="选择当前接口列表"/);
  assert.doesNotMatch(projectPageSource, /已生成用例接口/);
  assert.doesNotMatch(projectPageSource, /仅显示已从接口资产生成过用例的接口/);
  assert.match(projectPageSource, /toggleVisibleApiCaseEndpoints\(Boolean\(checked\)\)/);
  assert.match(projectPageSource, /deleteApiCaseEndpoints\(selectedApiCaseEndpointIds\)/);
  assert.match(projectPageSource, /disabled=\{busy \|\| selectedApiCaseEndpointIds\.length === 0\}/);
  assert.match(
    projectPageSource,
    /删除\{selectedApiCaseEndpointIds\.length > 0 \? ` \(\$\{selectedApiCaseEndpointIds\.length\}\)` : ""\}/,
  );
  assert.match(projectPageSource, /Object\.entries\(groupedApiCaseEndpoints\)/);
  assert.match(projectPageSource, /toggleApiCaseEndpoint\(endpoint\.id, Boolean\(checked\)\)/);
  assert.match(projectPageSource, /toggleEndpointAssetGroup\(groupEndpointIds, Boolean\(checked\)\)/);
  assert.match(projectPageSource, /aria-label={`选择 \$\{group\} 分组的全部接口`}/);
  assert.match(
    projectPageSource,
    /aria-label={`选择 \$\{group\} 分组的全部接口`}\s+checked=\{[\s\S]*?className="after:inset-0"/,
  );
  assert.match(projectPageSource, /toggleApiCaseEndpointGroupSelection\(groupEndpointIds, Boolean\(checked\)\)/);
  assert.match(projectPageSource, /aria-label={`选择 \$\{group\} 分组的全部接口用例`}/);
  assert.match(
    projectPageSource,
    /aria-label={`选择 \$\{group\} 分组的全部接口用例`}\s+checked=\{[\s\S]*?className="after:inset-0"/,
  );
  assert.match(projectPageSource, /setActiveApiCaseEndpointId\(endpoint\.id\)/);
  assert.match(
    projectPageSource,
    /\$\{activeApiCaseEndpoint\.summary \|\| activeApiCaseEndpoint\.path\} · \$\{activeApiCaseEndpoint\.path\}/,
  );
  assert.match(projectPageSource, /<RefreshCw className="size-4" \/>/);
  assert.match(projectPageSource, /placeholder="搜索用例名称"/);
  assert.match(projectPageSource, /onBatchDelete=\{\(\) => deleteApiTestCases\(selectedApiCaseIds\)\}/);
  assert.match(projectPageSource, /aria-label="选择全部接口用例"/);
  assert.match(projectPageSource, /<TableHead>用例名称<\/TableHead>/);
  assert.doesNotMatch(projectPageSource, /<TableHead>接口<\/TableHead>/);
  assert.doesNotMatch(projectPageSource, /<TableHead>状态<\/TableHead>/);
  assert.doesNotMatch(projectPageSource, /apiCaseFilters/);
  assert.doesNotMatch(projectPageSource, /ApiCaseStatusBadge/);
  assert.doesNotMatch(projectPageSource, /ApiCaseEndpointPath/);
  assert.doesNotMatch(projectPageSource, /可执行/);
  assert.doesNotMatch(projectPageSource, /待补充/);
  assert.doesNotMatch(projectPageSource, /草稿/);
  assert.match(projectPageSource, /<TableHead className="w-16">操作<\/TableHead>/);
  assert.match(projectPageSource, /label: "删除"/);
  assert.match(projectPageSource, /deleteApiTestCases\(\[item\.id\]\)/);
  assert.match(projectPageSource, /onClick=\{handleGenerateScripts\}/);
  assert.match(projectPageSource, /const router = useRouter\(\);/);
  assert.match(projectPageSource, /onClick=\{\(\) => router\.push\(apiCaseDetailHref\(projectId, item\.id\)\)\}/);
  assert.match(projectPageSource, /onSelect: \(\) => router\.push\(apiCaseDetailHref\(projectId, item\.id\)\)/);
  assert.doesNotMatch(projectPageSource, /window\.open\(apiCaseDetailHref/);
  assert.doesNotMatch(projectPageSource, /href=\{apiCaseDetailHref\(projectId, item\.id\)\}/);
  assert.doesNotMatch(projectPageSource, /target="_blank"/);
  assert.doesNotMatch(projectPageSource, /setApiCaseDetailOpen\(true\);/);
  assert.doesNotMatch(projectPageSource, /<Dialog onOpenChange=\{setApiCaseDetailOpen\} open=\{apiCaseDetailOpen\}>/);
  assert.doesNotMatch(projectPageSource, /ApiCaseAssetPanel/);
});

test("project api automation generates project scripts from selected interfaces", () => {
  assert.match(projectPageSource, /const \[scripts, setScripts\] = useState<ApiAutomationScript\[]>\(\[\]\)/);
  assert.match(projectPageSource, /const endpointIds = selectedApiCaseEndpointIds/);
  assert.match(projectPageSource, /generateApiAutomationScripts\(projectId/);
  assert.match(projectPageSource, /endpoint_ids: endpointIds/);
  assert.match(projectPageSource, /listApiAutomationScripts\(projectId\)/);
  assert.match(projectPageSource, /handleRun\(runTargetScriptIds\)/);
  assert.match(projectPageSource, /删除[\s\S]*执行脚本/);
  assert.doesNotMatch(projectPageSource, /getApiAutomationScriptFiles/);
  assert.doesNotMatch(projectPageSource, /scriptCodeOpen/);
  assert.doesNotMatch(projectPageSource, /查看代码/);
  assert.doesNotMatch(projectPageSource, /selectedEnvironment \? "修改环境配置" : "新建接口环境"/);
  assert.doesNotMatch(projectPageSource, /前置检查 \{scriptReadinessChecks/);
  assert.doesNotMatch(projectPageSource, /runTargetCaseCount/);
  assert.doesNotMatch(apiClientSource, /ApiAutomationScriptFile/);
  assert.doesNotMatch(apiClientSource, /getApiAutomationScriptFiles/);
});

test("project api automation refreshes case list when generation run completes", () => {
  assert.match(projectPageSource, /const API_GENERATION_ACTIVE_STATUSES = new Set\(\["queued", "running"\]\);/);
  assert.match(projectPageSource, /const applyGenerationRun = useCallback\(\(nextRun: ApiAutomationGenerationRun\) =>/);
  assert.match(projectPageSource, /setApiTestCases\(nextRun\.test_cases\)/);
  assert.match(projectPageSource, /const latest = await getApiAutomationGenerationRun\(projectId, generationRun\.id\)/);
  assert.match(projectPageSource, /applyGenerationRun\(latest\)/);
});

test("project api automation generate button spinner is scoped to generation requests", () => {
  assert.match(projectPageSource, /const \[generateBusy, setGenerateBusy\] = useState\(false\);/);
  assert.match(projectPageSource, /setGenerateBusy\(true\);[\s\S]*generateApiAutomationTestCases/);
  assert.match(projectPageSource, /finally \{[\s\S]*setGenerateBusy\(false\);[\s\S]*setBusy\(false\);/);
  assert.match(projectPageSource, /generateBusy \? <Loader2 className="size-4 animate-spin" \/> : <WandSparkles/);
  assert.doesNotMatch(projectPageSource, /busy \? <Loader2 className="size-4 animate-spin" \/> : <WandSparkles/);
});

test("project api automation uses selected environment for generate scripts and runs", () => {
  assert.match(projectPageSource, /const \[selectedEnvironmentId, setSelectedEnvironmentId\] = useState\(""\);/);
  assert.match(projectPageSource, /api_environment_id: selectedEnvironment\?\.id \?\? null/);
  assert.doesNotMatch(projectPageSource, /api_environment_id: environments\[0\]\?\.id \?\? null/);
  assert.match(apiClientSource, /export function updateApiAutomationEnvironment/);
  assert.match(apiClientSource, /export function deleteApiAutomationEnvironment/);
  assert.match(apiClientSource, /export function deleteApiAutomationTestCase/);
  assert.match(apiClientSource, /export function deleteApiAutomationScript/);
  assert.match(apiClientSource, /`\/projects\/\$\{projectId\}\/api-test-cases\/\$\{caseId\}`/);
  assert.match(apiClientSource, /`\/projects\/\$\{projectId\}\/api-scripts\/\$\{scriptId\}`/);
  assert.match(projectPageSource, /async function handleDeleteScripts\(scriptIds: string\[\] = selectedScriptIds\)/);
  assert.match(projectPageSource, /onClick=\{\(\) => handleRun\(runTargetScriptIds\)\}/);
  assert.match(projectPageSource, /onClick=\{\(\) => handleDeleteScripts\(selectedScriptIds\)\}/);
  assert.doesNotMatch(projectPageSource, /从接口用例生成脚本/);
});

test("project api automation uses a script execution workspace", () => {
  assert.match(projectPageSource, /xl:grid-cols-\[360px_minmax\(0,1fr\)\]/);
  assert.match(projectPageSource, /<div className="font-semibold text-sm">接口脚本<\/div>/);
  assert.doesNotMatch(projectPageSource, /\{scripts\.length\} 个接口，已选择 \{selectedScriptIds\.length\}/);
  assert.doesNotMatch(projectPageSource, /\{script\.case_count\} 条用例/);
  assert.doesNotMatch(projectPageSource, /\["runs", "执行历史"\]/);
  assert.match(projectPageSource, />运行配置<\/h3>/);
  assert.match(projectPageSource, />执行前检查<\/h3>/);
  assert.match(projectPageSource, />前置条件<\/h3>/);
  assert.match(projectPageSource, /运行所需配置已准备完成。/);
  assert.doesNotMatch(projectPageSource, /scriptDetailTab/);
});

test("project api automation run records use a persistent paged history list", () => {
  assert.match(apiClientSource, /export function listApiAutomationRuns/);
  assert.match(apiClientSource, /`\/projects\/\$\{projectId\}\/api-runs\$\{query \? `\?\$\{query\}` : ""\}`/);
  assert.match(projectPageSource, /const \[runs, setRuns\] = useState<ApiAutomationRun\[]>\(\[\]\)/);
  assert.match(projectPageSource, /<TableHead>运行 ID<\/TableHead>/);
  assert.match(projectPageSource, /<TableHead>执行环境<\/TableHead>/);
  assert.match(projectPageSource, /<TableHead>测试接口数量<\/TableHead>/);
  assert.match(projectPageSource, /<TableHead>执行结果<\/TableHead>/);
  assert.match(projectPageSource, /<TableHead>执行时间<\/TableHead>/);
  assert.doesNotMatch(projectPageSource, /<TableHead>执行范围<\/TableHead>/);
  assert.doesNotMatch(projectPageSource, /<TableHead>执行人<\/TableHead>/);
  assert.match(projectPageSource, /label=\{`运行记录 \$\{item\.id\} 操作`\}/);
  assert.match(projectPageSource, /暂无运行记录。请前往测试脚本选择脚本并执行。/);
  assert.match(projectPageSource, /runs\.some\(\(item\) => API_RUN_ACTIVE_STATUSES\.has\(item\.status\)\)/);
});

test("project api automation run detail supports deep links, logs, reports, and reruns", () => {
  assert.match(projectPageSource, /const selectedRunId = searchParams\.get\("run"\)/);
  assert.match(projectPageSource, /getApiAutomationRunLogs\(projectId, nextRun\.id\)/);
  assert.match(projectPageSource, /getApiAutomationRunReport\(projectId, run\.id\)/);
  assert.match(projectPageSource, /按原配置重新执行/);
  assert.match(projectPageSource, /handleRun\(run\.script_ids, run\.api_environment_id \?\? ""\)/);
});

test("project api automation case detail shows structured QA review sections", () => {
  assert.match(apiClientSource, /coverage: string;/);
  assert.match(apiClientSource, /preconditions: string\[\];/);
  assert.match(apiClientSource, /test_data: Record<string, unknown>;/);
  assert.match(apiClientSource, /test_description: string;/);
  assert.doesNotMatch(apiClientSource, /export type ApiAutomationTestCase = \{[\s\S]*?\n\s+tags: string\[\];/);
  assert.doesNotMatch(apiClientSource, /expected: Record<string, unknown>;/);
  assert.doesNotMatch(apiClientSource, /data_origin: Record<string, unknown>;/);
  assert.match(apiClientSource, /export function getApiAutomationTestCase/);
  assert.match(caseDetailPageSource, /getApiAutomationTestCase\(projectId, caseId\)/);
  assert.doesNotMatch(caseDetailPageSource, /testCase\.tags|>标签</);
  assert.doesNotMatch(caseDetailPageSource, /<ReviewBlock title="基础信息">/);
  assert.match(caseDetailPageSource, /testCase\.preconditions\.length > 0/);
  assert.match(caseDetailPageSource, /title="请求信息"/);
  assert.match(caseDetailPageSource, /<ReviewBlock title="测试数据">/);
  assert.match(caseDetailPageSource, /测试描述/);
  assert.match(caseDetailPageSource, /testCase\.notes\.trim\(\)/);
  assert.match(caseDetailPageSource, /生成说明/);
  assert.match(caseDetailPageSource, /\{testCase\.notes\}/);
  assert.match(caseDetailPageSource, /<ReviewBlock icon=\{<Code2 className="size-4" \/>\} title="请求信息">/);
  assert.match(caseDetailPageSource, /<ReviewBlock icon=\{<ShieldAlert className="size-4" \/>\} title="验证规则">/);
  assert.match(caseDetailPageSource, /renderApiCaseRequest/);
  assert.match(caseDetailPageSource, /renderApiCaseTestData/);
  assert.match(caseDetailPageSource, /hasValue\(assertion\.expected\)/);
  assert.doesNotMatch(caseDetailPageSource, /actions=\{/);
  assert.match(caseDetailPageSource, /formatApiCaseCoverage\(testCase\.coverage\)/);
  assert.match(caseDetailPageSource, /negative: "负向"/);
  assert.match(
    caseDetailPageSource,
    /<h1 className="mr-1 max-w-3xl break-words font-semibold text-2xl tracking-tight">\{testCase\.title\}<\/h1>/,
  );
  assert.match(caseDetailPageSource, /href=\{`\/projects\/\$\{projectId\}\/automation\/api\?tab=cases`\}/);
  assert.match(caseDetailPageSource, /<section className="rounded-xl border bg-card/);
  assert.match(caseDetailPageSource, /dark:border-sky-900\/70 dark:bg-sky-950\/30/);
  assert.match(caseDetailPageSource, /dark:border-emerald-900\/70 dark:bg-emerald-950\/30/);
  assert.doesNotMatch(caseDetailPageSource, /bg-white p-4/);
  assert.doesNotMatch(caseDetailPageSource, /text-\[#101828\]/);
  assert.match(projectPageSource, /function tabFromSearchParam\(value: string \| null\)/);
  assert.match(projectPageSource, /if \(value === "cases"\) return "接口用例";/);
  assert.match(projectPageSource, /useState\(\(\) => tabFromSearchParam\(searchParams\.get\("tab"\)\)\)/);
});

test("project api automation script workspace summarizes real environment configuration", () => {
  assert.match(projectPageSource, /id="script-run-environment"/);
  assert.match(projectPageSource, /selectedEnvironment\.timeout_seconds/);
  assert.match(projectPageSource, /Object\.keys\(selectedEnvironment\.variables\)\.length/);
  assert.match(projectPageSource, /Object\.keys\(selectedEnvironment\.default_headers\)\.length/);
  assert.doesNotMatch(projectPageSource, /selectedEnvironment \? "修改环境配置" : "新建接口环境"/);
});

test("project api automation script workspace summarizes preconditions without repeating cases", () => {
  assert.match(projectPageSource, /const activeScriptPreconditions = useMemo/);
  assert.match(projectPageSource, /testCase\.preconditions\.map/);
  assert.match(projectPageSource, /来自关联接口用例/);
  assert.doesNotMatch(projectPageSource, /selectedScriptCaseIds/);
  assert.doesNotMatch(projectPageSource, /scriptCaseSearchText/);
  assert.doesNotMatch(projectPageSource, /选择全部脚本关联用例/);
});

test("project api automation generation and execution notify the top running task indicator", () => {
  assert.match(taskRunningIndicatorSource, /"api_automation_generation_run"/);
  assert.match(taskRunningIndicatorSource, /"api_automation_run"/);
  assert.match(projectPageSource, /import \{ notifyAiTaskStarted \} from "@\/lib\/ai-task-events";/);
  assert.match(projectPageSource, /toast\.success\("接口用例生成任务已创建"\);\s*notifyAiTaskStarted\(\);/);
  assert.match(projectPageSource, /toast\.success\("执行任务已创建"\);\s*notifyAiTaskStarted\(\);/);
});

test("project api automation endpoint schema detail uses compact badges and response header", () => {
  assert.match(projectPageSource, /function ContentTypeBadge/);
  assert.match(projectPageSource, /rounded-md border bg-muted\/40 px-2 py-1 font-mono/);
  assert.match(projectPageSource, /md:grid-cols-\[minmax\(220px,1\.1fr\)_64px_64px_56px_minmax\(220px,1\.4fr\)\]/);
  assert.match(projectPageSource, /border-b bg-muted\/20 px-4 py-3/);
  assert.match(projectPageSource, /<ContentTypeBadge key=\{contentType\} value=\{contentType\} \/>/);
});

test("project api automation endpoint responses switch by status code", () => {
  assert.match(
    projectPageSource,
    /const preferredStatus = entries\.find\(\(\[status\]\) => status\.startsWith\("2"\)\)\?\.\[0\] \?\? entries\[0\]\?\.\[0\] \?\? "";/,
  );
  assert.match(projectPageSource, /<Select onValueChange=\{setSelectedStatus\} value=\{activeStatus\}>/);
  assert.match(projectPageSource, /<SelectItem key=\{status\} value=\{status\}>\s*\{status\}\s*<\/SelectItem>/);
  assert.match(projectPageSource, /const activeEntry = entries\.find\(\(\[status\]\) => status === activeStatus\);/);
  assert.match(projectPageSource, /activeEntry \? \(/);
  assert.match(
    projectPageSource,
    /<div className="flex flex-wrap items-center justify-between gap-3 border-b pb-2">[\s\S]*<h3 className="font-semibold text-lg">响应信息<\/h3>[\s\S]*<Select onValueChange=\{setSelectedStatus\} value=\{activeStatus\}>[\s\S]*contentEntries\.map/,
  );
  assert.match(projectPageSource, /<p className="text-muted-foreground text-sm">\{responseDescription\}<\/p>/);
  assert.doesNotMatch(projectPageSource, /border-b bg-muted\/20 px-4 py-3/);
});
