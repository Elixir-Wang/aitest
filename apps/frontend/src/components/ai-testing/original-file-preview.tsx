"use client";

import { useEffect, useRef, useState } from "react";

import dynamic from "next/dynamic";

import { renderAsync } from "docx-preview";
import { FileText, Loader2 } from "lucide-react";

import { IllustratedEmptyState } from "@/components/ai-testing/illustrated-empty-state";
import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";

const PdfCanvasPreview = dynamic(
  () => import("@/components/ai-testing/pdf-canvas-preview").then((mod) => mod.PdfCanvasPreview),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-[680px] items-center justify-center rounded-lg border bg-muted/20 text-muted-foreground text-sm">
        <Loader2 className="mr-2 size-4 animate-spin" />
        加载中
      </div>
    ),
  },
);

type OriginalPreview = {
  title: string;
  fileFormat: string;
  contentType: "text" | "file";
  content: string;
  objectUrl?: string;
};

type OriginalFilePreviewProps = {
  preview: OriginalPreview | null;
  selectedFilename?: string;
};

export function OriginalFilePreview({ preview, selectedFilename }: OriginalFilePreviewProps) {
  if (!preview) {
    return (
      <IllustratedEmptyState
        className="min-h-[360px] rounded-lg border border-dashed bg-muted/20"
        description="请从文件列表中选择一个原始文件进行预览。"
        title="暂无原始文件预览"
      />
    );
  }

  if (preview.contentType === "text") {
    if (isMarkdownFormat(preview.fileFormat)) {
      return (
        <MarkdownPreview
          className="requirement-document-preview"
          content={preview.content}
          emptyText="当前原始 Markdown 文件暂无可展示内容。"
        />
      );
    }

    return (
      <pre className="min-h-[360px] whitespace-pre-wrap rounded-lg border bg-background p-5 text-sm leading-7">
        {preview.content}
      </pre>
    );
  }

  const fileFormat = preview.fileFormat.toLowerCase();
  if (preview.objectUrl && fileFormat === "pdf") {
    return <PdfCanvasPreview objectUrl={preview.objectUrl} />;
  }
  if (preview.objectUrl && fileFormat === "docx") {
    return <DocxPreview objectUrl={preview.objectUrl} />;
  }

  const fallbackTitle = preview.title.trim() ? preview.title : (selectedFilename ?? "原始文件");

  return (
    <div className="flex min-h-[360px] flex-col items-center justify-center gap-3 rounded-lg border bg-muted/20 text-center text-sm">
      <FileText className="size-8 text-muted-foreground" />
      <div className="font-medium">{displayFilename(fallbackTitle)}</div>
      <div className="text-muted-foreground">当前文件暂不支持内嵌预览。</div>
    </div>
  );
}

function DocxPreview({ objectUrl }: { objectUrl: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const container = containerRef.current;
    if (!container) {
      return;
    }

    setLoading(true);
    setError("");
    container.replaceChildren();

    fetch(objectUrl)
      .then((response) => {
        if (!response.ok) {
          throw new Error("DOCX 文件读取失败");
        }
        return response.arrayBuffer();
      })
      .then((buffer) =>
        renderAsync(buffer, container, undefined, {
          className: "docx-preview-document",
          inWrapper: false,
          ignoreFonts: true,
          renderChanges: false,
          renderComments: false,
          trimXmlDeclaration: true,
          useBase64URL: true,
        }),
      )
      .catch(() => {
        if (!cancelled) {
          setError("DOCX 预览加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      container.replaceChildren();
    };
  }, [objectUrl]);

  return (
    <div className="overflow-hidden rounded-lg border bg-background">
      <div className="relative min-h-[680px] overflow-auto bg-muted/30 p-6">
        {loading ? (
          <div className="absolute inset-x-0 top-6 z-10 mx-auto flex w-fit items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm shadow-sm">
            <Loader2 className="size-4 animate-spin" />
            加载中
          </div>
        ) : null}
        {error ? (
          <div className="flex min-h-[620px] items-center justify-center text-muted-foreground text-sm">{error}</div>
        ) : (
          <div
            ref={containerRef}
            className="docx-preview mx-auto max-w-[900px] bg-white p-8 text-foreground shadow-sm ring-1 ring-border"
          />
        )}
      </div>
    </div>
  );
}

function displayFilename(filename: string) {
  return filename.replace(/^\d+[_-]/, "");
}

function isMarkdownFormat(fileFormat: string) {
  const normalized = fileFormat.trim().toLowerCase();
  return normalized === "md" || normalized === "markdown";
}
