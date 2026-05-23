"use client";

import { useEffect, useRef, useState } from "react";

import { ChevronLeft, ChevronRight, FileText, Loader2, Minus, Plus, RotateCw } from "lucide-react";
import mammoth from "mammoth";
import { GlobalWorkerOptions, getDocument, type PDFDocumentProxy, type RenderTask } from "pdfjs-dist";
import "pdfjs-dist/web/pdf_viewer.css";

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
    return (
      <pre className="min-h-[360px] whitespace-pre-wrap rounded-lg border bg-background p-5 text-sm leading-7">
        {preview.content}
      </pre>
    );
  }

  const fileFormat = preview.fileFormat.toLowerCase();
  if (preview.objectUrl && fileFormat === "pdf") {
    return <PdfCanvasPreview objectUrl={preview.objectUrl} title={preview.title} />;
  }

  if (preview.objectUrl && ["doc", "docx"].includes(fileFormat)) {
    return <DocxPreview objectUrl={preview.objectUrl} title={preview.title} />;
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

function PdfCanvasPreview({ objectUrl, title }: { objectUrl: string; title: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const renderTaskRef = useRef<RenderTask | null>(null);
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [pageCount, setPageCount] = useState(0);
  const [scale, setScale] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setPdf(null);
    setPageNumber(1);

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
    if (!pdf || !canvasRef.current) {
      return;
    }

    let cancelled = false;
    const canvas = canvasRef.current;
    const context = canvas.getContext("2d");
    if (!context) {
      setError("当前浏览器不支持 PDF 画布预览");
      return;
    }

    renderTaskRef.current?.cancel();
    setLoading(true);
    setError("");

    pdf
      .getPage(pageNumber)
      .then((page) => {
        if (cancelled) {
          return;
        }
        const viewport = page.getViewport({ scale: scale * window.devicePixelRatio });
        const displayViewport = page.getViewport({ scale });
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        canvas.style.width = `${displayViewport.width}px`;
        canvas.style.height = `${displayViewport.height}px`;
        context.setTransform(1, 0, 0, 1, 0, 0);
        context.clearRect(0, 0, canvas.width, canvas.height);
        renderTaskRef.current = page.render({ canvas, canvasContext: context, viewport });
        return renderTaskRef.current.promise;
      })
      .catch((renderError) => {
        if (!cancelled && renderError?.name !== "RenderingCancelledException") {
          setError("PDF 页面渲染失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      renderTaskRef.current?.cancel();
    };
  }, [pageNumber, pdf, scale]);

  return (
    <div className="overflow-hidden rounded-lg border bg-background">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b bg-muted/20 px-3 py-2">
        <div className="min-w-0 font-medium text-sm">{displayFilename(title)}</div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            disabled={pageNumber <= 1 || loading}
            onClick={() => setPageNumber((current) => Math.max(1, current - 1))}
            size="icon"
            type="button"
            variant="ghost"
          >
            <ChevronLeft className="size-4" />
          </Button>
          <div className="w-16 text-center text-sm tabular-nums">
            {pageNumber} / {pageCount || "-"}
          </div>
          <Button
            disabled={!pageCount || pageNumber >= pageCount || loading}
            onClick={() => setPageNumber((current) => Math.min(pageCount, current + 1))}
            size="icon"
            type="button"
            variant="ghost"
          >
            <ChevronRight className="size-4" />
          </Button>
          <div className="mx-1 hidden h-5 w-px bg-border sm:block" />
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
          <div className="w-12 text-right text-muted-foreground text-xs tabular-nums">{Math.round(scale * 100)}%</div>
          <Button disabled={loading} onClick={() => setScale(1)} size="icon" type="button" variant="ghost">
            <RotateCw className="size-4" />
          </Button>
        </div>
      </div>
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
          <canvas ref={canvasRef} className="mx-auto block bg-white shadow-sm ring-1 ring-border" />
        )}
      </div>
    </div>
  );
}

function DocxPreview({ objectUrl, title }: { objectUrl: string; title: string }) {
  const [html, setHtml] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setHtml("");

    fetch(objectUrl)
      .then((response) => response.arrayBuffer())
      .then((arrayBuffer) => mammoth.convertToHtml({ arrayBuffer }))
      .then((result) => {
        if (!cancelled) {
          setHtml(result.value);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Word 文件预览加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [objectUrl]);

  return (
    <div className="overflow-hidden rounded-lg border bg-background">
      <div className="border-b bg-muted/20 px-3 py-2 font-medium text-sm">{displayFilename(title)}</div>
      <div className="min-h-[680px] bg-muted/30 p-6">
        <article className="mx-auto min-h-[620px] max-w-4xl bg-white px-12 py-10 shadow-sm ring-1 ring-border">
          {loading ? (
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Loader2 className="size-4 animate-spin" />
              加载中
            </div>
          ) : error ? (
            <div className="text-muted-foreground text-sm">{error}</div>
          ) : (
            <div
              className="markdown-preview border-0 bg-transparent shadow-none"
              dangerouslySetInnerHTML={{ __html: html || "<p>文档暂无可预览内容。</p>" }}
            />
          )}
        </article>
      </div>
    </div>
  );
}

function displayFilename(filename: string) {
  return filename.replace(/^\d+[_-]/, "");
}
