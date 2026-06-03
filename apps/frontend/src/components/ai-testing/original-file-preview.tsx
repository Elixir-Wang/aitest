"use client";

import { useEffect, useRef, useState } from "react";

import { renderAsync } from "docx-preview";
import { FileText, Loader2, Minus, Plus, RotateCw } from "lucide-react";
import { GlobalWorkerOptions, getDocument, type PDFDocumentProxy, type RenderTask } from "pdfjs-dist";
import "pdfjs-dist/web/pdf_viewer.css";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";

GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.mjs", import.meta.url).toString();

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
      <div className="flex min-h-[360px] items-center justify-center rounded-lg border border-dashed bg-muted/20 text-muted-foreground text-sm">
        请选择一个原始文件。
      </div>
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

function PdfCanvasPreview({ objectUrl }: { objectUrl: string }) {
  const pagesRef = useRef<HTMLDivElement | null>(null);
  const renderTasksRef = useRef<RenderTask[]>([]);
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [scale, setScale] = useState(1);
  const [containerWidth, setContainerWidth] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const pagesElement = pagesRef.current;
    if (!pagesElement) {
      return;
    }

    const updateContainerWidth = () => {
      setContainerWidth(Math.max(0, pagesElement.clientWidth));
    };
    updateContainerWidth();

    const observer = new ResizeObserver(updateContainerWidth);
    observer.observe(pagesElement);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setPdf(null);
    setPageCount(0);
    pagesRef.current?.replaceChildren();

    const task = getDocument(objectUrl);
    task.promise
      .then((document) => {
        if (cancelled) {
          void document.destroy();
          return;
        }
        setPdf(document);
        setPageCount(document.numPages);
      })
      .catch(() => {
        if (!cancelled) {
          setError("PDF 预览加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      task.destroy();
    };
  }, [objectUrl]);

  useEffect(() => {
    const pagesElement = pagesRef.current;
    if (!pdf || !pagesElement || !containerWidth) {
      return;
    }

    let cancelled = false;
    renderTasksRef.current.forEach((task) => {
      task.cancel();
    });
    renderTasksRef.current = [];
    pagesElement.replaceChildren();
    setLoading(true);
    setError("");

    const renderPages = async () => {
      const availableWidth = Math.max(320, containerWidth - 8);

      for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
        if (cancelled) {
          return;
        }

        const page = await pdf.getPage(pageNumber);
        if (cancelled) {
          return;
        }

        const baseViewport = page.getViewport({ scale: 1 });
        const fitScale = availableWidth / baseViewport.width;
        const displayScale = Math.max(0.1, fitScale * scale);
        const viewport = page.getViewport({
          scale: displayScale * window.devicePixelRatio,
        });
        const displayViewport = page.getViewport({ scale: displayScale });
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");
        if (!context) {
          throw new Error("当前浏览器不支持 PDF 画布预览");
        }

        canvas.width = viewport.width;
        canvas.height = viewport.height;
        canvas.style.width = `${displayViewport.width}px`;
        canvas.style.height = `${displayViewport.height}px`;
        canvas.className = "block bg-white shadow-sm ring-1 ring-border";
        context.setTransform(1, 0, 0, 1, 0, 0);
        context.clearRect(0, 0, canvas.width, canvas.height);
        pagesElement.appendChild(canvas);

        const renderTask = page.render({
          canvas,
          canvasContext: context,
          viewport,
        });
        renderTasksRef.current.push(renderTask);
        await renderTask.promise;
      }
    };

    renderPages()
      .catch((renderError) => {
        if (!cancelled && renderError?.name !== "RenderingCancelledException") {
          setError(renderError?.message === "当前浏览器不支持 PDF 画布预览" ? renderError.message : "PDF 页面渲染失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      renderTasksRef.current.forEach((task) => {
        task.cancel();
      });
      renderTasksRef.current = [];
    };
  }, [containerWidth, pdf, scale]);

  return (
    <div className="overflow-hidden rounded-lg border bg-background">
      <div className="flex flex-wrap items-center justify-end gap-3 border-b bg-muted/20 px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <div className="w-20 text-center text-sm tabular-nums">{pageCount || "-"} 页</div>
          <Button
            disabled={scale <= 0.7 || loading}
            onClick={() => setScale((current) => Math.max(0.7, Number((current - 0.1).toFixed(1))))}
            size="icon"
            type="button"
            variant="ghost"
          >
            <Minus className="size-4" />
          </Button>
          <div className="w-24 px-1">
            <Slider
              disabled={loading}
              max={1.8}
              min={0.7}
              onValueChange={([value]) => setScale(Number(value.toFixed(1)))}
              step={0.1}
              value={[scale]}
            />
          </div>
          <Button
            disabled={scale >= 1.8 || loading}
            onClick={() => setScale((current) => Math.min(1.8, Number((current + 0.1).toFixed(1))))}
            size="icon"
            type="button"
            variant="ghost"
          >
            <Plus className="size-4" />
          </Button>
          <div className="w-20 text-right text-muted-foreground text-xs tabular-nums">
            适宽 {Math.round(scale * 100)}%
          </div>
          <Button disabled={loading} onClick={() => setScale(1)} size="icon" type="button" variant="ghost">
            <RotateCw className="size-4" />
          </Button>
        </div>
      </div>
      <div className="relative min-h-[680px] overflow-auto bg-muted/30 px-2 py-4 sm:px-4">
        {loading ? (
          <div className="absolute inset-x-0 top-6 z-10 mx-auto flex w-fit items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm shadow-sm">
            <Loader2 className="size-4 animate-spin" />
            加载中
          </div>
        ) : null}
        {error ? (
          <div className="flex min-h-[620px] items-center justify-center text-muted-foreground text-sm">{error}</div>
        ) : (
          <div ref={pagesRef} className="flex min-h-[620px] flex-col items-center gap-4" />
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
