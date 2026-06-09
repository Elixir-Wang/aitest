"use client";

import * as React from "react";

import { Archive, ArrowUp, Check, ChevronDown, Clock, FileText, Plus, X } from "lucide-react";

import { cn } from "@/lib/utils";

type KnowledgeSourceMode = "all" | "requirements" | "explorations";

type PastedContent = {
  id: string;
  content: string;
};

type KnowledgeChatInputProps = {
  disabled?: boolean;
  loading?: boolean;
  value: string;
  includeRequirements: boolean;
  includeExplorations: boolean;
  onSourceChange: (next: { includeRequirements: boolean; includeExplorations: boolean }) => void;
  onSubmit: (instruction: string) => void;
  onValueChange: (value: string) => void;
};

const sourceModes: Array<{
  id: KnowledgeSourceMode;
  name: string;
  description: string;
  includeRequirements: boolean;
  includeExplorations: boolean;
}> = [
  {
    id: "all",
    name: "需求 + 探索",
    description: "合并需求文件和探索文件",
    includeRequirements: true,
    includeExplorations: true,
  },
  {
    id: "requirements",
    name: "仅需求",
    description: "只读取已确认需求版本",
    includeRequirements: true,
    includeExplorations: false,
  },
  {
    id: "explorations",
    name: "仅探索",
    description: "只读取已完成探索结果",
    includeRequirements: false,
    includeExplorations: true,
  },
];

export function KnowledgeChatInput({
  disabled = false,
  loading = false,
  value,
  includeRequirements,
  includeExplorations,
  onSourceChange,
  onSubmit,
  onValueChange,
}: KnowledgeChatInputProps) {
  const [sourceOpen, setSourceOpen] = React.useState(false);
  const [thinkingEnabled, setThinkingEnabled] = React.useState(false);
  const [isDragging, setIsDragging] = React.useState(false);
  const [pastedContents, setPastedContents] = React.useState<PastedContent[]>([]);
  const textareaRef = React.useRef<HTMLTextAreaElement | null>(null);
  const dropdownRef = React.useRef<HTMLDivElement | null>(null);

  const currentMode =
    sourceModes.find(
      (mode) => mode.includeRequirements === includeRequirements && mode.includeExplorations === includeExplorations,
    ) ?? sourceModes[0];
  const hasContent = value.trim().length > 0 || pastedContents.length > 0;

  React.useEffect(() => {
    if (!textareaRef.current) {
      return;
    }
    textareaRef.current.style.height = "auto";
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 260)}px`;
  }, [value]);

  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setSourceOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function submit() {
    if (!hasContent || disabled || loading) {
      return;
    }
    const pastedText = pastedContents.map((item) => item.content.trim()).filter(Boolean);
    const instruction = [value.trim(), ...pastedText].filter(Boolean).join("\n\n");
    onSubmit(instruction);
    setPastedContents([]);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  function handlePaste(event: React.ClipboardEvent<HTMLTextAreaElement>) {
    const text = event.clipboardData.getData("text");
    if (text.length <= 300) {
      return;
    }
    event.preventDefault();
    setPastedContents((current) => [...current, { id: crypto.randomUUID(), content: text }]);
    if (!value.trim()) {
      onValueChange("请结合粘贴内容查询项目知识库。");
    }
  }

  function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    const textFile = Array.from(event.dataTransfer.files).find((file) => file.type.startsWith("text/"));
    if (!textFile) {
      return;
    }
    void textFile.text().then((content) => {
      setPastedContents((current) => [...current, { id: crypto.randomUUID(), content }]);
      if (!value.trim()) {
        onValueChange(`请结合 ${textFile.name} 查询项目知识库。`);
      }
    });
  }

  return (
    <div
      className="relative mx-auto w-full max-w-3xl font-sans"
      onDragLeave={(event) => {
        event.preventDefault();
        setIsDragging(false);
      }}
      onDragOver={(event) => {
        event.preventDefault();
        setIsDragging(true);
      }}
      onDrop={handleDrop}
    >
      <div
        className={cn(
          "relative z-10 flex flex-col items-stretch rounded-2xl border border-border bg-background shadow-[0_0_15px_rgba(0,0,0,0.08)] transition-all duration-200 hover:shadow-[0_0_20px_rgba(0,0,0,0.12)] focus-within:shadow-[0_0_25px_rgba(0,0,0,0.15)] dark:border-transparent dark:bg-[#30302E]",
          disabled && "opacity-70",
        )}
      >
        <div className="flex flex-col gap-2 px-3 pt-3 pb-2">
          {pastedContents.length > 0 ? (
            <div className="flex gap-3 overflow-x-auto px-1 pb-2">
              {pastedContents.map((content) => (
                <PastedContentCard
                  content={content}
                  key={content.id}
                  onRemove={(id) => setPastedContents((current) => current.filter((item) => item.id !== id))}
                />
              ))}
            </div>
          ) : null}

          <div className="relative mb-1">
            <div className="max-h-72 min-h-10 w-full overflow-y-auto break-words pl-1 transition-opacity duration-200">
              <textarea
                className="block w-full resize-none overflow-hidden border-0 bg-transparent py-0 font-normal text-base leading-relaxed text-foreground antialiased outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
                disabled={disabled || loading}
                onChange={(event) => onValueChange(event.target.value)}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                placeholder={disabled ? "请先选择具体项目" : "询问最终需求文档或探索记录..."}
                ref={textareaRef}
                rows={1}
                value={value}
              />
            </div>
          </div>

          <div className="flex w-full items-center gap-2">
            <div className="flex min-w-0 flex-1 items-center gap-1">
              <button
                aria-label="添加知识来源"
                className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors duration-200 hover:bg-muted hover:text-foreground active:scale-95"
                disabled={disabled || loading}
                onClick={() => setSourceOpen((open) => !open)}
                type="button"
              >
                <Plus className="size-5" />
              </button>
              <button
                aria-label="深度思考"
                aria-pressed={thinkingEnabled}
                className={cn(
                  "inline-flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors duration-200 active:scale-95",
                  thinkingEnabled ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
                disabled={disabled || loading}
                onClick={() => setThinkingEnabled((enabled) => !enabled)}
                type="button"
              >
                <Clock className="size-5" />
              </button>
            </div>

            <div className="flex min-w-0 items-center gap-1">
              <div className="relative shrink-0 p-1 -m-1" ref={dropdownRef}>
                <button
                  className="inline-flex h-8 min-w-28 items-center justify-center gap-1 rounded-xl px-2.5 text-sm font-medium text-muted-foreground transition-colors duration-200 hover:bg-muted hover:text-foreground"
                  disabled={disabled || loading}
                  onClick={() => setSourceOpen((open) => !open)}
                  type="button"
                >
                  <span className="truncate">{currentMode.name}</span>
                  <ChevronDown className={cn("size-4 opacity-75 transition-transform", sourceOpen && "rotate-180")} />
                </button>
                {sourceOpen ? (
                  <div className="absolute right-0 bottom-full z-50 mb-2 flex w-64 origin-bottom-right flex-col overflow-hidden rounded-2xl border bg-popover p-1.5 text-popover-foreground shadow-2xl">
                    {sourceModes.map((mode) => (
                      <button
                        className="flex w-full items-start justify-between rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-muted"
                        key={mode.id}
                        onClick={() => {
                          onSourceChange({
                            includeRequirements: mode.includeRequirements,
                            includeExplorations: mode.includeExplorations,
                          });
                          setSourceOpen(false);
                        }}
                        type="button"
                      >
                        <span>
                          <span className="block font-semibold text-sm">{mode.name}</span>
                          <span className="block text-muted-foreground text-xs">{mode.description}</span>
                        </span>
                        {currentMode.id === mode.id ? <Check className="mt-1 size-4 text-primary" /> : null}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>

              <button
                aria-label="发送消息"
                className={cn(
                  "inline-flex size-8 shrink-0 items-center justify-center rounded-xl transition-colors active:scale-95",
                  hasContent && !disabled && !loading
                    ? "bg-primary text-primary-foreground shadow-md hover:bg-primary/90"
                    : "cursor-default bg-primary/30 text-primary-foreground/60",
                )}
                disabled={!hasContent || disabled || loading}
                onClick={submit}
                type="button"
              >
                <ArrowUp className="size-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {isDragging ? (
        <div className="pointer-events-none absolute inset-0 z-50 flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-primary bg-muted/90 backdrop-blur-sm">
          <Archive className="mb-2 size-10 animate-bounce text-primary" />
          <p className="font-medium text-primary text-sm">拖入文本文件作为补充指令</p>
        </div>
      ) : null}
    </div>
  );
}

function PastedContentCard({ content, onRemove }: { content: PastedContent; onRemove: (id: string) => void }) {
  return (
    <div className="group relative flex size-28 shrink-0 flex-col justify-between overflow-hidden rounded-2xl border bg-background p-3 shadow-[0_1px_2px_rgba(0,0,0,0.05)]">
      <div className="w-full overflow-hidden">
        <p className="line-clamp-4 select-none break-words font-mono text-[10px] text-muted-foreground leading-[1.4] whitespace-pre-wrap">
          {content.content}
        </p>
      </div>
      <div className="mt-2 flex items-center justify-between">
        <div className="inline-flex items-center justify-center rounded border bg-background px-1.5 py-[2px]">
          <FileText className="mr-1 size-3 text-muted-foreground" />
          <span className="font-bold text-[9px] text-muted-foreground uppercase tracking-wide">Pasted</span>
        </div>
      </div>
      <button
        className="absolute top-2 right-2 rounded-full border bg-background p-1 text-muted-foreground opacity-0 shadow-sm transition-opacity hover:text-foreground group-hover:opacity-100"
        onClick={() => onRemove(content.id)}
        type="button"
      >
        <X className="size-2.5" />
      </button>
    </div>
  );
}
