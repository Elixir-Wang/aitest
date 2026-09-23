import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const reportSource = readFileSync(
  new URL("../src/components/ai-testing/performance-testing/performance-analysis-report.tsx", import.meta.url),
  "utf8",
);
const reportPageSource = readFileSync(
  new URL(
    "../src/app/(main)/projects/[projectId]/performance-tests/[testId]/runs/[runId]/analysis/[analysisId]/page.tsx",
    import.meta.url,
  ),
  "utf8",
);
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

test("performance analysis report omits the Locust console return button", () => {
  assert.doesNotMatch(reportSource, /返回 Locust 控制台/);
  assert.doesNotMatch(reportSource, /<ArrowLeft/);
});

test("performance analysis report breadcrumbs include report center, performance test, and test name", () => {
  assert.match(reportPageSource, /getPerformanceTest/);
  assert.match(reportPageSource, /moduleBreadcrumbs\(\s*"reports"/);
  assert.match(reportPageSource, /reportBreadcrumbLabel = testName \? `\$\{testName\} - 性能智能分析报告`/);
  assert.doesNotMatch(reportPageSource, /label: "性能测试"/);
});

test("performance analysis API exposes generation metadata", () => {
  assert.match(apiClientSource, /generation_mode: "" \| "ai_primary" \| "ai_repaired" \| "deterministic_fallback"/);
  assert.match(apiClientSource, /analysis_attempts: Array<Record<string, unknown>>/);
  assert.match(apiClientSource, /generation_warnings\?: Array<\{/);
});

test("fallback report displays warning and supports reanalysis", () => {
  assert.match(reportSource, /analysis\.generation_mode === "deterministic_fallback"/);
  assert.match(reportSource, /当前为基础性能报告/);
  assert.match(reportSource, /AI 根因分析及修复建议未生成/);
  assert.match(reportSource, /createPerformanceAnalysis/);
  assert.match(reportSource, /重新分析/);
});

test("fallback report hides AI findings and recommendations", () => {
  assert.match(reportSource, /!isFallback && findings\.length \? \(/);
  assert.match(reportSource, /!isFallback && recommendations\.length \? \(/);
  assert.match(reportSource, /优化与复测建议/);
  assert.match(reportSource, /诊断发现/);
});

test("performance report keeps quality and scope compact without a runtime metadata section", () => {
  assert.doesNotMatch(reportSource, /分析 v\{analysis\.analysis_version\}/);
  assert.doesNotMatch(reportSource, /指标 v\{metric\.schema_version/);
  assert.doesNotMatch(reportSource, /证据覆盖/);
  assert.doesNotMatch(reportSource, /title="测试有效性"/);
  assert.doesNotMatch(reportSource, /report\.capacity_summary/);
  assert.doesNotMatch(reportSource, /生成信息/);
  assert.doesNotMatch(reportSource, /来源指纹/);
  assert.match(reportSource, /buildScopeItems\(testScope\)/);
  assert.match(reportSource, /qualityLabel\(quality\.status\)/);
});

test("performance report follows the concise decision-first structure", () => {
  const headings = ["性能结论", "性能目标", "接口表现", "运行趋势", "风险与边界", "优化与复测建议"];
  let previous = -1;
  for (const heading of headings) {
    const index = reportSource.indexOf(heading);
    assert.ok(index > previous, `${heading} should appear after the previous report section`);
    previous = index;
  }
  assert.match(reportSource, /label="P99 响应时间"/);
  assert.match(reportSource, /id="core-metrics-heading"/);
  assert.match(reportSource, /max-w-\[90rem\]/);
  assert.match(reportSource, /endpointDisplayName\(endpoint\.method, endpoint\.name\)/);
  assert.match(reportSource, /percentageValue\(endpoint\.request_share\)\}%/);
  assert.match(reportSource, /verdictAccentClass\(verdict\)/);
  assert.doesNotMatch(reportSource, /measurementWindowLabel/);
  assert.doesNotMatch(reportSource, /统计窗口约/);
  assert.doesNotMatch(reportSource, /未设置独立预热/);
  assert.doesNotMatch(reportSource, /title="数据限制"/);
  assert.match(reportSource, /未配置验收目标，仅作为观察指标/);
});

test("performance report places core metrics in the wider left column and scope details on the right", () => {
  assert.match(reportSource, /xl:grid-cols-\[minmax\(34rem,1\.15fr\)_minmax\(22rem,0\.85fr\)\]/);
  assert.ok(
    reportSource.indexOf('id="core-metrics-heading"') < reportSource.indexOf("scopeItems.length"),
    "core metrics should appear before the right-side scope details",
  );
});

test("performance report presents scope details as a balanced two-column configuration matrix", () => {
  assert.match(reportSource, /id="test-config-heading"/);
  assert.match(reportSource, /aria-labelledby="test-config-heading"/);
  assert.match(reportSource, /flex h-full flex-col justify-center/);
  assert.match(reportSource, /mt-4 grid grid-cols-2 gap-x-8/);
  assert.match(reportSource, /className="border-t py-3"/);
  assert.match(reportSource, /<Gauge className="size-3\.5" \/>/);
  assert.doesNotMatch(reportSource, /grid grid-cols-2 gap-x-5 gap-y-4 sm:grid-cols-3/);
});

test("performance verdict glyph sits beside the verdict headline instead of the section label", () => {
  const labelIndex = reportSource.indexOf("<span>性能结论</span>");
  const glyphIndex = reportSource.indexOf("<VerdictGlyph verdict={verdict} />");
  const headlineIndex = reportSource.indexOf('<h1 className="font-semibold text-3xl tabular-nums">');
  assert.ok(labelIndex < glyphIndex, "the verdict glyph should appear after the section label");
  assert.ok(glyphIndex < headlineIndex, "the verdict glyph should sit immediately before the verdict headline");
  assert.match(reportSource, /className="mt-3 flex items-center gap-2"/);
  assert.match(reportSource, /size-6 shrink-0/);
  assert.match(reportSource, /text-emerald-600/);
});

test("performance report renders endpoint metrics and degrades without inventing them", () => {
  assert.match(reportSource, /metric\.endpoint_metrics/);
  assert.match(reportSource, /endpoint\.request_share/);
  assert.match(reportSource, /endpoint\.p95_response_time_ms/);
  assert.match(reportSource, /endpoint\.p99_response_time_ms/);
  assert.match(reportSource, /未使用全局指标推算接口结果/);
});

test("performance report separates SSE event metrics from HTTP response metrics", () => {
  assert.match(reportSource, /metric\.sse_metrics\?\.metrics/);
  assert.match(reportSource, /title="SSE 事件指标"/);
  assert.match(reportSource, /item\.missing_count/);
  assert.match(reportSource, /item\.p95_ms/);
  assert.match(reportSource, /测量文件达到大小上限/);
  assert.match(reportSource, /JSON 格式错误/);
});

test("performance report hides empty analytical sections", () => {
  assert.match(reportSource, /objectives\.length \? \(/);
  assert.match(reportSource, /stageAnalysis\.length > 1 \? \(/);
  assert.match(reportSource, /showCapacityAnalysis \? \(/);
  assert.match(reportSource, /failureAnalysis\.length \? \(/);
  assert.match(reportSource, /findings\.length \? \(/);
  assert.match(reportSource, /recommendations\.length \? \(/);
});

test("performance report compresses AI findings and recommendations", () => {
  assert.doesNotMatch(reportSource, /置信度 \{Math\.round/);
  assert.doesNotMatch(reportSource, /recommendation\.expected_effect/);
  assert.match(reportSource, /\.slice\(0, 3\)/);
  assert.doesNotMatch(reportSource, /evidenceGapLabel/);
  assert.doesNotMatch(reportSource, /title="分析与行动"/);
  assert.match(reportSource, /divide-y rounded-lg border bg-card px-4 sm:px-5/);
  assert.match(reportSource, /severityBadgeClass/);
  assert.match(reportSource, /text-muted-foreground text-xs leading-5/);
  assert.match(reportSource, /recommendationAction\(recommendation\.action\)/);
  assert.doesNotMatch(reportSource, /sm:text-base/);
  assert.doesNotMatch(reportSource, /sm:grid-cols-\[5\.5rem_minmax\(0,1fr\)\]/);
  assert.match(reportSource, /normalizedFindingSeverity/);
  assert.match(reportSource, /displayFindingStatement\(finding, testScope\.users\)/);
  assert.match(reportSource, /本次仅验证了 \$\{loadScope\}下的表现/);
  assert.match(reportSource, /can_claim_stable_capacity\|knee_point/);
  assert.match(reportSource, /normalizedRecommendationPriority/);
  assert.match(reportSource, /目标\|指标\|验收\|测试有效性/);
  assert.match(reportSource, /达成\|合格\|passed/);
});

test("performance report humanizes internal capacity fields in historical recommendation verification", () => {
  const verificationHelper = reportSource.slice(
    reportSource.indexOf("function recommendationVerification"),
    reportSource.indexOf("function isSupportedRecommendation"),
  );
  assert.match(verificationHelper, /can_claim_stable_capacity\|knee_point/);
  assert.match(verificationHelper, /已验证的最大稳定负载/);
  assert.match(verificationHelper, /P95、P99、失败率与吞吐量/);
});

test("zero failure rate does not prevent capacity-boundary humanization", () => {
  const capacityHelper = reportSource.slice(
    reportSource.indexOf("function isCapacityBoundaryFinding"),
    reportSource.indexOf("function displayFindingStatement"),
  );
  assert.doesNotMatch(capacityHelper, /\/失败\|退化/);
  assert.match(capacityHelper, /请求失败\|失败请求/);
});

test("performance trend chart separates latency from throughput and retains the console curve style", () => {
  assert.match(reportSource, /dataKey="sampled_at"/);
  assert.match(reportSource, /响应延迟/);
  assert.match(reportSource, /吞吐量/);
  assert.match(reportSource, /核心指标/);
  assert.match(reportSource, /观察请求响应速度是否稳定/);
  assert.match(reportSource, /观察服务处理能力是否稳定/);
  assert.doesNotMatch(reportSource, /P95 衡量绝大多数请求体验/);
  assert.doesNotMatch(reportSource, /趋势按 Locust 采样记录展示/);
  assert.match(reportSource, /hasP50Series \? "grid-cols-3" : "grid-cols-2"/);
  assert.match(reportSource, /min-w-\[5\.25rem\] text-left/);
  assert.match(reportSource, /xl:grid-cols-2/);
  assert.doesNotMatch(reportSource, /yAxisId=/);
  assert.equal(reportSource.match(/type="monotone"/g)?.length, 4);
  assert.match(reportSource, /formatTrendValue/);
  assert.equal(reportSource.match(/<TrendTooltip \/>/g)?.length, 2);
  assert.match(reportSource, /backgroundColor: "var\(--popover\)"/);
  assert.match(reportSource, /border: "1px solid var\(--border\)"/);
  assert.match(reportSource, /stroke: "var\(--muted-foreground\)"/);
});
