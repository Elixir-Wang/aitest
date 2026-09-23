"use client";

import { useEffect, useState } from "react";

import type { LucideIcon } from "lucide-react";
import {
  AlertCircle,
  Braces,
  Building2,
  CheckCircle2,
  Compass,
  FileCheck2,
  ListChecks,
  Loader2,
  RotateCcw,
  Save,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { apiRequest } from "@/lib/api-client";
import { cn } from "@/lib/utils";

type SourceType = "final_requirements" | "explorations" | "test_cases" | "api_information" | "company_knowledge";

type SettingsResponse = {
  scope: "global" | "project";
  scope_key: string;
  project_id: string | null;
  sources: Array<{
    source_type: SourceType;
    enabled: boolean;
    origin: "system" | "global" | "project";
    inherited: boolean;
  }>;
};

const sourceDefinitions: Array<{
  sourceType: SourceType;
  label: string;
  description: string;
  icon: LucideIcon;
}> = [
  {
    sourceType: "final_requirements",
    label: "最终需求",
    description: "检索当前最终需求 Markdown，不读取工作稿。",
    icon: FileCheck2,
  },
  {
    sourceType: "explorations",
    label: "探索产物",
    description: "检索项目已生成的页面 YAML 探索产物。",
    icon: Compass,
  },
  {
    sourceType: "test_cases",
    label: "已采纳测试用例",
    description: "只检索评审状态为已采纳的测试用例。",
    icon: ListChecks,
  },
  {
    sourceType: "api_information",
    label: "接口信息",
    description: "检索接口资产和接口场景。",
    icon: Braces,
  },
  {
    sourceType: "company_knowledge",
    label: "公司知识库",
    description: "检索公司级规范、模板和通用知识。",
    icon: Building2,
  },
];

export function KnowledgeSearchSettings({
  projectId,
  projectName,
  scope,
}: {
  projectId: string | null;
  projectName: string | null;
  scope: "all" | "project";
}) {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [values, setValues] = useState<Record<SourceType, boolean>>({
    final_requirements: true,
    explorations: true,
    test_cases: false,
    api_information: false,
    company_knowledge: true,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");

  const path = scope === "all" ? "/knowledge/search-settings" : `/projects/${projectId}/knowledge/search-settings`;

  useEffect(() => {
    if (scope === "project" && !projectId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    setFeedback("");
    void apiRequest<SettingsResponse>(path)
      .then((result) => {
        if (cancelled) return;
        setSettings(result);
        setValues(
          Object.fromEntries(result.sources.map((item) => [item.source_type, item.enabled])) as Record<
            SourceType,
            boolean
          >,
        );
      })
      .catch((nextError) => {
        if (!cancelled) setError(nextError instanceof Error ? nextError.message : "加载检索设置失败。");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [path, projectId, scope]);

  async function save() {
    if (!Object.values(values).some(Boolean)) {
      setError("请至少启用一个检索来源。");
      return;
    }
    setSaving(true);
    setError("");
    setFeedback("");
    try {
      const result = await apiRequest<SettingsResponse>(path, {
        method: "PUT",
        body: JSON.stringify({
          sources: sourceDefinitions.map(({ sourceType }) => ({
            source_type: sourceType,
            enabled: values[sourceType],
          })),
        }),
      });
      setSettings(result);
      setFeedback("设置已保存");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "保存检索设置失败。");
    } finally {
      setSaving(false);
    }
  }

  async function restore() {
    setSaving(true);
    setError("");
    setFeedback("");
    try {
      const result = await apiRequest<SettingsResponse>(`/projects/${projectId}/knowledge/search-settings`, {
        method: "DELETE",
      });
      setSettings(result);
      setValues(
        Object.fromEntries(result.sources.map((item) => [item.source_type, item.enabled])) as Record<
          SourceType,
          boolean
        >,
      );
      setFeedback("已恢复全局设置");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "恢复全局设置失败。");
    } finally {
      setSaving(false);
    }
  }

  if (scope === "project" && !projectId) {
    return <div className="rounded-xl border p-6 text-muted-foreground text-sm">请选择具体项目后配置检索来源。</div>;
  }

  const hasChanges = settings
    ? sourceDefinitions.some(({ sourceType }) => {
        const savedValue = settings.sources.find((item) => item.source_type === sourceType)?.enabled;
        return savedValue !== values[sourceType];
      })
    : false;

  function updateSource(sourceType: SourceType, checked: boolean) {
    setValues((current) => ({ ...current, [sourceType]: checked }));
    setFeedback("");
    setError("");
  }

  return (
    <section
      aria-busy={loading || saving}
      aria-labelledby="knowledge-search-settings-title"
      className="w-full overflow-hidden rounded-xl border bg-card shadow-xs"
    >
      <header className="border-b px-5 py-5 sm:px-6">
        <h2 className="font-semibold text-base leading-6 tracking-tight" id="knowledge-search-settings-title">
          检索内容范围
        </h2>
        <p className="mt-1 text-muted-foreground text-sm leading-5">
          {scope === "all"
            ? "全局设置，应用于全部项目。开启后，知识库问答将检索以下来源。"
            : `应用于「${projectName ?? "当前项目"}」。开启后，该项目的知识库问答将检索以下来源。`}
        </p>
      </header>

      <fieldset disabled={loading || saving}>
        <legend className="sr-only">可检索的知识来源</legend>
        {sourceDefinitions.map(({ description, icon: Icon, label, sourceType }) => {
          const source = settings?.sources.find((item) => item.source_type === sourceType);
          const switchId = `knowledge-search-source-${sourceType}`;
          const enabled = values[sourceType];
          return (
            <label
              className={cn(
                "group flex min-h-[4.75rem] cursor-pointer items-center gap-4 border-b px-5 py-3.5 transition-colors last:border-b-0 sm:px-6",
                "focus-within:bg-muted/25 hover:bg-muted/25",
                (loading || saving) && "cursor-wait opacity-65",
              )}
              htmlFor={switchId}
              key={sourceType}
            >
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border bg-muted/50">
                <Icon className="size-4 text-muted-foreground" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2 font-medium text-sm">
                  {label}
                  {source?.inherited ? (
                    <span className="rounded-full bg-muted px-2 py-0.5 font-normal text-muted-foreground text-xs">
                      沿用全局
                    </span>
                  ) : null}
                </span>
                <span className="mt-1 block text-muted-foreground text-sm leading-5">{description}</span>
              </span>
              <Switch
                aria-label={`${label}检索`}
                checked={enabled}
                id={switchId}
                onCheckedChange={(checked) => updateSource(sourceType, checked)}
              />
            </label>
          );
        })}
      </fieldset>

      <footer className="flex flex-col gap-3 border-t px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div aria-live="polite" className="min-h-5 text-sm" role="status">
          {error ? (
            <span className="flex items-center gap-1.5 text-destructive">
              <AlertCircle className="size-4" />
              {error}
            </span>
          ) : feedback ? (
            <span className="flex items-center gap-1.5 text-primary">
              <CheckCircle2 className="size-4" />
              {feedback}
            </span>
          ) : hasChanges ? (
            <span className="text-muted-foreground">有未保存的更改</span>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center justify-end gap-2">
          {scope === "project" ? (
            <Button disabled={loading || saving} onClick={() => void restore()} type="button" variant="ghost">
              <RotateCcw className="size-4" />
              恢复全局设置
            </Button>
          ) : null}
          <Button disabled={loading || saving || !hasChanges} onClick={() => void save()} type="button">
            {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
            {saving ? "正在保存" : "保存更改"}
          </Button>
        </div>
      </footer>
    </section>
  );
}
