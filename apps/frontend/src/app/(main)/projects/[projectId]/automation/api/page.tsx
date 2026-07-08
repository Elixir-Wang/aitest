"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Braces, FileJson, Play, RefreshCw, WandSparkles } from "lucide-react";

import { PageShell } from "@/components/ai-testing/page-shell";
import { useProjectName } from "@/components/ai-testing/use-project-name";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  type ApiAutomationEndpoint,
  type ApiAutomationEnvironment,
  type ApiAutomationGenerationRun,
  type ApiAutomationRun,
  type ApiAutomationScript,
  createApiAutomationEnvironment,
  createApiAutomationRun,
  generateApiAutomation,
  generateApiAutomationScripts,
  getApiAutomationGenerationRun,
  getApiAutomationRun,
  importOpenApiDocument,
  listApiAutomationEndpoints,
  listApiAutomationEnvironments,
} from "@/lib/api-client";

const tabs = ["接口资产", "测试脚本", "运行记录", "场景编排"];

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const projectName = useProjectName(projectId);
  const [activeTab, setActiveTab] = useState(tabs[0]);
  const [endpoints, setEndpoints] = useState<ApiAutomationEndpoint[]>([]);
  const [environments, setEnvironments] = useState<ApiAutomationEnvironment[]>([]);
  const [generationRun, setGenerationRun] = useState<ApiAutomationGenerationRun | null>(null);
  const [scripts, setScripts] = useState<ApiAutomationScript[]>([]);
  const [run, setRun] = useState<ApiAutomationRun | null>(null);
  const [selectedEndpointIds, setSelectedEndpointIds] = useState<string[]>([]);
  const [openApiText, setOpenApiText] = useState("");
  const [openApiName, setOpenApiName] = useState("");
  const [generationGoal, setGenerationGoal] = useState("覆盖正常响应、参数缺失和鉴权失败");
  const [environmentName, setEnvironmentName] = useState("测试环境");
  const [apiBaseUrl, setApiBaseUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const readyCases = useMemo(
    () => generationRun?.test_cases?.filter((item) => item.status === "ready") ?? [],
    [generationRun],
  );

  async function refresh() {
    const [endpointRows, environmentRows] = await Promise.all([
      listApiAutomationEndpoints(projectId),
      listApiAutomationEnvironments(projectId),
    ]);
    setEndpoints(endpointRows);
    setEnvironments(environmentRows);
    if (generationRun) {
      setGenerationRun(await getApiAutomationGenerationRun(projectId, generationRun.id));
    }
    if (run) {
      setRun(await getApiAutomationRun(projectId, run.id));
    }
  }

  useEffect(() => {
    Promise.all([listApiAutomationEndpoints(projectId), listApiAutomationEnvironments(projectId)])
      .then(([endpointRows, environmentRows]) => {
        setEndpoints(endpointRows);
        setEnvironments(environmentRows);
      })
      .catch((error) => setMessage(error.message));
  }, [projectId]);

  async function handleImport() {
    setBusy(true);
    setMessage("");
    try {
      await importOpenApiDocument(projectId, {
        source_type: "file",
        name: openApiName || "OpenAPI",
        content: openApiText,
      });
      setOpenApiText("");
      await refresh();
      setActiveTab("接口资产");
      setMessage("导入完成。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "导入失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateEnvironment() {
    setBusy(true);
    setMessage("");
    try {
      await createApiAutomationEnvironment(projectId, {
        name: environmentName,
        api_base_url: apiBaseUrl,
        auth_type: "none",
      });
      await refresh();
      setMessage("接口环境已保存。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "环境保存失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerate() {
    setBusy(true);
    setMessage("");
    try {
      const created = await generateApiAutomation(projectId, {
        endpoint_ids: selectedEndpointIds,
        api_environment_id: environments[0]?.id ?? null,
        generation_goal: generationGoal,
        include_security_cases: false,
        generate_code: false,
      });
      setGenerationRun(created);
      setActiveTab("测试脚本");
      setMessage("生成任务已创建，稍后刷新查看用例。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "生成失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerateScripts() {
    setBusy(true);
    setMessage("");
    try {
      const result = await generateApiAutomationScripts(projectId, {
        api_test_case_ids: readyCases.map((item) => item.id),
        api_environment_id: environments[0]?.id ?? null,
      });
      setScripts(result.scripts);
      setMessage("脚本已生成。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "脚本生成失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleRun() {
    setBusy(true);
    setMessage("");
    try {
      const created = await createApiAutomationRun(projectId, {
        script_ids: scripts.map((item) => item.id),
        api_environment_id: environments[0]?.id ?? null,
      });
      setRun(created);
      setActiveTab("运行记录");
      setMessage("执行任务已创建。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "执行失败。");
    } finally {
      setBusy(false);
    }
  }

  function toggleEndpoint(endpointId: string) {
    setSelectedEndpointIds((current) =>
      current.includes(endpointId) ? current.filter((item) => item !== endpointId) : [...current, endpointId],
    );
  }

  return (
    <PageShell
      activeTab={activeTab}
      breadcrumbs={["项目", projectName, "接口自动化"]}
      description="导入 OpenAPI、生成接口自动化用例、生成 pytest 脚本并执行。"
      onTabChange={setActiveTab}
      projectScope="project"
      tabs={tabs}
      title="接口自动化"
      actions={
        <Button disabled={busy} onClick={() => refresh()} size="sm" variant="outline">
          <RefreshCw className="size-4" />
          刷新
        </Button>
      }
    >
      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="接口" value={endpoints.length} />
        <Metric label="环境" value={environments.length} />
        <Metric label="用例" value={generationRun?.test_cases?.length ?? 0} />
        <Metric label="脚本" value={scripts.length} />
      </div>
      {message && <div className="rounded-md border px-3 py-2 text-sm">{message}</div>}
      {activeTab === "接口资产" && (
        <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FileJson className="size-4" />
                导入 OpenAPI
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input placeholder="文档名称" value={openApiName} onChange={(event) => setOpenApiName(event.target.value)} />
              <Textarea
                className="min-h-[260px] font-mono text-xs"
                placeholder='{"openapi":"3.0.3","info":{"title":"API"},"paths":{}}'
                value={openApiText}
                onChange={(event) => setOpenApiText(event.target.value)}
              />
              <Button disabled={busy || !openApiText.trim()} onClick={handleImport}>
                <Braces className="size-4" />
                导入
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">接口列表</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {endpoints.map((endpoint) => (
                <button
                  className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm"
                  key={endpoint.id}
                  onClick={() => toggleEndpoint(endpoint.id)}
                  type="button"
                >
                  <span className="min-w-0 truncate">
                    <Badge variant="outline">{endpoint.method}</Badge> {endpoint.path}
                  </span>
                  <Badge>{selectedEndpointIds.includes(endpoint.id) ? "已选" : endpoint.tags[0] || "Other"}</Badge>
                </button>
              ))}
              {endpoints.length === 0 && <p className="text-muted-foreground text-sm">暂无接口资产。</p>}
            </CardContent>
          </Card>
        </div>
      )}
      {activeTab === "测试脚本" && (
        <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <WandSparkles className="size-4" />
                生成
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input placeholder="API Base URL" value={apiBaseUrl} onChange={(event) => setApiBaseUrl(event.target.value)} />
              <Input placeholder="环境名称" value={environmentName} onChange={(event) => setEnvironmentName(event.target.value)} />
              <Button disabled={busy || !apiBaseUrl.trim()} onClick={handleCreateEnvironment} variant="outline">
                保存环境
              </Button>
              <Textarea value={generationGoal} onChange={(event) => setGenerationGoal(event.target.value)} />
              <Button disabled={busy || selectedEndpointIds.length === 0} onClick={handleGenerate}>
                生成用例
              </Button>
              <Button disabled={busy || readyCases.length === 0} onClick={handleGenerateScripts} variant="outline">
                生成脚本
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">成果物</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm">生成任务：{generationRun?.status ?? "-"}</p>
              {generationRun?.test_cases?.map((item) => (
                <div className="rounded-md border px-3 py-2 text-sm" key={item.id}>
                  <div className="flex items-center justify-between">
                    <span>{item.title}</span>
                    <Badge>{item.status}</Badge>
                  </div>
                </div>
              ))}
              {scripts.map((script) => (
                <div className="rounded-md border px-3 py-2 text-sm" key={script.id}>
                  <div className="font-medium">{script.name}</div>
                  <div className="truncate text-muted-foreground text-xs">{script.test_file_path}</div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}
      {activeTab === "运行记录" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Play className="size-4" />
              执行
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button disabled={busy || scripts.length === 0 || environments.length === 0} onClick={handleRun}>
              执行脚本
            </Button>
            <div className="rounded-md border px-3 py-2 text-sm">
              <div>状态：{run?.status ?? "-"}</div>
              <div>报告：{run?.json_report_path || "-"}</div>
              <pre className="mt-2 overflow-auto text-xs">{JSON.stringify(run?.summary ?? {}, null, 2)}</pre>
            </div>
          </CardContent>
        </Card>
      )}
      {activeTab === "场景编排" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">场景编排</CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground text-sm">
            当前后端已支持场景和步骤接口，前端第一步提供入口，后续按表单式步骤编辑完善。
          </CardContent>
        </Card>
      )}
    </PageShell>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border px-3 py-2">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="font-semibold text-xl">{value}</div>
    </div>
  );
}
