import { AlertTriangle, ChevronDown } from "lucide-react";

import type { ApiTestPointCoverageSummary } from "@/lib/api-client";

type TestPointCoverageSummaryProps = {
  coverage: ApiTestPointCoverageSummary;
};

export function TestPointCoverageSummary({ coverage }: TestPointCoverageSummaryProps) {
  const incomplete = coverage.status === "incomplete" || coverage.status === "invalid";
  const visibleMissingObligations = coverage.missing_obligations.slice(0, 5);
  const remainingMissingObligations = coverage.missing_obligations.slice(5);

  if (!incomplete) {
    return null;
  }

  return (
    <div className="mt-3 border-amber-200 border-t pt-3 text-amber-900 text-sm">
      <div className="flex items-center gap-2 font-medium">
        <AlertTriangle className="size-4" />
        当前测试要点未生成完整
      </div>
      <div className="mt-2">
        需求义务：已覆盖 {coverage.covered_obligation_count}/{coverage.obligation_count}，补生成轮次：
        {coverage.supplement_round}
      </div>
      <div className="mt-1">未覆盖：{coverage.missing_obligations.length}</div>
      {coverage.missing_obligations.length > 0 ? (
        <div className="mt-2">
          <ObligationList obligations={visibleMissingObligations} />
          {remainingMissingObligations.length > 0 ? (
            <details className="group mt-2">
              <summary className="flex w-fit cursor-pointer list-none items-center gap-1 font-medium hover:text-amber-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/50">
                <ChevronDown className="size-4 transition-transform group-open:rotate-180" />
                <span className="group-open:hidden">展开全部（另有 {remainingMissingObligations.length} 条）</span>
                <span className="hidden group-open:inline">收起</span>
              </summary>
              <ObligationList className="mt-2" obligations={remainingMissingObligations} />
            </details>
          ) : null}
        </div>
      ) : null}
      {coverage.unsupported_assumptions.length > 0 ? (
        <div className="mt-2">PRD 外推断：{coverage.unsupported_assumptions.join("；")}</div>
      ) : null}
    </div>
  );
}

function ObligationList({
  obligations,
  className = "",
}: {
  obligations: ApiTestPointCoverageSummary["missing_obligations"];
  className?: string;
}) {
  return (
    <ul className={`${className} space-y-1`}>
      {obligations.map((obligation) => (
        <li key={`${obligation.obligation_key}:${obligation.source_section}:${obligation.statement}`}>
          {obligation.obligation_key} {obligation.statement}（{obligation.source_section}）
        </li>
      ))}
    </ul>
  );
}
