import { Checkbox } from "@/components/ui/checkbox";
import type { PerformanceAnalysisChange } from "@/lib/api-client";

export function PerformanceAiConfigDiff({
  changes,
  applicableChangeIds = [],
  selectedChangeIds = [],
  onSelectionChange,
}: {
  changes: PerformanceAnalysisChange[];
  applicableChangeIds?: string[];
  selectedChangeIds?: string[];
  onSelectionChange?: (changeIds: string[]) => void;
}) {
  if (!changes.length) return null;
  return (
    <section>
      <h3 className="mb-2 font-semibold text-sm">修改建议</h3>
      <div className="space-y-3">
        {changes.map((change) => {
          const applicable = applicableChangeIds.includes(change.id);
          const selected = selectedChangeIds.includes(change.id);
          return (
            <article
              className={
                applicable ? "overflow-hidden rounded-lg border" : "overflow-hidden rounded-lg border opacity-60"
              }
              key={change.id}
            >
              <div className="flex items-center justify-between gap-3 border-b bg-muted/30 px-3 py-2">
                <div className="flex min-w-0 items-center gap-2">
                  {onSelectionChange ? (
                    <Checkbox
                      checked={selected}
                      disabled={!applicable}
                      aria-label={`选择修复 ${change.target}`}
                      onCheckedChange={(checked) =>
                        onSelectionChange(
                          checked
                            ? [...selectedChangeIds, change.id]
                            : selectedChangeIds.filter((id) => id !== change.id),
                        )
                      }
                    />
                  ) : null}
                  <span className="truncate font-mono text-xs">{change.target}</span>
                </div>
                <span className="text-[10px] text-muted-foreground">风险：{riskLabel(change.risk_level)}</span>
              </div>
              <div className="grid gap-px bg-border md:grid-cols-2">
                <DiffValue label="修改前" tone="before" value={change.before} />
                <DiffValue label="建议值" tone="after" value={change.after} />
              </div>
              <p className="border-t px-3 py-2 text-muted-foreground text-xs">{change.reason}</p>
              {!applicable ? (
                <p className="border-t px-3 py-2 text-amber-700 text-xs">该建议涉及非结构化源码，不能直接自动应用。</p>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function DiffValue({ label, value, tone }: { label: string; value: unknown; tone: "before" | "after" }) {
  return (
    <div
      className={
        tone === "before" ? "bg-red-50/70 p-3 dark:bg-red-950/15" : "bg-emerald-50/70 p-3 dark:bg-emerald-950/15"
      }
    >
      <div className="mb-1 text-[10px] text-muted-foreground uppercase tracking-wide">{label}</div>
      <pre className="overflow-auto whitespace-pre-wrap break-all font-mono text-xs">
        {JSON.stringify(value ?? null, null, 2)}
      </pre>
    </div>
  );
}

function riskLabel(value: PerformanceAnalysisChange["risk_level"]) {
  return value === "high" ? "高" : value === "medium" ? "中" : "低";
}
