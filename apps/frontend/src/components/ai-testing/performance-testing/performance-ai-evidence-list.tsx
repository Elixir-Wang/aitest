import type { PerformanceAnalysisEvidence } from "@/lib/api-client";

export function PerformanceAiEvidenceList({ evidence }: { evidence: PerformanceAnalysisEvidence[] }) {
  const observed = evidence.filter((item) => item.level === "observed" || item.level === "derived");
  const inferred = evidence.filter((item) => item.level === "inferred");

  return (
    <div className="space-y-5">
      <EvidenceGroup emptyText="暂无直接证据" items={observed} title="已证实证据" />
      <EvidenceGroup emptyText="暂无推断建议" items={inferred} title="推断与建议" />
    </div>
  );
}

function EvidenceGroup({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: PerformanceAnalysisEvidence[];
  emptyText: string;
}) {
  return (
    <section>
      <h3 className="mb-2 font-semibold text-sm">{title}</h3>
      {items.length ? (
        <div className="space-y-2">
          {items.map((item) => (
            <article
              className="rounded-lg border p-3"
              key={`${item.source}-${item.title}-${item.reference || item.detail}`}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium text-sm">{item.title}</span>
                <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                  {item.source}
                </span>
              </div>
              <p className="mt-1 whitespace-pre-wrap text-muted-foreground text-xs leading-5">{item.detail}</p>
              {item.reference ? (
                <p className="mt-2 break-all font-mono text-[10px] text-muted-foreground">{item.reference}</p>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground text-xs">{emptyText}</p>
      )}
    </section>
  );
}
