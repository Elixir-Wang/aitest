"use client";

import * as React from "react";

import { Archive, ArrowUp, Brain, FileText, Square, X } from "lucide-react";

import type { ApiModelProvider } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

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
  showThinking: boolean;
  onModelProviderChange: (modelProviderId: string) => void;
  onProjectScopeChange: (value: string) => void;
  onShowThinkingChange: (value: boolean) => void;
  onStop?: () => void;
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
  showThinking,
  onModelProviderChange,
  onProjectScopeChange,
  onShowThinkingChange,
  onStop,
  onSubmit,
  onValueChange,
}: KnowledgeChatInputProps) {
  const [isDragging, setIsDragging] = React.useState(false);
  const [pastedContents, setPastedContents] = React.useState<PastedContent[]>([]);
  const textareaRef = React.useRef<HTMLTextAreaElement | null>(null);

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

          <div className={cn("flex w-full items-center gap-2", compact ? "pt-1.5" : "pt-2")}>
            <div className="flex min-w-0 flex-1 items-center gap-1">
              <Select
                disabled={projectScopeSelectorDisabled}
                onValueChange={onProjectScopeChange}
                value={selectedProjectScope}
              >
                <SelectTrigger
                  aria-label="选择知识检索项目"
                  className={cn(
                    "max-w-full min-w-0 gap-2 bg-background shadow-sm **:data-[slot=select-value]:truncate",
                    compact ? "h-7 px-2 text-xs" : "h-8 px-2.5 text-sm",
                  )}
                  size={compact ? "sm" : "default"}
                  title={selectedProjectScopeOption?.locked ? "跟随右上角项目上下文" : selectedProjectScopeOption?.label}
                >
                  <SelectValue placeholder="选择知识库" />
                </SelectTrigger>
                <SelectContent
                  align="center"
                  className="w-max min-w-0"
                  position="popper"
                  side="top"
                  viewportClassName="w-max"
                >
                  {projectScopeOptions.map((option) => (
                    <SelectItem
                      className={cn("whitespace-nowrap", compact ? "text-xs" : "text-sm")}
                      disabled={option.locked}
                      key={option.value}
                      value={option.value}
                    >
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select
                disabled={disabled || loading || modelLoading || modelSaving || modelProviders.length === 0}
                onValueChange={onModelProviderChange}
                value={selectedModelProviderId}
              >
                <SelectTrigger
                  aria-label="选择知识库查询模型"
                  className={cn(
                    "max-w-56 min-w-28 gap-2 bg-background shadow-sm **:data-[slot=select-value]:truncate",
                    compact ? "h-7 px-2 text-xs" : "h-8 px-2.5 text-sm",
                  )}
                  size={compact ? "sm" : "default"}
                >
                  <SelectValue placeholder={modelSaving ? "保存中" : modelLabel}>
                    <span className="truncate">{modelSaving ? "保存中" : modelLabel}</span>
                  </SelectValue>
                </SelectTrigger>
                <SelectContent
                  align="center"
                  className="w-max min-w-0"
                  position="popper"
                  side="top"
                  viewportClassName="w-max"
                >
                  {modelProviders.map((provider) => (
                    <SelectItem
                      className={cn("whitespace-nowrap py-1.5", compact ? "text-xs" : "text-sm")}
                      key={provider.id}
                      value={provider.id}
                    >
                      <span className="flex min-w-0 items-baseline gap-2">
                        <span className="max-w-40 truncate">{provider.model}</span>
                        <span className="max-w-28 truncate text-muted-foreground">{provider.provider}</span>
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex shrink-0 items-center gap-1">
              <button
                aria-label="深度思考"
                aria-pressed={showThinking}
                className={cn(
                  "inline-flex shrink-0 items-center justify-center rounded-md border transition-colors",
                  compact ? "size-7" : "size-8",
                  showThinking
                    ? "border-primary bg-primary/10 text-primary"
                    : "bg-background text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
                disabled={disabled || loading}
                onClick={() => onShowThinkingChange(!showThinking)}
                title={showThinking ? "关闭深度思考显示" : "显示深度思考内容"}
                type="button"
              >
                <Brain className="size-4" />
              </button>
              <button
                aria-label={loading ? "停止生成" : "发送消息"}
                className={cn(
                  "inline-flex shrink-0 items-center justify-center rounded-md transition-colors active:scale-95",
                  compact ? "size-7" : "size-8",
                  loading
                    ? "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90"
                    : hasContent && !disabled
                    ? "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90"
                    : "cursor-default bg-muted text-muted-foreground",
                )}
                disabled={loading ? disabled || !onStop : !hasContent || disabled}
                onClick={loading ? onStop : submit}
                type="button"
              >
                {loading ? <Square className="size-3 fill-current" /> : <ArrowUp className="size-4" />}
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
