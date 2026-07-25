"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { apiRequest } from "@/lib/api-client";

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

const sourceDefinitions: Array<{ sourceType: SourceType; label: string; description: string }> = [
  { sourceType: "final_requirements", label: "最终需求", description: "检索当前最终需求 Markdown，不读取工作稿。" },
  { sourceType: "explorations", label: "探索产物", description: "检索项目已生成的 Markdown、JSON、YAML 等探索产物。" },
  { sourceType: "test_cases", label: "已采纳测试用例", description: "只检索评审状态为已采纳的测试用例。" },
  { sourceType: "api_information", label: "接口信息", description: "检索接口资产和接口场景。" },
  { sourceType: "company_knowledge", label: "公司知识库", description: "检索公司级规范、模板和通用知识。" },
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

  const path = scope === "all" ? "/knowledge/search-settings" : `/projects/${projectId}/knowledge/search-settings`;

  useEffect(() => {
    if (scope === "project" && !projectId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
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
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "保存检索设置失败。");
    } finally {
      setSaving(false);
    }
  }

  async function restore() {
    setSaving(true);
    setError("");
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
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "恢复全局设置失败。");
    } finally {
      setSaving(false);
    }
  }

  if (scope === "project" && !projectId) {
    return <div className="rounded-lg border p-6 text-muted-foreground text-sm">请选择具体项目后配置检索来源。</div>;
  }

  return (
    <div className="space-y-5 rounded-lg border bg-background p-6">
      <div>
        <h2 className="font-semibold text-lg">
          {scope === "all" ? "全局项目检索设置" : `项目检索设置 · ${projectName ?? "当前项目"}`}
        </h2>
        <p className="mt-1 text-muted-foreground text-sm">控制知识库问答会注册哪些来源目录供智能体检索。</p>
      </div>
      <div className="divide-y rounded-lg border">
        {sourceDefinitions.map(({ description, label, sourceType }) => {
          const source = settings?.sources.find((item) => item.source_type === sourceType);
          const checkboxId = `knowledge-search-source-${sourceType}`;
          return (
            <div className="flex items-start gap-3 p-4" key={sourceType}>
              <Checkbox
                checked={values[sourceType]}
                disabled={loading || saving}
                id={checkboxId}
                onCheckedChange={(checked) => setValues((current) => ({ ...current, [sourceType]: Boolean(checked) }))}
              />
              <label className="min-w-0 flex-1 cursor-pointer" htmlFor={checkboxId}>
                <span className="flex items-center gap-2 font-medium">
                  {label}
                  {source?.inherited ? <span className="text-muted-foreground text-xs">继承全局</span> : null}
                </span>
                <span className="mt-1 block text-muted-foreground text-sm">{description}</span>
              </label>
            </div>
          );
        })}
      </div>
      {error ? <p className="text-destructive text-sm">{error}</p> : null}
      <div className="flex justify-end gap-2">
        {scope === "project" ? (
          <Button disabled={loading || saving} onClick={() => void restore()} type="button" variant="outline">
            恢复全局设置
          </Button>
        ) : null}
        <Button disabled={loading || saving} onClick={() => void save()} type="button">
          {saving ? "正在保存" : "保存设置"}
        </Button>
      </div>
    </div>
  );
}
