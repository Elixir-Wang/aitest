"use client";

import * as React from "react";

import { Archive, ArrowUp, Check, ChevronDown, FileText, X } from "lucide-react";

import type { ApiModelProvider } from "@/lib/api-client";
import { cn } from "@/lib/utils";

type PastedContent = {
  id: string;
  content: string;
};

type KnowledgeProjectScopeOption = { value: string; label: string; locked?: boolean };

type KnowledgeChatInputProps = {
  compact?: boolean;
  disabled?: boolean;
  loading?: boolean;
  value: string;
  modelProviders: ApiModelProvider[];
  modelLoading?: boolean;
  modelSaving?: boolean;
  projectScopeOptions: KnowledgeProjectScopeOption[];
  projectScopeDisabled?: boolean;
  selectedModelProviderId: string;
  selectedProjectScope: string;
  onModelProviderChange: (modelProviderId: string) => void;
  onProjectScopeChange: (value: string) => void;
  onSubmit: (instruction: string) => void;
  onValueChange: (value: string) => void;
};

export function KnowledgeChatInput({
  compact = false,
  disabled = false,
  loading = false,
  value,
  modelProviders,
  modelLoading = false,
  modelSaving = false,
  projectScopeOptions,
  projectScopeDisabled = false,
  selectedModelProviderId,
  selectedProjectScope,
  onModelProviderChange,
  onProjectScopeChange,
  onSubmit,
  onValueChange,
}: KnowledgeChatInputProps) {
  const [modelOpen, setModelOpen] = React.useState(false);
  const [isDragging, setIsDragging] = React.useState(false);
  const [pastedContents, setPastedContents] = React.useState<PastedContent[]>([]);
  const textareaRef = React.useRef<HTMLTextAreaElement | null>(null);
  const dropdownRef = React.useRef<HTMLDivElement | null>(null);

  const selectedModelProvider = modelProviders.find((provider) => provider.id === selectedModelProviderId) ?? null;
  const modelLabel = selectedModelProvider
    ? selectedModelProvider.model
    : modelLoading
      ? "加载模型"
      : "选择模型";
  const selectedProjectScopeOption =
    projectScopeOptions.find((option) => option.value === selectedProjectScope) ?? projectScopeOptions[0] ?? null;
  const projectScopeSelectorDisabled =
    disabled || loading || projectScopeDisabled || projectScopeOptions.length <= 1 || selectedProjectScopeOption?.locked;
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
        setModelOpen(false);
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
          "relative z-10 flex flex-col items-stretch overflow-hidden rounded-lg border bg-background shadow-sm transition-all duration-200 hover:border-ring/50 focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/20",
          disabled && "opacity-70",
        )}
      >
        <div className={cn("flex flex-col gap-2", compact ? "px-3 pt-3 pb-2.5" : "px-4 pt-4 pb-3")}>
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
            <div
              className={cn(
                "w-full overflow-y-auto break-words pl-1 transition-opacity duration-200",
                compact ? "max-h-40 min-h-10" : "max-h-72 min-h-12",
              )}
            >
              <textarea
                className={cn(
                  "block w-full resize-none overflow-hidden border-0 bg-transparent py-1 font-normal text-foreground text-sm antialiased outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed",
                  compact ? "leading-5" : "leading-6",
                )}
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

          <div className={cn("flex w-full items-center gap-2 border-t", compact ? "pt-1.5" : "pt-2")}>
            <div className="flex min-w-0 flex-1 items-center gap-1">
              <select
                aria-label="选择知识检索项目"
                className={cn(
                  "max-w-full min-w-0 appearance-none truncate rounded-md border bg-background font-medium text-muted-foreground shadow-sm outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-60",
                  compact ? "h-7 px-2 pr-7 text-xs" : "h-8 px-2.5 pr-8 text-sm",
                )}
                disabled={projectScopeSelectorDisabled}
                onChange={(event) => onProjectScopeChange(event.target.value)}
                title={selectedProjectScopeOption?.locked ? "跟随右上角项目上下文" : selectedProjectScopeOption?.label}
                value={selectedProjectScope}
              >
                {projectScopeOptions.map((option) => (
                  <option disabled={option.locked} key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex min-w-0 items-center gap-1">
              <div className="relative shrink-0 p-1 -m-1" ref={dropdownRef}>
                <button
                  className={cn(
                    "inline-flex max-w-56 min-w-28 items-center justify-center gap-1 rounded-md font-medium text-muted-foreground transition-colors duration-200 hover:bg-muted hover:text-foreground",
                    compact ? "h-7 px-2 text-xs" : "h-8 px-2.5 text-sm",
                  )}
                  disabled={disabled || loading || modelLoading || modelSaving || modelProviders.length === 0}
                  onClick={() => setModelOpen((open) => !open)}
                  type="button"
                >
                  <span className="truncate">{modelSaving ? "保存中" : modelLabel}</span>
                  <ChevronDown className={cn("size-4 opacity-75 transition-transform", modelOpen && "rotate-180")} />
                </button>
                {modelOpen ? (
                  <div className="absolute right-0 bottom-full z-50 mb-2 flex w-64 origin-bottom-right flex-col overflow-hidden rounded-lg border bg-popover p-1.5 text-popover-foreground shadow-2xl">
                    {modelProviders.map((provider) => (
                      <button
                        className="flex w-full items-start justify-between rounded-md px-3 py-2.5 text-left transition-colors hover:bg-muted"
                        key={provider.id}
                        onClick={() => {
                          onModelProviderChange(provider.id);
                          setModelOpen(false);
                        }}
                        type="button"
                      >
                        <span>
                          <span className="block font-semibold text-sm">{provider.model}</span>
                          <span className="block text-muted-foreground text-xs">{provider.provider}</span>
                        </span>
                        {selectedModelProviderId === provider.id ? (
                          <Check className="mt-1 size-4 text-primary" />
                        ) : null}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>

              <button
                aria-label="发送消息"
                className={cn(
                  "inline-flex shrink-0 items-center justify-center rounded-md transition-colors active:scale-95",
                  compact ? "size-7" : "size-8",
                  hasContent && !disabled && !loading
                    ? "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90"
                    : "cursor-default bg-muted text-muted-foreground",
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
        <div className="pointer-events-none absolute inset-0 z-50 flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-primary bg-background/90 backdrop-blur-sm">
          <Archive className="mb-2 size-10 animate-bounce text-primary" />
          <p className="font-medium text-primary text-sm">拖入文本文件作为补充指令</p>
        </div>
      ) : null}
    </div>
  );
}

function PastedContentCard({ content, onRemove }: { content: PastedContent; onRemove: (id: string) => void }) {
  return (
    <div className="group relative flex size-28 shrink-0 flex-col justify-between overflow-hidden rounded-lg border bg-background p-3 shadow-sm">
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
