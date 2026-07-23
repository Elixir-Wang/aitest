import { AlertTriangle } from "lucide-react";

import type { ApiTestPointCoverageSummary } from "@/lib/api-client";

type TestPointCoverageSummaryProps = {
  coverage: ApiTestPointCoverageSummary;
};

export function TestPointCoverageSummary({ coverage }: TestPointCoverageSummaryProps) {
  const incomplete = coverage.status === "incomplete" || coverage.status === "invalid";

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
        <ul className="mt-2 space-y-1">
          {coverage.missing_obligations.map((obligation) => (
            <li key={`${obligation.obligation_key}:${obligation.source_section}:${obligation.statement}`}>
              {obligation.obligation_key} {obligation.statement}（{obligation.source_section}）
            </li>
          ))}
        </ul>
      ) : null}
      {coverage.unsupported_assumptions.length > 0 ? (
        <div className="mt-2">PRD 外推断：{coverage.unsupported_assumptions.join("；")}</div>
      ) : null}
    </div>
  );
}
