"use client";

import { useEffect, useMemo, useState } from "react";

import { useParams, useSearchParams } from "next/navigation";

import {
  Braces,
  ChevronDown,
  ChevronRight,
  CircleCheck,
  ClipboardPaste,
  FileJson,
  Globe,
  ImportIcon,
  Loader2,
  Pencil,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  WandSparkles,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { useProjectName } from "@/components/ai-testing/use-project-name";
import { Select as AnimatedSelect, SelectOption } from "@/components/ui/animated-select-1";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import FileUpload1 from "@/components/ui/file-upload-1";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  type ApiAutomationCaseSet,
  type ApiAutomationDebugResult,
  type ApiAutomationEndpoint,
  type ApiAutomationEnvironment,
  type ApiAutomationGenerationRun,
  type ApiAutomationRun,
  type ApiAutomationScript,
  createApiAutomationEnvironment,
  createApiAutomationRun,
  debugApiAutomationEndpoint,
  deleteApiAutomationEndpoint,
  deleteApiAutomationEnvironment,
  formatDateTime,
  generateApiAutomation,
  generateApiAutomationScripts,
  getApiAutomationGenerationRun,
  getApiAutomationRun,
  importOpenApiDocument,
  listApiAutomationCaseSets,
  listApiAutomationEndpoints,
  listApiAutomationEnvironments,
  updateApiAutomationEnvironment,
} from "@/lib/api-client";
import { cn } from "@/lib/utils";

const tabs = ["接口资产", "接口环境", "测试脚本", "运行记录", "场景编排"];
const importModes = [
  {
    value: "file",
    label: "文件导入",
    icon: FileJson,
    description: "读取本地 OpenAPI/Swagger文件。",
  },
  {
    value: "url",
    label: "URL 导入",
    icon: Globe,
    description: "通过 URL 拉取 OpenAPI/Swagger 内容后解析成接口资产。",
  },
  {
    value: "ai",
    label: "AI 导入",
    icon: ClipboardPaste,
    description: "粘贴接口文档内容，复用当前解析链路整理展示。",
  },
] as const;

type ImportMode = (typeof importModes)[number]["value"];
type EnvironmentForm = {
  name: string;
  apiBaseUrl: string;
  authType: "none" | "static_bearer" | "static_headers" | "cookie" | "login_request";
  username: string;
  password: string;
  defaultHeaders: string;
  variables: string;
  timeoutSeconds: string;
  verifySsl: boolean;
  description: string;
};

const authTypeOptions = [
  { value: "none", label: "无需鉴权" },
  { value: "static_bearer", label: "Bearer Token" },
  { value: "static_headers", label: "固定请求头" },
  { value: "cookie", label: "Cookie" },
  { value: "login_request", label: "登录接口" },
] as const;

const emptyEnvironmentForm: EnvironmentForm = {
  name: "测试环境",
  apiBaseUrl: "",
  authType: "none",
  username: "",
  password: "",
  defaultHeaders: "{}",
  variables: "{}",
  timeoutSeconds: "30",
  verifySsl: true,
  description: "",
};
type ApiFieldRow = {
  name: string;
  location: string;
  type: string;
  required: boolean;
  description: string;
  depth?: number;
};
type EndpointDebugForm = {
  environmentId: string;
  pathParams: Record<string, string>;
  queryParams: Record<string, string>;
  headers: Record<string, string>;
  cookies: string;
  bodyText: string;
};

const emptyDebugForm: EndpointDebugForm = {
  environmentId: "",
  pathParams: {},
  queryParams: {},
  headers: {},
  cookies: "{}",
  bodyText: "",
};

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const searchParams = useSearchParams();
  const projectId = params.projectId;
  const selectedCaseSetId = searchParams.get("set");
  const projectName = useProjectName(projectId);
  const [activeTab, setActiveTab] = useState(tabs[0]);
  const [selectedCaseSet, setSelectedCaseSet] = useState<ApiAutomationCaseSet | null>(null);
  const [endpoints, setEndpoints] = useState<ApiAutomationEndpoint[]>([]);
  const [environments, setEnvironments] = useState<ApiAutomationEnvironment[]>([]);
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState("");
  const [generationRun, setGenerationRun] = useState<ApiAutomationGenerationRun | null>(null);
  const [scripts, setScripts] = useState<ApiAutomationScript[]>([]);
  const [run, setRun] = useState<ApiAutomationRun | null>(null);
  const [selectedEndpointIds, setSelectedEndpointIds] = useState<string[]>([]);
  const [selectedEndpointAssetIds, setSelectedEndpointAssetIds] = useState<string[]>([]);
  const [activeEndpointId, setActiveEndpointId] = useState("");
  const [expandedEndpointGroups, setExpandedEndpointGroups] = useState<string[]>([]);
  const [searchText, setSearchText] = useState("");
  const [environmentSearchText, setEnvironmentSearchText] = useState("");
  const [selectedEnvironmentIds, setSelectedEnvironmentIds] = useState<string[]>([]);
  const [importOpen, setImportOpen] = useState(false);
  const [importMode, setImportMode] = useState<ImportMode>("file");
  const [openApiFiles, setOpenApiFiles] = useState<File[]>([]);
  const [openApiText, setOpenApiText] = useState("");
  const [openApiUrl, setOpenApiUrl] = useState("");
  const [generationGoal, setGenerationGoal] = useState("覆盖正常响应、参数缺失和鉴权失败");
  const [environmentOpen, setEnvironmentOpen] = useState(false);
  const [editingEnvironment, setEditingEnvironment] = useState<ApiAutomationEnvironment | null>(null);
  const [environmentForm, setEnvironmentForm] = useState<EnvironmentForm>({ ...emptyEnvironmentForm });
  const [debugOpen, setDebugOpen] = useState(false);
  const [debugForm, setDebugForm] = useState<EndpointDebugForm>({ ...emptyDebugForm });
  const [debugResult, setDebugResult] = useState<ApiAutomationDebugResult | null>(null);
  const [debugBusy, setDebugBusy] = useState(false);
  const [busy, setBusy] = useState(false);

  const groupedEndpoints = useMemo(() => {
    const keyword = searchText.trim().toLowerCase();
    const rows = keyword
      ? endpoints.filter((endpoint) =>
          [endpoint.method, endpoint.path, endpoint.summary, endpoint.description, ...endpoint.tags]
            .join(" ")
            .toLowerCase()
            .includes(keyword),
        )
      : endpoints;

    return rows.reduce<Record<string, ApiAutomationEndpoint[]>>((groups, endpoint) => {
      const groupName = endpointGroupName(endpoint);
      groups[groupName] = [...(groups[groupName] ?? []), endpoint];
      return groups;
    }, {});
  }, [endpoints, searchText]);

  const activeEndpoint = useMemo(
    () => endpoints.find((endpoint) => endpoint.id === activeEndpointId) ?? endpoints[0] ?? null,
    [activeEndpointId, endpoints],
  );

  const readyCases = useMemo(
    () => generationRun?.test_cases?.filter((item) => item.status === "ready") ?? [],
    [generationRun],
  );

  const selectedEnvironment = useMemo(
    () => environments.find((environment) => environment.id === selectedEnvironmentId) ?? environments[0] ?? null,
    [environments, selectedEnvironmentId],
  );

  const filteredEnvironments = useMemo(() => {
    const keyword = environmentSearchText.trim().toLowerCase();
    if (!keyword) {
      return environments;
    }
    return environments.filter((environment) =>
      [
        environment.name,
        environment.api_base_url,
        environment.username,
        environment.auth_type,
        environment.description,
        authTypeLabel(environment.auth_type),
      ]
        .join(" ")
        .toLowerCase()
        .includes(keyword),
    );
  }, [environments, environmentSearchText]);

  const allEnvironmentsSelected =
    filteredEnvironments.length > 0 &&
    filteredEnvironments.every((environment) => selectedEnvironmentIds.includes(environment.id));
  const partiallySelected = filteredEnvironments.some((environment) => selectedEnvironmentIds.includes(environment.id));
  const visibleEndpointIds = useMemo(
    () => Object.values(groupedEndpoints).flatMap((rows) => rows.map((endpoint) => endpoint.id)),
    [groupedEndpoints],
  );
  const selectedVisibleEndpointIds = selectedEndpointAssetIds.filter((id) => visibleEndpointIds.includes(id));

  const activeBaseUrl =
    selectedEnvironment?.api_base_url.trim() ||
    environments.find((item) => item.api_base_url.trim())?.api_base_url.trim() ||
    "";

  function toggleEndpointGroup(group: string) {
    setExpandedEndpointGroups((current) =>
      current.includes(group) ? current.filter((item) => item !== group) : [...current, group],
    );
  }

  async function refresh() {
    setBusy(true);
    try {
      const [endpointRows, environmentRows] = await Promise.all([
        listApiAutomationEndpoints(projectId),
        listApiAutomationEnvironments(projectId),
      ]);
      setEndpoints(endpointRows);
      setSelectedEndpointAssetIds((current) =>
        current.filter((id) => endpointRows.some((endpoint) => endpoint.id === id)),
      );
      setSelectedEndpointIds((current) => current.filter((id) => endpointRows.some((endpoint) => endpoint.id === id)));
      setEnvironments(environmentRows);
      setActiveEndpointId((current) =>
        current && endpointRows.some((endpoint) => endpoint.id === current) ? current : (endpointRows[0]?.id ?? ""),
      );
      setSelectedEnvironmentId((current) =>
        current && environmentRows.some((environment) => environment.id === current)
          ? current
          : (environmentRows[0]?.id ?? ""),
      );
      if (generationRun) {
        setGenerationRun(await getApiAutomationGenerationRun(projectId, generationRun.id));
      }
      if (run) {
        setRun(await getApiAutomationRun(projectId, run.id));
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "刷新失败");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([listApiAutomationEndpoints(projectId), listApiAutomationEnvironments(projectId)])
      .then(([endpointRows, environmentRows]) => {
        if (cancelled) {
          return;
        }
        setEndpoints(endpointRows);
        setEnvironments(environmentRows);
        setActiveEndpointId(endpointRows[0]?.id ?? "");
        setSelectedEnvironmentId(environmentRows[0]?.id ?? "");
      })
      .catch((error) => toast.error(error instanceof Error ? error.message : "接口自动化数据加载失败"));

    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    if (!selectedCaseSetId) {
      setSelectedCaseSet(null);
      return;
    }

    let cancelled = false;
    listApiAutomationCaseSets(projectId)
      .then((caseSets) => {
        if (cancelled) {
          return;
        }
        setSelectedCaseSet(caseSets.find((caseSet) => caseSet.id === selectedCaseSetId) ?? null);
      })
      .catch(() => {
        if (!cancelled) {
          setSelectedCaseSet(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [projectId, selectedCaseSetId]);

  async function handleImportFilesChange(nextFiles: File[]) {
    setOpenApiFiles(nextFiles);
    const file = nextFiles[0];
    if (!file) {
      setOpenApiText("");
      return;
    }
    setOpenApiText(await file.text());
  }

  async function handleImport() {
    const url = openApiUrl.trim();
    const content = openApiText.trim();
    const name =
      importMode === "file"
        ? fileNameWithoutExtension(openApiFiles[0]?.name ?? "") || "OpenAPI"
        : importMode === "url"
          ? "URL OpenAPI"
          : "AI OpenAPI";
    if (importMode === "url" && !url) {
      toast.error("请填写 OpenAPI URL");
      return;
    }
    if (importMode !== "url" && !content) {
      toast.error(importMode === "file" ? "请选择或粘贴 OpenAPI 文件内容" : "请粘贴接口文档内容");
      return;
    }

    setBusy(true);
    try {
      const document = await importOpenApiDocument(
        projectId,
        importMode === "url" ? { source_type: "url", name, url } : { source_type: "file", name, content },
      );
      setOpenApiFiles([]);
      setOpenApiText("");
      setOpenApiUrl("");
      setImportOpen(false);
      await refresh();
      setActiveTab("接口资产");
      toast.success(`导入完成，解析 ${document.endpoint_count} 个接口`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "导入失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateEnvironment() {
    const name = environmentForm.name.trim();
    const apiBaseUrl = environmentForm.apiBaseUrl.trim();
    const timeoutSeconds = Number.parseInt(environmentForm.timeoutSeconds, 10);

    if (!name || !apiBaseUrl) {
      toast.error("请填写环境名称和 API Base URL");
      return;
    }
    if (!Number.isFinite(timeoutSeconds) || timeoutSeconds < 1 || timeoutSeconds > 600) {
      toast.error("超时时间需在 1 到 600 秒之间");
      return;
    }

    let defaultHeaders: Record<string, unknown>;
    let variables: Record<string, unknown>;
    try {
      defaultHeaders = parseJsonObject(environmentForm.defaultHeaders, "默认请求头");
      variables = parseJsonObject(environmentForm.variables, "环境变量");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "环境配置格式不正确");
      return;
    }

    setBusy(true);
    try {
      const payload = {
        name,
        api_base_url: apiBaseUrl,
        username: environmentForm.username,
        password: environmentForm.password,
        auth_type: environmentForm.authType,
        auth_config: {},
        variables,
        default_headers: defaultHeaders,
        timeout_seconds: timeoutSeconds,
        verify_ssl: environmentForm.verifySsl,
        description: environmentForm.description,
      };
      const saved = editingEnvironment
        ? await updateApiAutomationEnvironment(projectId, editingEnvironment.id, payload)
        : await createApiAutomationEnvironment(projectId, payload);
      await refresh();
      setSelectedEnvironmentId(saved.id);
      setEnvironmentOpen(false);
      setEditingEnvironment(null);
      setEnvironmentForm({ ...emptyEnvironmentForm });
      toast.success(editingEnvironment ? "接口环境已更新" : "接口环境已保存");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "环境保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerate() {
    setBusy(true);
    try {
      const created = await generateApiAutomation(projectId, {
        endpoint_ids: selectedEndpointIds,
        api_environment_id: selectedEnvironment?.id ?? null,
        generation_goal: generationGoal,
        include_security_cases: false,
        generate_code: false,
      });
      setGenerationRun(created);
      setActiveTab("测试脚本");
      toast.success("生成任务已创建，稍后刷新查看用例");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "生成失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerateScripts() {
    setBusy(true);
    try {
      const result = await generateApiAutomationScripts(projectId, {
        api_test_case_ids: readyCases.map((item) => item.id),
        api_environment_id: selectedEnvironment?.id ?? null,
      });
      setScripts(result.scripts);
      toast.success("脚本已生成");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "脚本生成失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRun() {
    setBusy(true);
    try {
      const created = await createApiAutomationRun(projectId, {
        script_ids: scripts.map((item) => item.id),
        api_environment_id: selectedEnvironment?.id ?? null,
      });
      setRun(created);
      setActiveTab("运行记录");
      toast.success("执行任务已创建");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "执行失败");
    } finally {
      setBusy(false);
    }
  }

  function toggleEndpoint(endpointId: string) {
    setSelectedEndpointIds((current) =>
      current.includes(endpointId) ? current.filter((item) => item !== endpointId) : [...current, endpointId],
    );
  }

  function toggleEndpointAsset(endpointId: string, checked: boolean) {
    setSelectedEndpointAssetIds((current) =>
      checked ? [...new Set([...current, endpointId])] : current.filter((id) => id !== endpointId),
    );
  }

  function toggleVisibleEndpointAssets(checked: boolean) {
    setSelectedEndpointAssetIds((current) => {
      if (!checked) {
        return current.filter((id) => !visibleEndpointIds.includes(id));
      }
      return [...new Set([...current, ...visibleEndpointIds])];
    });
  }

  async function deleteEndpoints(endpointIds: string[]) {
    const ids = [...new Set(endpointIds)];
    if (ids.length === 0) {
      return;
    }
    setBusy(true);
    try {
      await Promise.all(ids.map((endpointId) => deleteApiAutomationEndpoint(projectId, endpointId)));
      setSelectedEndpointAssetIds((current) => current.filter((id) => !ids.includes(id)));
      setSelectedEndpointIds((current) => current.filter((id) => !ids.includes(id)));
      if (activeEndpointId && ids.includes(activeEndpointId)) {
        setActiveEndpointId("");
      }
      await refresh();
      toast.success(`已删除 ${ids.length} 个接口`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "接口删除失败");
    } finally {
      setBusy(false);
    }
  }

  function openImportDialog(mode: ImportMode) {
    setImportMode(mode);
    setImportOpen(true);
  }

  function openCreateEnvironmentDialog() {
    setEditingEnvironment(null);
    setEnvironmentForm({ ...emptyEnvironmentForm });
    setEnvironmentOpen(true);
  }

  function openEditEnvironmentDialog(environment: ApiAutomationEnvironment) {
    setEditingEnvironment(environment);
    setEnvironmentForm(formFromEnvironment(environment));
    setEnvironmentOpen(true);
  }

  function openEndpointDebugDialog(endpoint: ApiAutomationEndpoint) {
    const nextForm = formFromEndpoint(endpoint, selectedEnvironment?.id ?? "");
    setDebugForm(nextForm);
    setDebugResult(null);
    setDebugOpen(true);
  }

  function updateDebugMapField(section: "pathParams" | "queryParams" | "headers", key: string, value: string) {
    setDebugForm((current) => ({
      ...current,
      [section]: {
        ...current[section],
        [key]: value,
      },
    }));
  }

  async function handleDebugSend() {
    if (!activeEndpoint) {
      return;
    }
    if (!debugForm.environmentId) {
      toast.error("请选择接口环境");
      return;
    }
    let cookies: Record<string, unknown>;
    let body: unknown = null;
    try {
      cookies = parseJsonObject(debugForm.cookies, "Cookie");
      body = parseDebugBody(debugForm.bodyText);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "调试参数格式不正确");
      return;
    }

    setDebugBusy(true);
    setDebugResult(null);
    try {
      const result = await debugApiAutomationEndpoint(projectId, activeEndpoint.id, {
        api_environment_id: debugForm.environmentId,
        path_params: debugForm.pathParams,
        query_params: debugForm.queryParams,
        headers: debugForm.headers,
        cookies,
        body,
      });
      setDebugResult(result);
      if (result.error_message) {
        toast.error("请求发送失败");
      } else {
        toast.success(`请求完成：${result.status_code}`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "请求发送失败");
    } finally {
      setDebugBusy(false);
    }
  }

  function toggleAllEnvironments(checked: boolean) {
    setSelectedEnvironmentIds(checked ? filteredEnvironments.map((environment) => environment.id) : []);
  }

  function toggleEnvironment(environmentId: string, checked: boolean) {
    setSelectedEnvironmentIds((current) =>
      checked ? [...new Set([...current, environmentId])] : current.filter((id) => id !== environmentId),
    );
  }

  async function deleteEnvironments(environmentIds: string[]) {
    if (environmentIds.length === 0) {
      return;
    }
    setBusy(true);
    try {
      await Promise.all(
        environmentIds.map((environmentId) => deleteApiAutomationEnvironment(projectId, environmentId)),
      );
      if (environmentIds.includes(selectedEnvironmentId)) {
        setSelectedEnvironmentId("");
      }
      setSelectedEnvironmentIds([]);
      await refresh();
      toast.success(`已删除 ${environmentIds.length} 个接口环境`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "环境删除失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell
      activeTab={activeTab}
      breadcrumbs={[
        { label: "测试资产" },
        { label: "接口自动化", href: "/automation/api" },
        { label: selectedCaseSet?.name ?? projectName },
      ]}
      description="导入 OpenAPI、生成接口自动化用例、生成 pytest 脚本并执行。"
      onTabChange={setActiveTab}
      projectScope="project"
      tabActions={
        <div className="flex items-center gap-2">
          <Button disabled={busy} onClick={() => openImportDialog("file")}>
            <ImportIcon className="size-4" />
            导入
          </Button>
          <Button disabled={busy} onClick={() => refresh()} size="sm" variant="outline">
            {busy ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
            刷新
          </Button>
        </div>
      }
      tabs={tabs}
      title="接口自动化"
    >
      {activeTab === "接口资产" && (
        <div className="grid min-h-[620px] items-start overflow-visible rounded-xl border bg-background xl:grid-cols-[360px_minmax(0,1fr)]">
          <aside className="no-scrollbar max-h-[calc(100dvh-5rem)] overflow-y-auto overflow-x-hidden border-r bg-muted/20 xl:sticky xl:top-16">
            <div className="border-b p-3">
              <div className="flex items-center gap-2">
                <Checkbox
                  aria-label="选择当前接口列表"
                  checked={
                    visibleEndpointIds.length > 0 &&
                    visibleEndpointIds.every((id) => selectedEndpointAssetIds.includes(id))
                      ? true
                      : selectedVisibleEndpointIds.length > 0
                        ? "indeterminate"
                        : false
                  }
                  disabled={busy || visibleEndpointIds.length === 0}
                  onCheckedChange={(checked) => toggleVisibleEndpointAssets(Boolean(checked))}
                />
                <div className="relative min-w-0 flex-1">
                  <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    className="h-9 bg-background pl-9"
                    onChange={(event) => setSearchText(event.target.value)}
                    placeholder="搜索 method、path、tag"
                    value={searchText}
                  />
                </div>
                {selectedEndpointAssetIds.length > 0 ? (
                  <Button
                    className="border-red-200 bg-red-50 text-red-700 hover:border-red-300 hover:bg-red-100 hover:text-red-800"
                    disabled={busy}
                    onClick={() => deleteEndpoints(selectedEndpointAssetIds)}
                    size="sm"
                    variant="outline"
                  >
                    <Trash2 className="size-4" />
                    删除 ({selectedEndpointAssetIds.length})
                  </Button>
                ) : null}
              </div>
            </div>
            <div className="p-2">
              {Object.entries(groupedEndpoints).map(([group, rows]) => {
                const hasActiveEndpoint = rows.some((endpoint) => endpoint.id === activeEndpoint?.id);
                const isCollapsed = searchText.trim() ? false : !expandedEndpointGroups.includes(group);

                return (
                  <div className="mb-3" key={group}>
                    <button
                      aria-expanded={!isCollapsed}
                      aria-label={`${group} 分组，${rows.length} 个接口，${isCollapsed ? "展开" : "折叠"}`}
                      className={cn(
                        "mb-1 flex w-full items-center gap-2 rounded-md border border-transparent bg-slate-100/70 px-2 py-1.5 text-left font-medium text-muted-foreground text-xs transition-colors hover:border-slate-200 hover:bg-slate-100",
                        hasActiveEndpoint && "border-sky-200 bg-sky-50/80 text-sky-800",
                      )}
                      onClick={() => toggleEndpointGroup(group)}
                      type="button"
                    >
                      {isCollapsed ? (
                        <ChevronRight className="size-3.5 shrink-0" />
                      ) : (
                        <ChevronDown className="size-3.5 shrink-0" />
                      )}
                      <span className="min-w-0 flex-1 truncate">{group}</span>
                      <span className="rounded-full bg-sky-100 px-2 py-0.5 font-semibold text-sky-700 tabular-nums">
                        {rows.length}
                      </span>
                    </button>
                    {isCollapsed ? null : (
                      <div className="space-y-1">
                        {rows.map((endpoint) => (
                          <div
                            className={cn(
                              "flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-background",
                              activeEndpoint?.id === endpoint.id && "bg-background shadow-xs ring-1 ring-border",
                            )}
                            key={endpoint.id}
                          >
                            <Checkbox
                              aria-label={`选择删除 ${endpoint.summary || endpoint.path}`}
                              checked={selectedEndpointAssetIds.includes(endpoint.id)}
                              disabled={busy}
                              onCheckedChange={(checked) => toggleEndpointAsset(endpoint.id, Boolean(checked))}
                            />
                            <button
                              className="flex min-w-0 flex-1 items-center gap-2 text-left"
                              onClick={() => setActiveEndpointId(endpoint.id)}
                              title={endpoint.path}
                              type="button"
                            >
                              <MethodBadge method={endpoint.method} />
                              <span className="min-w-0 flex-1 truncate text-xs">
                                {endpoint.summary || endpoint.path}
                              </span>
                              {selectedEndpointIds.includes(endpoint.id) ? (
                                <CircleCheck className="size-4 shrink-0 text-emerald-600" />
                              ) : null}
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
              {endpoints.length === 0 ? (
                <div className="flex h-full min-h-72 flex-col items-center justify-center gap-3 px-6 text-center text-sm">
                  <FileJson className="size-9 text-muted-foreground" />
                  <div>
                    <div className="font-medium">暂无接口资产</div>
                    <div className="mt-1 text-muted-foreground">从右上角导入 OpenAPI、URL 或粘贴内容。</div>
                  </div>
                  <Button onClick={() => openImportDialog("file")} size="sm">
                    <ImportIcon className="size-4" />
                    导入接口
                  </Button>
                </div>
              ) : null}
            </div>
          </aside>

          <section className="min-w-0">
            {activeEndpoint ? (
              <div>
                <div className="border-b bg-background p-5">
                  <div className="mx-auto max-w-4xl space-y-5">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        {activeEndpoint.tags.length > 0 ? (
                          activeEndpoint.tags.map((tag) => (
                            <Badge className="bg-emerald-50 text-emerald-700" key={tag} variant="secondary">
                              {tag}
                            </Badge>
                          ))
                        ) : (
                          <Badge variant="outline">未分组</Badge>
                        )}
                      </div>
                      <div>
                        <h2 className="font-semibold text-2xl tracking-normal">
                          {activeEndpoint.summary || activeEndpoint.path}
                        </h2>
                        <p className="mt-2 text-muted-foreground text-sm">
                          {activeEndpoint.description || activeEndpoint.summary || "该接口暂无摘要。"}
                        </p>
                      </div>
                    </div>
                    <div className="flex flex-col gap-2 rounded-lg border bg-muted/20 p-2 lg:flex-row lg:items-center">
                      <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md bg-background px-3 py-2 shadow-xs">
                        <MethodBadge method={activeEndpoint.method} />
                        <span className="min-w-0 truncate font-mono text-muted-foreground text-sm">
                          {formatEndpointUrl(activeBaseUrl, activeEndpoint.path)}
                        </span>
                      </div>
                      <Button onClick={() => openEndpointDebugDialog(activeEndpoint)}>
                        <Play className="size-4" />
                        测试一下
                      </Button>
                      <Button onClick={() => toggleEndpoint(activeEndpoint.id)} variant="outline">
                        <CircleCheck className="size-4" />
                        {selectedEndpointIds.includes(activeEndpoint.id) ? "已选择" : "加入生成"}
                      </Button>
                    </div>
                  </div>
                </div>

                <div className="min-w-0">
                  <div className="mx-auto max-w-4xl space-y-8 p-5">
                    <EndpointFieldSection rows={getParameterRows(activeEndpoint.parameters, "header")} title="授权" />
                    <EndpointFieldSection
                      rows={getParameterRows(activeEndpoint.parameters, "path", "query")}
                      title="请求参数"
                    />
                    <EndpointFieldSection
                      contentType={getRequestBodyContentType(activeEndpoint.request_body)}
                      rows={getRequestBodyRows(activeEndpoint.request_body)}
                      title="请求体"
                    />
                    <ResponseSummary responses={activeEndpoint.responses} />
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex h-full min-h-96 items-center justify-center text-muted-foreground text-sm">
                请选择左侧接口查看详情。
              </div>
            )}
          </section>
        </div>
      )}

      {activeTab === "接口环境" && (
        <ShellSection>
          <ListToolbar
            createLabel="新建环境"
            onBatchDelete={() => deleteEnvironments(selectedEnvironmentIds)}
            onCreate={openCreateEnvironmentDialog}
            onSearch={setEnvironmentSearchText}
            placeholder="搜索环境名称、地址、用户名或鉴权方式"
            selectedCount={selectedEnvironmentIds.length}
            title="环境列表"
          />
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <Checkbox
                      aria-label="选择全部接口环境"
                      checked={allEnvironmentsSelected || (partiallySelected ? "indeterminate" : false)}
                      disabled={busy}
                      onCheckedChange={(checked) => toggleAllEnvironments(Boolean(checked))}
                    />
                  </TableHead>
                  <TableHead>环境名称</TableHead>
                  <TableHead>API Base URL</TableHead>
                  <TableHead>鉴权方式</TableHead>
                  <TableHead>超时</TableHead>
                  <TableHead>SSL</TableHead>
                  <TableHead>更新时间</TableHead>
                  <TableHead className="w-16">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredEnvironments.map((environment) => (
                  <TableRow
                    data-state={selectedEnvironmentId === environment.id ? "selected" : undefined}
                    key={environment.id}
                  >
                    <TableCell>
                      <Checkbox
                        aria-label={`选择 ${environment.name}`}
                        checked={selectedEnvironmentIds.includes(environment.id)}
                        onCheckedChange={(checked) => toggleEnvironment(environment.id, Boolean(checked))}
                      />
                    </TableCell>
                    <TableCell className="font-medium">
                      <button
                        className="hover:underline"
                        onClick={() => {
                          setSelectedEnvironmentId(environment.id);
                          openEditEnvironmentDialog(environment);
                        }}
                        type="button"
                      >
                        {environment.name}
                      </button>
                    </TableCell>
                    <TableCell>
                      <span className="block max-w-96 truncate font-mono text-xs" title={environment.api_base_url}>
                        {environment.api_base_url}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{authTypeLabel(environment.auth_type)}</Badge>
                    </TableCell>
                    <TableCell>{environment.timeout_seconds} 秒</TableCell>
                    <TableCell>{environment.verify_ssl ? "开启" : "关闭"}</TableCell>
                    <TableCell>{formatDateTime(environment.updated_at)}</TableCell>
                    <TableCell>
                      <RowActions
                        actions={[
                          {
                            label: "修改",
                            icon: Pencil,
                            onSelect: () => {
                              setSelectedEnvironmentId(environment.id);
                              openEditEnvironmentDialog(environment);
                            },
                          },
                          {
                            label: "删除",
                            icon: Trash2,
                            destructive: true,
                            onSelect: () => deleteEnvironments([environment.id]),
                          },
                        ]}
                        label={`打开 ${environment.name} 操作菜单`}
                      />
                    </TableCell>
                  </TableRow>
                ))}
                {busy && filteredEnvironments.length === 0 ? (
                  <TableLoadingRow colSpan={8} label="环境列表加载中" />
                ) : null}
                {!busy && filteredEnvironments.length === 0 ? (
                  <TableRow>
                    <TableCell className="h-24 text-center text-muted-foreground" colSpan={8}>
                      暂无接口环境。新增环境后，可用于生成用例、生成脚本和执行接口自动化。
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>
        </ShellSection>
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
              <div className="space-y-2">
                <div className="font-medium text-sm">执行环境</div>
                <Select value={selectedEnvironment?.id ?? ""} onValueChange={setSelectedEnvironmentId}>
                  <SelectTrigger className="h-9 w-full">
                    <SelectValue placeholder="选择接口环境" />
                  </SelectTrigger>
                  <SelectContent>
                    {environments.map((environment) => (
                      <SelectItem key={environment.id} value={environment.id}>
                        {environment.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="text-muted-foreground text-xs">
                  {selectedEnvironment?.api_base_url ?? "请先在接口环境页签新建环境。"}
                </div>
              </div>
              <Textarea value={generationGoal} onChange={(event) => setGenerationGoal(event.target.value)} />
              <Button
                disabled={busy || selectedEndpointIds.length === 0 || !selectedEnvironment}
                onClick={handleGenerate}
              >
                生成用例
              </Button>
              <Button
                disabled={busy || readyCases.length === 0 || !selectedEnvironment}
                onClick={handleGenerateScripts}
                variant="outline"
              >
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
                  <div className="flex items-center justify-between gap-3">
                    <span className="min-w-0 truncate">{item.title}</span>
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
            <div className="grid gap-2 sm:max-w-md">
              <div className="font-medium text-sm">执行环境</div>
              <Select value={selectedEnvironment?.id ?? ""} onValueChange={setSelectedEnvironmentId}>
                <SelectTrigger className="h-9 w-full">
                  <SelectValue placeholder="选择接口环境" />
                </SelectTrigger>
                <SelectContent>
                  {environments.map((environment) => (
                    <SelectItem key={environment.id} value={environment.id}>
                      {environment.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button disabled={busy || scripts.length === 0 || !selectedEnvironment} onClick={handleRun}>
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

      <Dialog open={environmentOpen} onOpenChange={setEnvironmentOpen}>
        <DialogContent className="max-h-[calc(100vh-2rem)] overflow-hidden p-0 sm:max-w-3xl">
          <DialogHeader className="px-6 pt-6">
            <DialogTitle>{editingEnvironment ? "修改接口环境" : "新建接口环境"}</DialogTitle>
            <DialogDescription>配置接口执行目标、鉴权和请求参数，供生成与运行复用。</DialogDescription>
          </DialogHeader>
          <div className="grid min-h-0 gap-4 overflow-y-auto px-6 py-5 md:grid-cols-2">
            <FieldText
              label="环境名称"
              onChange={(value) => setEnvironmentForm((current) => ({ ...current, name: value }))}
              placeholder="测试环境"
              value={environmentForm.name}
            />
            <FieldText
              label="API Base URL"
              mono
              onChange={(value) => setEnvironmentForm((current) => ({ ...current, apiBaseUrl: value }))}
              placeholder="https://api.example.com"
              value={environmentForm.apiBaseUrl}
            />
            <div className="space-y-2">
              <div className="font-medium text-sm">鉴权方式</div>
              <Select
                value={environmentForm.authType}
                onValueChange={(value) =>
                  setEnvironmentForm((current) => ({ ...current, authType: value as EnvironmentForm["authType"] }))
                }
              >
                <SelectTrigger className="h-9 w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {authTypeOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <FieldText
              label="用户名"
              onChange={(value) => setEnvironmentForm((current) => ({ ...current, username: value }))}
              placeholder="可选"
              value={environmentForm.username}
            />
            <FieldText
              label="密码 / Token"
              onChange={(value) => setEnvironmentForm((current) => ({ ...current, password: value }))}
              placeholder="可选"
              type="password"
              value={environmentForm.password}
            />
            <FieldText
              label="超时时间（秒）"
              onChange={(value) => setEnvironmentForm((current) => ({ ...current, timeoutSeconds: value }))}
              placeholder="30"
              value={environmentForm.timeoutSeconds}
            />
            <div className="flex items-center gap-3 rounded-md border bg-muted/20 px-3 py-2">
              <Checkbox
                checked={environmentForm.verifySsl}
                id="api-environment-verify-ssl"
                onCheckedChange={(checked) =>
                  setEnvironmentForm((current) => ({ ...current, verifySsl: checked === true }))
                }
              />
              <label className="font-medium text-sm" htmlFor="api-environment-verify-ssl">
                校验 SSL 证书
              </label>
            </div>
            <div className="space-y-2 md:col-span-2">
              <div className="font-medium text-sm">默认请求头（JSON）</div>
              <Textarea
                className="min-h-28 font-mono text-xs"
                onChange={(event) =>
                  setEnvironmentForm((current) => ({ ...current, defaultHeaders: event.target.value }))
                }
                value={environmentForm.defaultHeaders}
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <div className="font-medium text-sm">环境变量（JSON）</div>
              <Textarea
                className="min-h-28 font-mono text-xs"
                onChange={(event) => setEnvironmentForm((current) => ({ ...current, variables: event.target.value }))}
                value={environmentForm.variables}
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <div className="font-medium text-sm">描述</div>
              <Textarea
                onChange={(event) => setEnvironmentForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="用于说明环境用途、网络限制或数据注意事项"
                value={environmentForm.description}
              />
            </div>
          </div>
          <DialogFooter className="m-0 px-6 py-4">
            <Button onClick={() => setEnvironmentOpen(false)} type="button" variant="outline">
              <X className="size-4" />
              取消
            </Button>
            <Button disabled={busy} onClick={handleCreateEnvironment} type="button">
              {busy ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}
              保存环境
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={debugOpen} onOpenChange={setDebugOpen}>
        <DialogContent className="max-h-[calc(100vh-2rem)] overflow-hidden p-0 sm:max-w-5xl">
          <DialogHeader className="px-6 pt-6">
            <DialogTitle>接口调试</DialogTitle>
            <DialogDescription>通过后端代理发送请求，填写参数后可查看响应状态、耗时和返回内容。</DialogDescription>
          </DialogHeader>
          <div className="min-h-0 space-y-5 overflow-y-auto px-6 py-5">
            {activeEndpoint ? (
              <div className="flex flex-col gap-2 rounded-lg border bg-muted/20 p-2 lg:flex-row lg:items-center">
                <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md bg-background px-3 py-2 shadow-xs">
                  <MethodBadge method={activeEndpoint.method} />
                  <span className="min-w-0 truncate font-mono text-muted-foreground text-sm">
                    {formatEndpointUrl(
                      environments.find((environment) => environment.id === debugForm.environmentId)?.api_base_url ??
                        activeBaseUrl,
                      activeEndpoint.path,
                    )}
                  </span>
                </div>
                <Select
                  value={debugForm.environmentId}
                  onValueChange={(value) => setDebugForm((current) => ({ ...current, environmentId: value }))}
                >
                  <SelectTrigger className="h-9 w-full bg-background lg:w-56">
                    <SelectValue placeholder="选择接口环境" />
                  </SelectTrigger>
                  <SelectContent>
                    {environments.map((environment) => (
                      <SelectItem key={environment.id} value={environment.id}>
                        {environment.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}

            <div className="grid gap-5 lg:grid-cols-2">
              <DebugMapSection
                emptyLabel="该接口没有路径参数。"
                fields={debugForm.pathParams}
                onChange={(key, value) => updateDebugMapField("pathParams", key, value)}
                rows={activeEndpoint ? getParameterRows(activeEndpoint.parameters, "path") : []}
                title="路径参数"
              />
              <DebugMapSection
                emptyLabel="该接口没有 Query 参数。"
                fields={debugForm.queryParams}
                onChange={(key, value) => updateDebugMapField("queryParams", key, value)}
                rows={activeEndpoint ? getParameterRows(activeEndpoint.parameters, "query") : []}
                title="Query 参数"
              />
              <DebugMapSection
                emptyLabel="该接口没有 Header 参数。环境默认请求头会在后端自动合并。"
                fields={debugForm.headers}
                onChange={(key, value) => updateDebugMapField("headers", key, value)}
                rows={activeEndpoint ? getParameterRows(activeEndpoint.parameters, "header") : []}
                title="Header 参数"
              />
              <div className="space-y-2">
                <div className="font-medium text-sm">Cookie（JSON）</div>
                <Textarea
                  className="min-h-32 font-mono text-xs"
                  onChange={(event) => setDebugForm((current) => ({ ...current, cookies: event.target.value }))}
                  value={debugForm.cookies}
                />
              </div>
            </div>

            {activeEndpoint && getRequestBodyRows(activeEndpoint.request_body).length > 0 ? (
              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-medium text-sm">请求体</div>
                  <ContentTypeBadge
                    value={getRequestBodyContentType(activeEndpoint.request_body) || "application/json"}
                  />
                </div>
                <Textarea
                  className="min-h-44 font-mono text-xs"
                  onChange={(event) => setDebugForm((current) => ({ ...current, bodyText: event.target.value }))}
                  placeholder='{"key":"value"}'
                  value={debugForm.bodyText}
                />
              </div>
            ) : null}

            {debugResult ? (
              <div className="space-y-3 rounded-lg border bg-background p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge className="font-mono" variant={debugResult.error_message ? "destructive" : "outline"}>
                    {debugResult.error_message ? "ERR" : debugResult.status_code}
                  </Badge>
                  <span className="text-muted-foreground text-sm">{debugResult.elapsed_ms} ms</span>
                  {debugResult.error_message ? (
                    <span className="text-red-600 text-sm">{debugResult.error_message}</span>
                  ) : null}
                </div>
                <div className="grid gap-3 lg:grid-cols-2">
                  <DebugResultBlock title="请求信息" value={JSON.stringify(debugResult.request, null, 2)} />
                  <DebugResultBlock title="响应头" value={JSON.stringify(debugResult.headers, null, 2)} />
                </div>
                <DebugResultBlock
                  title="响应内容"
                  value={
                    debugResult.body_json === null
                      ? debugResult.body_text || "(空响应)"
                      : JSON.stringify(debugResult.body_json, null, 2)
                  }
                />
              </div>
            ) : null}
          </div>
          <DialogFooter className="m-0 px-6 py-4">
            <Button onClick={() => setDebugOpen(false)} type="button" variant="outline">
              <X className="size-4" />
              关闭
            </Button>
            <Button
              disabled={debugBusy || !activeEndpoint || environments.length === 0}
              onClick={handleDebugSend}
              type="button"
            >
              {debugBusy ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
              发送
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="max-h-[calc(100vh-2rem)] overflow-hidden p-0 sm:max-w-3xl">
          <DialogHeader className="sr-only">
            <DialogTitle>导入接口</DialogTitle>
            <DialogDescription>选择一种来源，导入后会解析为接口资产并在列表中展示。</DialogDescription>
          </DialogHeader>
          <div className="min-h-0 space-y-4 overflow-y-auto px-6 py-5">
            <div className="max-w-xs space-y-2">
              <div className="font-medium text-sm">导入方式</div>
              <AnimatedSelect
                className="w-52 min-w-0"
                placeholder="选择导入方式"
                setValue={(value) => setImportMode(value as ImportMode)}
                value={importMode}
              >
                {importModes.map((mode) => (
                  <SelectOption key={mode.value} value={mode.value}>
                    {mode.label}
                  </SelectOption>
                ))}
              </AnimatedSelect>
              <div className="text-muted-foreground text-xs">
                {importModes.find((mode) => mode.value === importMode)?.description}
              </div>
            </div>
            <div className="space-y-3">
              {importMode === "url" ? (
                <Input
                  placeholder="https://example.com/openapi.json"
                  value={openApiUrl}
                  onChange={(event) => setOpenApiUrl(event.target.value)}
                />
              ) : (
                <>
                  {importMode === "file" ? (
                    <FileUpload1
                      accept={{
                        "application/json": [".json"],
                        "application/x-yaml": [".yaml", ".yml"],
                        "text/yaml": [".yaml", ".yml"],
                      }}
                      files={openApiFiles}
                      hint="仅支持 OpenAPI/Swagger文件"
                      maxFiles={1}
                      onFilesChange={handleImportFilesChange}
                      title="上传接口文件"
                    />
                  ) : null}
                  {importMode === "ai" ? (
                    <Textarea
                      className="min-h-[260px] font-mono text-xs"
                      placeholder="粘贴接口说明、OpenAPI 片段或完整 Swagger 文档"
                      value={openApiText}
                      onChange={(event) => setOpenApiText(event.target.value)}
                    />
                  ) : null}
                </>
              )}
            </div>
          </div>
          <DialogFooter className="m-0 px-6 py-4">
            <Button onClick={() => setImportOpen(false)} type="button" variant="outline">
              <X className="size-4" />
              取消
            </Button>
            <Button disabled={busy} onClick={handleImport} type="button">
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Braces className="size-4" />}
              导入
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}

function fileNameWithoutExtension(filename: string) {
  const baseName = filename.replace(/\\/g, "/").split("/").pop() ?? filename;
  return baseName.replace(/\.(json|ya?ml)$/i, "");
}

function FieldText({
  label,
  mono,
  onChange,
  placeholder,
  type,
  value,
}: {
  label: string;
  mono?: boolean;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
  value: string;
}) {
  return (
    <div className="space-y-2">
      <div className="font-medium text-sm">{label}</div>
      <Input
        className={mono ? "font-mono text-xs" : undefined}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        type={type}
        value={value}
      />
    </div>
  );
}

function DebugMapSection({
  title,
  rows,
  fields,
  emptyLabel,
  onChange,
}: {
  title: string;
  rows: ApiFieldRow[];
  fields: Record<string, string>;
  emptyLabel: string;
  onChange: (key: string, value: string) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="font-medium text-sm">{title}</div>
      {rows.length === 0 ? (
        <div className="rounded-md border bg-muted/20 px-3 py-2 text-muted-foreground text-sm">{emptyLabel}</div>
      ) : (
        <div className="space-y-2">
          {rows.map((row) => (
            <div className="grid gap-2 sm:grid-cols-[minmax(140px,0.9fr)_1fr]" key={`${row.location}-${row.name}`}>
              <div className="flex min-w-0 items-center gap-2">
                <span className="truncate font-mono text-sm" title={row.name}>
                  {row.name}
                </span>
                {row.required ? (
                  <Badge className="bg-rose-50 text-rose-600" variant="secondary">
                    必填
                  </Badge>
                ) : null}
              </div>
              <Input
                className="font-mono text-xs"
                onChange={(event) => onChange(row.name, event.target.value)}
                placeholder={row.description || row.type}
                value={fields[row.name] ?? ""}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DebugResultBlock({ title, value }: { title: string; value: string }) {
  return (
    <div className="min-w-0 space-y-2">
      <div className="font-medium text-sm">{title}</div>
      <pre className="max-h-72 overflow-auto rounded-md bg-slate-950 p-3 font-mono text-slate-50 text-xs">{value}</pre>
    </div>
  );
}

function authTypeLabel(value: string) {
  return authTypeOptions.find((option) => option.value === value)?.label ?? value;
}

function formFromEndpoint(endpoint: ApiAutomationEndpoint, environmentId: string): EndpointDebugForm {
  const requestSchema = getRequestBodySchema(endpoint.request_body);
  const bodyExample =
    Object.keys(requestSchema).length > 0 ? JSON.stringify(exampleFromSchema(requestSchema), null, 2) : "";
  return {
    environmentId,
    pathParams: rowsToEmptyValues(getParameterRows(endpoint.parameters, "path")),
    queryParams: rowsToEmptyValues(getParameterRows(endpoint.parameters, "query")),
    headers: rowsToEmptyValues(getParameterRows(endpoint.parameters, "header")),
    cookies: "{}",
    bodyText: bodyExample,
  };
}

function formFromEnvironment(environment: ApiAutomationEnvironment): EnvironmentForm {
  return {
    name: environment.name,
    apiBaseUrl: environment.api_base_url,
    authType: (authTypeOptions.some((option) => option.value === environment.auth_type)
      ? environment.auth_type
      : "none") as EnvironmentForm["authType"],
    username: environment.username,
    password: "",
    defaultHeaders: JSON.stringify(environment.default_headers ?? {}, null, 2),
    variables: JSON.stringify(environment.variables ?? {}, null, 2),
    timeoutSeconds: String(environment.timeout_seconds),
    verifySsl: environment.verify_ssl,
    description: environment.description,
  };
}

function rowsToEmptyValues(rows: ApiFieldRow[]): Record<string, string> {
  return Object.fromEntries(rows.map((row) => [row.name, ""]));
}

function parseDebugBody(value: string): unknown {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  try {
    return JSON.parse(trimmed) as unknown;
  } catch {
    throw new Error("请求体必须是合法 JSON");
  }
}

function endpointGroupName(endpoint: ApiAutomationEndpoint) {
  const tag = endpoint.tags[0]?.trim();
  if (tag) {
    return tag;
  }
  return "未分组";
}

function parseJsonObject(value: string, label: string): Record<string, unknown> {
  const trimmed = value.trim();
  if (!trimmed) {
    return {};
  }
  const parsed = JSON.parse(trimmed) as unknown;
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error(`${label}必须是 JSON 对象`);
  }
  return parsed as Record<string, unknown>;
}

function MethodBadge({ method }: { method: string }) {
  const upper = method.toUpperCase();
  const tone =
    {
      GET: "border-emerald-200 bg-emerald-50 text-emerald-700",
      POST: "border-sky-200 bg-sky-50 text-sky-700",
      PUT: "border-amber-200 bg-amber-50 text-amber-700",
      PATCH: "border-violet-200 bg-violet-50 text-violet-700",
      DELETE: "border-rose-200 bg-rose-50 text-rose-700",
    }[upper] ?? "border-slate-200 bg-slate-50 text-slate-700";

  return (
    <span
      className={cn(
        "inline-flex h-6 min-w-14 items-center justify-center rounded border px-2 font-semibold text-xs",
        tone,
      )}
    >
      {upper}
    </span>
  );
}

function EndpointFieldSection({
  title,
  rows,
  contentType,
}: {
  title: string;
  rows: ApiFieldRow[];
  contentType?: string;
}) {
  if (rows.length === 0) {
    return null;
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3 border-b pb-2">
        <h3 className="font-semibold text-lg">{title}</h3>
        {contentType ? <ContentTypeBadge value={contentType} /> : null}
      </div>
      <div className="divide-y rounded-md border border-transparent">
        {rows.map((row) => (
          <FieldRow key={`${row.location}-${row.name}`} row={row} />
        ))}
      </div>
    </section>
  );
}

function FieldRow({ row }: { row: ApiFieldRow }) {
  return (
    <div className="grid gap-3 py-3 md:grid-cols-[minmax(220px,1.1fr)_64px_64px_56px_minmax(220px,1.4fr)] md:items-center md:gap-2">
      <span
        className="min-w-0 truncate font-mono font-semibold text-emerald-600 text-sm"
        style={{ paddingLeft: `${(row.depth ?? 0) * 16}px` }}
        title={row.name}
      >
        {row.name}
      </span>
      <Badge className="w-fit" variant="secondary">
        {row.type}
      </Badge>
      <Badge className="w-fit" variant="secondary">
        {row.location}
      </Badge>
      {row.required ? (
        <Badge className="w-fit bg-rose-50 text-rose-600" variant="secondary">
          必填
        </Badge>
      ) : (
        <span className="hidden md:block" />
      )}
      <p className="min-w-0 text-muted-foreground text-sm">{row.description || "暂无说明"}</p>
    </div>
  );
}

function ResponseSummary({ responses }: { responses: Record<string, unknown> }) {
  const entries = Object.entries(responses);
  if (entries.length === 0) {
    return null;
  }

  return (
    <section className="space-y-3">
      <div className="border-b pb-2">
        <h3 className="font-semibold text-lg">响应信息</h3>
      </div>
      <div className="space-y-3">
        {entries.map(([status, value]) => {
          const response = asRecord(value);
          const contentEntries = Object.entries(asRecord(response.content));
          const responseRows = contentEntries.flatMap(([contentType, content]) =>
            getSchemaRows(asRecord(asRecord(content).schema), {
              fallbackName: contentType,
              location: "response",
            }),
          );
          const responseDescription =
            asString(response.description) || (status.startsWith("2") ? "Successful Response" : "响应定义");
          return (
            <div className="overflow-hidden rounded-md border bg-background" key={status}>
              <div className="flex flex-wrap items-center gap-2 border-b bg-muted/20 px-4 py-3">
                <Badge className="bg-background px-2.5 font-mono" variant="outline">
                  {status}
                </Badge>
                <span className="font-medium text-sm">{responseDescription}</span>
                {contentEntries.length > 0 ? (
                  <div className="ml-auto flex flex-wrap justify-end gap-2">
                    {contentEntries.map(([contentType]) => (
                      <ContentTypeBadge key={contentType} value={contentType} />
                    ))}
                  </div>
                ) : null}
              </div>
              {responseRows.length > 0 ? (
                <div className="divide-y px-4 py-1">
                  {responseRows.map((row) => (
                    <FieldRow key={`${status}-${row.location}-${row.name}`} row={row} />
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ContentTypeBadge({ value }: { value: string }) {
  return (
    <span className="inline-flex items-center rounded-md border bg-muted/40 px-2 py-1 font-mono text-muted-foreground text-xs">
      {value}
    </span>
  );
}

function formatEndpointUrl(baseUrl: string, path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return baseUrl ? `${baseUrl.replace(/\/+$/, "")}${normalizedPath}` : normalizedPath;
}

function getParameterRows(parameters: Record<string, unknown>[], ...locations: string[]): ApiFieldRow[] {
  const acceptedLocations = new Set(locations);
  return parameters
    .map((parameter) => {
      const schema = asRecord(parameter.schema);
      return {
        name: asString(parameter.name) || "-",
        location: asString(parameter.in) || "param",
        type: getSchemaType(schema),
        required: Boolean(parameter.required),
        description: asString(parameter.description),
      };
    })
    .filter((row) => acceptedLocations.has(row.location));
}

function getRequestBodyRows(requestBody: Record<string, unknown>): ApiFieldRow[] {
  const schema = getRequestBodySchema(requestBody);
  return getSchemaRows(schema, {
    fallbackName: "body",
    location: "body",
    required: Boolean(requestBody.required),
    description: asString(requestBody.description),
  });
}

function getRequestBodyContentType(requestBody: Record<string, unknown>) {
  return Object.keys(asRecord(requestBody.content))[0] ?? "";
}

function getRequestBodySchema(requestBody: Record<string, unknown>) {
  const content = asRecord(requestBody.content);
  const contentType = getRequestBodyContentType(requestBody);
  return asRecord(asRecord(content[contentType]).schema);
}

function exampleFromSchema(schema: Record<string, unknown>): unknown {
  const example = schema.example;
  if (example !== undefined) {
    return example;
  }
  const defaultValue = schema.default;
  if (defaultValue !== undefined) {
    return defaultValue;
  }
  const properties = asRecord(schema.properties);
  if (Object.keys(properties).length > 0) {
    const required = new Set(asStringArray(schema.required));
    const entries = Object.entries(properties).filter(([name]) => required.size === 0 || required.has(name));
    return Object.fromEntries(entries.map(([name, value]) => [name, exampleFromSchema(asRecord(value))]));
  }
  const type = asString(schema.type);
  if (type === "array") {
    return [exampleFromSchema(asRecord(schema.items))];
  }
  if (type === "integer" || type === "number") {
    return 0;
  }
  if (type === "boolean") {
    return false;
  }
  if (type === "object") {
    return {};
  }
  return "";
}

function getSchemaType(schema: Record<string, unknown>): string {
  const ref = asString(schema.$ref);
  if (ref) {
    return ref.split("/").at(-1) ?? "object";
  }
  const type = asString(schema.type);
  const format = asString(schema.format);
  if (type === "array") {
    return `${getSchemaType(asRecord(schema.items))}[]`;
  }
  return [type || "object", format].filter(Boolean).join("<") + (type && format ? ">" : "");
}

function getSchemaRows(
  schema: Record<string, unknown>,
  options: { fallbackName: string; location: string; required?: boolean; description?: string; depth?: number },
): ApiFieldRow[] {
  if (Object.keys(schema).length === 0) {
    return [];
  }

  const properties = asRecord(schema.properties);
  if (Object.keys(properties).length === 0) {
    return [
      {
        name: options.fallbackName,
        location: options.location,
        type: getSchemaType(schema),
        required: Boolean(options.required),
        description: options.description ?? asString(schema.description),
        depth: options.depth ?? 0,
      },
    ];
  }

  const required = new Set(asStringArray(schema.required));
  return Object.entries(properties).flatMap(([name, value]) => {
    const propertySchema = asRecord(value);
    const row: ApiFieldRow = {
      name,
      location: options.location,
      type: getSchemaType(propertySchema),
      required: required.has(name),
      description: asString(propertySchema.description),
      depth: options.depth ?? 0,
    };
    const children = getSchemaRows(propertySchema, {
      fallbackName: name,
      location: options.location,
      depth: (options.depth ?? 0) + 1,
    });
    return children.length > 1 || children[0]?.name !== name ? [row, ...children] : [row];
  });
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}
