"use client";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";

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
  return (
    <MarkdownPreview
      className="requirement-document-preview"
      content={version.markdown_content ?? ""}
      emptyClassName="flex min-h-32 items-center justify-center text-center"
      emptyText="该版本暂无最终需求内容"
    />
  );
}
