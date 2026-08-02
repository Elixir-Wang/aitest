import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const panelSource = readFileSync(
  new URL("../src/components/ai-testing/test-points-panel.tsx", import.meta.url),
  "utf8",
);
const listSource = readFileSync(new URL("../src/components/ai-testing/test-points-list.tsx", import.meta.url), "utf8");
const mindMapSource = readFileSync(
  new URL("../src/components/ai-testing/test-point-mind-map.tsx", import.meta.url),
  "utf8",
);
const mindMapTreeSource = readFileSync(
  new URL("../src/components/ai-testing/mind-map-tree.tsx", import.meta.url),
  "utf8",
);
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");
const requirementPageSource = readFileSync(
  new URL("../src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx", import.meta.url),
  "utf8",
);

test("test points prerequisite empty state reuses the illustrated empty-state treatment", () => {
  assert.match(
    panelSource,
    /import \{ IllustratedEmptyState \} from "@\/components\/ai-testing\/illustrated-empty-state"/,
  );
  assert.equal((panelSource.match(/<IllustratedEmptyState/g) ?? []).length, 2);
  assert.match(panelSource, /title="暂无测试点"/);
  assert.match(panelSource, /请先在需求分析中点击“转为最终需求”。/);
});

test("test point generation keeps the list area visible", () => {
  assert.match(panelSource, /\{!hasPoints \? \(/);
  assert.match(panelSource, /\{hasPoints \? \(/);
  assert.doesNotMatch(panelSource, /测试点生成中\.\.\./);
  assert.doesNotMatch(panelSource, /hasPoints && !regenerating/);
});

test("regenerating test points clears the current list immediately", () => {
  assert.match(panelSource, /const run = await generateTestPoints\(projectId, documentId\)/);
  assert.match(panelSource, /setData\(\(current\) =>[\s\S]*?points: \[\][\s\S]*?markdown_content: ""/);
});

test("test points tab does not expose generation errors inline", () => {
  assert.doesNotMatch(panelSource, /data\.run\?\.status === "failed"/);
  assert.doesNotMatch(panelSource, /data\.run\.error_message/);
  assert.doesNotMatch(panelSource, />测试点生成失败</);
});

test("test points panel reports refreshed generation state to its container", () => {
  assert.match(panelSource, /onOverviewChange\?: \(overview: ApiTestPointOverview\) => void/);
  assert.match(panelSource, /setData\(overview\);\s*onOverviewChange\?\.\(overview\);/);
});

test("test points actions mount beside the active top-level tab", () => {
  assert.match(panelSource, /import \{ createPortal \} from "react-dom"/);
  assert.match(panelSource, /actionContainer\?: HTMLElement \| null/);
  assert.match(panelSource, /createPortal\(testPointActions, actionContainer\)/);
  assert.match(requirementPageSource, /const \[testPointActionsContainer, setTestPointActionsContainer\]/);
  assert.match(requirementPageSource, /activeTab === "test-points"/);
  assert.match(requirementPageSource, /ref=\{setTestPointActionsContainer\}/);
  assert.match(requirementPageSource, /actionContainer=\{testPointActionsContainer\}/);
  assert.match(panelSource, /!hasPoints && canEdit/);
  assert.match(panelSource, /生成测试点/);
  assert.doesNotMatch(panelSource, /<h2 className="font-medium text-sm">测试点<\/h2>/);
  assert.match(panelSource, /title="测试点列表"/);
  assert.doesNotMatch(listSource, /<ShellSection>/);
  assert.doesNotMatch(listSource, /<ListToolbar/);
});

test("test point mind map aligns its bottom edge with the viewport", () => {
  assert.match(panelSource, /const mindMapContainerRef = useRef<HTMLDivElement>\(null\)/);
  assert.match(panelSource, /window\.innerHeight - container\.getBoundingClientRect\(\)\.top - 16/);
  assert.match(
    panelSource,
    /<div className="flex min-h-\[32rem\] flex-none rounded-lg border" ref=\{mindMapContainerRef\}>\s*<TestPointMindMap/,
  );
  assert.doesNotMatch(
    panelSource,
    /<div className="flex min-h-\[32rem\] flex-1 rounded-lg border" ref=\{mindMapContainerRef\}>/,
  );
  assert.doesNotMatch(panelSource, /h-\[calc\(100dvh-15rem\)\]/);
});

test("test points list omits the priority summary footer", () => {
  assert.doesNotMatch(listSource, /P0 × \{p0Count\}/);
  assert.doesNotMatch(listSource, /P1 × \{p1Count\}/);
  assert.doesNotMatch(listSource, /P2 × \{p2Count\}/);
});

test("test points tab does not add an outer shell section", () => {
  assert.match(requirementPageSource, /<TabsContent value="test-points">\s*<TestPointsPanel[^>]*\/>\s*<\/TabsContent>/);
});

test("test points list uses the requested title and column order", () => {
  assert.match(panelSource, /title="测试点列表"/);
  assert.match(listSource, /<TableHead[^>]*>标题<\/TableHead>[\s\S]*?<TableHead[^>]*>优先级<\/TableHead>/);
  assert.doesNotMatch(listSource, /<TableHead[^>]*>来源<\/TableHead>/);
});

test("test points list does not expose point details", () => {
  const apiTestPointType = apiClientSource.match(/export type ApiTestPoint = \{([\s\S]*?)\n\};/)?.[1] ?? "";

  assert.match(listSource, /<span className="block max-w-full truncate">\{point\.title\}<\/span>/);
  assert.doesNotMatch(listSource, /TestPointDetailDialog/);
  assert.doesNotMatch(listSource, /openDetail/);
  assert.doesNotMatch(listSource, /查看详情/);
  assert.doesNotMatch(listSource, /point\.description/);
  assert.doesNotMatch(listSource, /point\.preconditions/);
  assert.doesNotMatch(listSource, /point\.verification_points/);
  assert.doesNotMatch(listSource, /point\.source_refs/);
  assert.doesNotMatch(listSource, /point\.notes/);
  assert.match(apiTestPointType, /id: string;/);
  assert.match(apiTestPointType, /title: string;/);
  assert.match(apiTestPointType, /module: string;/);
  assert.match(apiTestPointType, /priority: string;/);
  assert.match(apiTestPointType, /description: string;/);
  assert.match(apiTestPointType, /preconditions: string\[\];/);
  assert.match(apiTestPointType, /verification_points: string\[\];/);
});

test("selecting a test point in the mind map keeps the mind map visible", () => {
  const handler = panelSource.match(/function handleSelectPoint\(pointId: string\) \{([\s\S]*?)\n {2}\}/)?.[1] ?? "";

  assert.match(handler, /setSelectedPointId\(pointId\)/);
  assert.doesNotMatch(handler, /setViewMode\("list"\)/);
});

test("editing a test point in the mind map persists and updates the shared list data", () => {
  assert.match(panelSource, /method: "PATCH"/);
  assert.match(panelSource, /body: JSON\.stringify\(\{ title \}\)/);
  assert.match(
    panelSource,
    /points: current\.points\.map\(\(point\) => \(point\.id === pointId \? \{ \.\.\.point, title \} : point\)\)/,
  );
  assert.match(panelSource, /editable=\{canEdit\}/);
  assert.match(panelSource, /onEditPoint=\{handleEditPoint\}/);
  assert.match(mindMapSource, /editable=\{rest\.editable\}/);
  assert.match(mindMapSource, /onEdit=\{onEditPoint\}/);
  assert.match(mindMapTreeSource, /\[&_\.smm-quick-create-child-btn\]:hidden/);
});

test("pagination is spaced from the table and page size updates visible rows", () => {
  assert.match(listSource, /const PAGE_SIZE = 15;/);
  assert.match(listSource, /className="mt-4 flex flex-col gap-3 text-sm/);
  assert.match(listSource, /setRows\(paginatedPoints\)/);
});

test("test points list does not expose a public point key", () => {
  assert.doesNotMatch(listSource, />ID:<\/span>/);
  assert.doesNotMatch(listSource, /point\.point_key/);
  assert.doesNotMatch(apiClientSource, /\n\s*point_key: string;/);
});
