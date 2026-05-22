"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

type MarkdownPreviewProps = {
  className?: string;
  content: string;
  emptyText?: string;
  indentParagraphs?: boolean;
};

export function MarkdownPreview({
  className,
  content,
  emptyText = "当前版本暂无可展示内容。",
  indentParagraphs = false,
}: MarkdownPreviewProps) {
  const markdown = content.trim();

  if (!markdown) {
    return <div className={cn("markdown-preview markdown-preview-empty", className)}>{emptyText}</div>;
  }

  return (
    <article className={cn("markdown-preview", className)}>
      <ReactMarkdown
        components={{
          p: ({ children }) => <p style={indentParagraphs ? { textIndent: "2em" } : undefined}>{children}</p>,
        }}
        remarkPlugins={[remarkGfm]}
      >
        {markdown}
      </ReactMarkdown>
    </article>
  );
}
