import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const panelSource = readFileSync(
  new URL("../src/components/ai-testing/test-points-panel.tsx", import.meta.url),
  "utf8",
);
const listSource = readFileSync(new URL("../src/components/ai-testing/test-points-list.tsx", import.meta.url), "utf8");
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

test("test points actions live in the list toolbar without a second outer toolbar", () => {
  assert.match(panelSource, /<ShellSection>[\s\S]*?<ListToolbar[\s\S]*?actions=\{/);
  assert.doesNotMatch(panelSource, /<h2 className="font-medium text-sm">测试点<\/h2>/);
  assert.match(panelSource, /title="测试点列表"/);
  assert.doesNotMatch(listSource, /<ShellSection>/);
  assert.doesNotMatch(listSource, /<ListToolbar/);
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

test("test point titles open the detail dialog", () => {
  assert.match(listSource, /onClick=\{\(\) => openDetail\(point\)\}[\s\S]*?\{point\.title\}/);
});

test("pagination is spaced from the table and page size updates visible rows", () => {
  assert.match(listSource, /className="mt-4 flex flex-col gap-3 text-sm/);
  assert.match(listSource, /setRows\(paginatedPoints\)/);
});

test("test point detail dialog overrides the shared desktop width", () => {
  assert.match(listSource, /style=\{\{ maxWidth: "56rem" \}\}/);
  assert.match(listSource, /w-\[calc\(100%-2rem\)\]/);
});

test("test point detail header shows badges then title without a public point key", () => {
  assert.match(
    listSource,
    /<div className="flex[^"]*">[\s\S]*?<Badge[^>]*>[\s\S]*?<Badge[^>]*>[\s\S]*?<DialogTitle[^>]*>\{point\.title\}<\/DialogTitle>[\s\S]*?<\/div>/,
  );
  assert.doesNotMatch(listSource, />ID:<\/span>/);
  assert.doesNotMatch(listSource, /point\.point_key/);
  assert.doesNotMatch(apiClientSource, /\n\s*point_key: string;/);
});
