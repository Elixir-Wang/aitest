"use client";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { OneClipboard } from "@/components/ui/one-clipboard";
import { formatDateTime } from "@/lib/api-client";

export type RequirementVersionDetail = {
  id: string;
  document_id?: string;
  version_no: number;
  source_action: string;
  change_summary: string;
  diff_summary: string;
  created_by?: string;
  created_at: string;
  markdown_content?: string;
  is_current?: boolean;
};

const finalRequirementVersionActions = new Set(["requirement_analysis", "requirement_analysis_finalize"]);

export function isFinalRequirementVersion(version: RequirementVersionDetail) {
  return finalRequirementVersionActions.has(version.source_action);
}

export function requirementVersionActionLabel() {
  return "需求分析转为最终需求";
}

export function requirementVersionSummary(version: RequirementVersionDetail) {
  return version.diff_summary || version.change_summary || "-";
}

export function RequirementVersionDetailContent({ version }: { version: RequirementVersionDetail }) {
  const rows: Array<[string, string]> = [
    ["版本", `v${version.version_no}`],
    ["状态", version.is_current ? "当前生效版本" : "历史版本"],
    ["来源动作", requirementVersionActionLabel()],
    ["摘要", requirementVersionSummary(version)],
    ["创建时间", formatDateTime(version.created_at)],
  ];

  return (
    <>
      <div className="relative min-w-0 rounded-lg border p-4 pr-28 text-sm">
        <div className="absolute top-4 right-4">
          <OneClipboard copiedLabel="已复制" label="复制" text={serializeDetailRows(rows)} />
        </div>
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="font-medium text-sm">基础信息</h2>
        </div>
        <div className="grid min-w-0 gap-3">
          {rows.map(([label, value]) => (
            <div className="grid min-w-0 gap-1 md:grid-cols-[120px_minmax(0,1fr)] md:gap-4" key={label}>
              <span className="text-muted-foreground">{label}</span>
              <span className="min-w-0 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{value}</span>
            </div>
          ))}
        </div>
      </div>
      <section className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-medium text-sm">最终需求预览</h2>
          <OneClipboard copiedLabel="已复制" label="复制" text={version.markdown_content ?? ""} />
        </div>
        <MarkdownPreview
          className="requirement-document-preview"
          content={version.markdown_content ?? ""}
          emptyClassName="flex min-h-32 items-center justify-center text-center"
          emptyText="该版本暂无最终需求内容"
        />
      </section>
    </>
  );
}

function serializeDetailRows(rows: Array<[string, string]>) {
  return rows.map(([label, value]) => `${label}：${value}`).join("\n");
}
