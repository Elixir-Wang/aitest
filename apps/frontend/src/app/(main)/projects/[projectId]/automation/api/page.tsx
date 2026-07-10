"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import Image from "next/image";
import { useParams, useRouter, useSearchParams } from "next/navigation";

import {
  Braces,
  ChevronDown,
  ChevronRight,
  ClipboardPaste,
  Eye,
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
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import {
  type ApiAutomationCaseSet,
  type ApiAutomationDebugResult,
  type ApiAutomationEndpoint,
  type ApiAutomationEnvironment,
  type ApiAutomationGenerationRun,
  type ApiAutomationRun,
  type ApiAutomationScript,
  type ApiAutomationTestCase,
  createApiAutomationEnvironment,
  createApiAutomationRun,
  debugApiAutomationEndpoint,
  deleteApiAutomationEndpoint,
  deleteApiAutomationEnvironment,
  deleteApiAutomationTestCase,
  formatDateTime,
  generateApiAutomationTestCases,
  getApiAutomationGenerationRun,
  getApiAutomationRun,
  importOpenApiDocument,
  listApiAutomationCaseSets,
  listApiAutomationEndpoints,
  listApiAutomationEnvironments,
  listApiAutomationTestCases,
  updateApiAutomationEnvironment,
} from "@/lib/api-client";
import { cn } from "@/lib/utils";

const tabs = ["接口资产", "接口环境", "接口用例", "测试脚本", "运行记录", "场景编排"];
const API_GENERATION_ACTIVE_STATUSES = new Set(["queued", "running"]);
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
type EnvironmentAuthType = "none" | "account_password" | "cybertron_agent";
type EnvironmentForm = {
  name: string;
  apiBaseUrl: string;
  authType: EnvironmentAuthType;
  username: string;
  password: string;
  cybertronRobotKey: string;
  cybertronRobotToken: string;
  cybertronUsername: string;
  defaultHeaders: string;
  timeoutSeconds: string;
  description: string;
};

const authTypeOptions = [
  { value: "none", label: "无需鉴权" },
  { value: "account_password", label: "账号密码" },
  { value: "cybertron_agent", label: "塞伯坦智能体" },
] as const;

const emptyEnvironmentForm: EnvironmentForm = {
  name: "测试环境",
  apiBaseUrl: "",
  authType: "none",
  username: "",
  password: "",
  cybertronRobotKey: "",
  cybertronRobotToken: "",
  cybertronUsername: "",
  defaultHeaders: JSON.stringify({}, null, 2),
  timeoutSeconds: "30",
  description: "",
};
type ApiFieldRow = {
  name: string;
  location: string;
  type: string;
  required: boolean;
  description: string;
  constraints: string[];
  depth?: number;
};
type EndpointDebugForm = {
  environmentId: string;
  pathParams: Record<string, string>;
  queryParams: Record<string, string>;
  headers: Record<string, string>;
  bodyText: string;
};
const emptyDebugForm: EndpointDebugForm = {
  environmentId: "",
  pathParams: {},
  queryParams: {},
  headers: {},
  bodyText: "",
};

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = params.projectId;
  const selectedCaseSetId = searchParams.get("set");
  const [activeTab, setActiveTab] = useState(tabs[0]);
  const [selectedCaseSet, setSelectedCaseSet] = useState<ApiAutomationCaseSet | null>(null);
  const [endpoints, setEndpoints] = useState<ApiAutomationEndpoint[]>([]);
  const [environments, setEnvironments] = useState<ApiAutomationEnvironment[]>([]);
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState("");
  const [generationRun, setGenerationRun] = useState<ApiAutomationGenerationRun | null>(null);
  const [generateBusy, setGenerateBusy] = useState(false);
  const [apiTestCases, setApiTestCases] = useState<ApiAutomationTestCase[]>([]);
  const [selectedApiCaseIds, setSelectedApiCaseIds] = useState<string[]>([]);
  const [apiCaseSearchText, setApiCaseSearchText] = useState("");
  const [activeApiCaseEndpointId, setActiveApiCaseEndpointId] = useState("");
  const [selectedApiCaseEndpointIds, setSelectedApiCaseEndpointIds] = useState<string[]>([]);
  const [expandedApiCaseEndpointGroups, setExpandedApiCaseEndpointGroups] = useState<string[]>([]);
  const [scripts] = useState<ApiAutomationScript[]>([]);
  const [run, setRun] = useState<ApiAutomationRun | null>(null);
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

  const apiCaseCountByEndpointId = useMemo(() => {
    return apiTestCases.reduce<Record<string, number>>((counts, testCase) => {
      if (!testCase.endpoint_id) {
        return counts;
      }
      counts[testCase.endpoint_id] = (counts[testCase.endpoint_id] ?? 0) + 1;
      return counts;
    }, {});
  }, [apiTestCases]);

  const apiCaseEndpoints = useMemo(
    () => endpoints.filter((endpoint) => (apiCaseCountByEndpointId[endpoint.id] ?? 0) > 0),
    [apiCaseCountByEndpointId, endpoints],
  );

  const activeApiCaseEndpoint = useMemo(
    () => apiCaseEndpoints.find((endpoint) => endpoint.id === activeApiCaseEndpointId) ?? apiCaseEndpoints[0] ?? null,
    [activeApiCaseEndpointId, apiCaseEndpoints],
  );

  const groupedApiCaseEndpoints = useMemo(() => {
    return apiCaseEndpoints.reduce<Record<string, ApiAutomationEndpoint[]>>((groups, endpoint) => {
      const groupName = endpointGroupName(endpoint);
      groups[groupName] = [...(groups[groupName] ?? []), endpoint];
      return groups;
    }, {});
  }, [apiCaseEndpoints]);

  const filteredApiTestCases = useMemo(() => {
    const keyword = apiCaseSearchText.trim().toLowerCase();
    return apiTestCases.filter((testCase) => {
      if (!activeApiCaseEndpoint || testCase.endpoint_id !== activeApiCaseEndpoint.id) {
        return false;
      }
      const matchesSearch =
        !keyword ||
        [testCase.title, testCase.priority, testCase.source, formatDateTime(testCase.updated_at)]
          .join(" ")
          .toLowerCase()
          .includes(keyword);
      return matchesSearch;
    });
  }, [activeApiCaseEndpoint, apiCaseSearchText, apiTestCases]);

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
  const visibleApiCaseEndpointIds = useMemo(
    () => Object.values(groupedApiCaseEndpoints).flatMap((rows) => rows.map((endpoint) => endpoint.id)),
    [groupedApiCaseEndpoints],
  );
  const selectedVisibleEndpointIds = selectedEndpointAssetIds.filter((id) => visibleEndpointIds.includes(id));
  const selectedVisibleApiCaseEndpointIds = selectedApiCaseEndpointIds.filter((id) =>
    visibleApiCaseEndpointIds.includes(id),
  );
  const allApiCasesSelected =
    filteredApiTestCases.length > 0 &&
    filteredApiTestCases.every((testCase) => selectedApiCaseIds.includes(testCase.id));
  const partiallyApiCasesSelected = filteredApiTestCases.some((testCase) => selectedApiCaseIds.includes(testCase.id));

  const activeBaseUrl =
    selectedEnvironment?.api_base_url.trim() ||
    environments.find((item) => item.api_base_url.trim())?.api_base_url.trim() ||
    "";

  const applyGenerationRun = useCallback((nextRun: ApiAutomationGenerationRun) => {
    setGenerationRun(nextRun);
    if (nextRun.test_cases) {
      setApiTestCases(nextRun.test_cases);
      setSelectedApiCaseIds((current) =>
        current.filter((id) => nextRun.test_cases?.some((testCase) => testCase.id === id)),
      );
      setSelectedApiCaseEndpointIds((current) =>
        current.filter((id) => nextRun.test_cases?.some((testCase) => testCase.endpoint_id === id)),
      );
      const firstGeneratedEndpointId =
        nextRun.endpoint_ids[0] ?? nextRun.test_cases.find((testCase) => testCase.endpoint_id)?.endpoint_id ?? "";
      if (firstGeneratedEndpointId) {
        setActiveApiCaseEndpointId(firstGeneratedEndpointId);
      }
    }
  }, []);

  function toggleEndpointGroup(group: string) {
    setExpandedEndpointGroups((current) =>
      current.includes(group) ? current.filter((item) => item !== group) : [...current, group],
    );
  }

  function toggleApiCaseEndpointGroup(group: string) {
    setExpandedApiCaseEndpointGroups((current) =>
      current.includes(group) ? current.filter((item) => item !== group) : [...current, group],
    );
  }

  async function refresh() {
    setBusy(true);
    try {
      const [endpointRows, environmentRows, apiCaseRows] = await Promise.all([
        listApiAutomationEndpoints(projectId),
        listApiAutomationEnvironments(projectId),
        listApiAutomationTestCases(projectId),
      ]);
      setEndpoints(endpointRows);
      setSelectedEndpointAssetIds((current) =>
        current.filter((id) => endpointRows.some((endpoint) => endpoint.id === id)),
      );
      setApiTestCases(apiCaseRows);
      setSelectedApiCaseIds((current) => current.filter((id) => apiCaseRows.some((testCase) => testCase.id === id)));
      setSelectedApiCaseEndpointIds((current) =>
        current.filter((id) => apiCaseRows.some((testCase) => testCase.endpoint_id === id)),
      );
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
    Promise.all([
      listApiAutomationEndpoints(projectId),
      listApiAutomationEnvironments(projectId),
      listApiAutomationTestCases(projectId),
    ])
      .then(([endpointRows, environmentRows, apiCaseRows]) => {
        if (cancelled) {
          return;
        }
        setEndpoints(endpointRows);
        setEnvironments(environmentRows);
        setApiTestCases(apiCaseRows);
        setSelectedApiCaseIds((current) => current.filter((id) => apiCaseRows.some((testCase) => testCase.id === id)));
        setSelectedApiCaseEndpointIds((current) =>
          current.filter((id) => apiCaseRows.some((testCase) => testCase.endpoint_id === id)),
        );
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

  useEffect(() => {
    if (apiCaseEndpoints.length === 0) {
      setActiveApiCaseEndpointId("");
      setSelectedApiCaseEndpointIds([]);
      setExpandedApiCaseEndpointGroups([]);
      return;
    }

    setSelectedApiCaseEndpointIds((current) =>
      current.filter((id) => apiCaseEndpoints.some((endpoint) => endpoint.id === id)),
    );

    if (!apiCaseEndpoints.some((endpoint) => endpoint.id === activeApiCaseEndpointId)) {
      setActiveApiCaseEndpointId(apiCaseEndpoints[0]?.id ?? "");
    }

    setExpandedApiCaseEndpointGroups((current) => {
      const groups = [...new Set(apiCaseEndpoints.map((endpoint) => endpointGroupName(endpoint)))];
      if (current.length > 0) {
        return current.filter((group) => groups.includes(group));
      }
      return groups;
    });
  }, [activeApiCaseEndpointId, apiCaseEndpoints]);

  useEffect(() => {
    if (!generationRun || !API_GENERATION_ACTIVE_STATUSES.has(generationRun.status)) {
      return;
    }

    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const latest = await getApiAutomationGenerationRun(projectId, generationRun.id);
        if (!cancelled) {
          applyGenerationRun(latest);
        }
      } catch (error) {
        if (!cancelled) {
          toast.error(error instanceof Error ? error.message : "生成任务状态刷新失败");
        }
      }
    }, 3000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [applyGenerationRun, projectId, generationRun]);

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
    try {
      defaultHeaders = parseJsonObject(environmentForm.defaultHeaders, "默认请求头");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "环境配置格式不正确");
      return;
    }
    if (
      environmentForm.authType === "account_password" &&
      (!environmentForm.username.trim() || (!environmentForm.password.trim() && !editingEnvironment))
    ) {
      toast.error("账号密码鉴权必须填写用户名和密码");
      return;
    }
    if (
      environmentForm.authType === "cybertron_agent" &&
      (!environmentForm.cybertronUsername.trim() ||
        (!environmentForm.cybertronRobotKey.trim() && !editingEnvironment?.auth_config.cybertron_robot_key_saved) ||
        (!environmentForm.cybertronRobotToken.trim() && !editingEnvironment?.auth_config.cybertron_robot_token_saved))
    ) {
      toast.error("塞伯坦智能体必须填写 robot key、robot token 和 username");
      return;
    }

    setBusy(true);
    try {
      const authConfig =
        environmentForm.authType === "cybertron_agent"
          ? {
              cybertron_robot_key: environmentForm.cybertronRobotKey,
              cybertron_robot_token: environmentForm.cybertronRobotToken,
              username: environmentForm.cybertronUsername,
            }
          : {};
      const payload = {
        name,
        api_base_url: apiBaseUrl,
        username: environmentForm.authType === "account_password" ? environmentForm.username : "",
        password: environmentForm.authType === "account_password" ? environmentForm.password : "",
        auth_type: environmentForm.authType,
        auth_config: authConfig,
        default_headers: defaultHeaders,
        timeout_seconds: timeoutSeconds,
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
    if (selectedEndpointAssetIds.length === 0) {
      toast.error("请先选择接口");
      return;
    }
    setBusy(true);
    setGenerateBusy(true);
    try {
      const created = await generateApiAutomationTestCases(projectId, {
        endpoint_ids: selectedEndpointAssetIds,
        api_environment_id: selectedEnvironment?.id ?? null,
        generation_goal: "直接生成所选接口的自动化测试用例",
        include_security_cases: false,
        generate_code: false,
      });
      applyGenerationRun(created);
      setActiveTab("接口用例");
      setActiveApiCaseEndpointId(created.endpoint_ids[0] ?? selectedEndpointAssetIds[0] ?? activeApiCaseEndpointId);
      setActiveEndpointId(created.endpoint_ids[0] ?? selectedEndpointAssetIds[0] ?? activeEndpointId);
      toast.success("接口用例生成任务已创建");
      notifyAiTaskStarted();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "生成失败");
    } finally {
      setGenerateBusy(false);
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
      notifyAiTaskStarted();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "执行失败");
    } finally {
      setBusy(false);
    }
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

  function toggleApiCaseEndpoint(endpointId: string, checked: boolean) {
    setSelectedApiCaseEndpointIds((current) =>
      checked ? [...new Set([...current, endpointId])] : current.filter((id) => id !== endpointId),
    );
  }

  function toggleVisibleApiCaseEndpoints(checked: boolean) {
    setSelectedApiCaseEndpointIds((current) => {
      if (!checked) {
        return current.filter((id) => !visibleApiCaseEndpointIds.includes(id));
      }
      return [...new Set([...current, ...visibleApiCaseEndpointIds])];
    });
  }

  function toggleApiCase(testCaseId: string, checked: boolean) {
    setSelectedApiCaseIds((current) =>
      checked ? [...new Set([...current, testCaseId])] : current.filter((id) => id !== testCaseId),
    );
  }

  function toggleAllApiCases(checked: boolean) {
    const visibleIds = filteredApiTestCases.map((testCase) => testCase.id);
    setSelectedApiCaseIds((current) => {
      if (!checked) {
        return current.filter((id) => !visibleIds.includes(id));
      }
      return [...new Set([...current, ...visibleIds])];
    });
  }

  async function deleteApiCaseEndpoints(endpointIds: string[]) {
    const ids = [...new Set(endpointIds)];
    if (ids.length === 0) {
      return;
    }
    const caseIds = apiTestCases
      .filter((testCase) => ids.includes(testCase.endpoint_id ?? ""))
      .map((testCase) => testCase.id);
    await deleteApiTestCases(caseIds);
    setSelectedApiCaseEndpointIds((current) => current.filter((id) => !ids.includes(id)));
  }

  async function deleteApiTestCases(caseIds: string[]) {
    const ids = [...new Set(caseIds)];
    if (ids.length === 0) {
      return;
    }
    setBusy(true);
    try {
      await Promise.all(ids.map((caseId) => deleteApiAutomationTestCase(projectId, caseId)));
      setApiTestCases((current) => current.filter((testCase) => !ids.includes(testCase.id)));
      setSelectedApiCaseIds((current) => current.filter((id) => !ids.includes(id)));
      toast.success(`已删除 ${ids.length} 个接口用例`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "接口用例删除失败");
    } finally {
      setBusy(false);
    }
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
    let body: unknown = null;
    try {
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
        ...(selectedCaseSet ? [{ label: selectedCaseSet.name }] : []),
      ]}
      description="导入 OpenAPI、生成接口自动化用例、生成 pytest 脚本并执行。"
      fillViewport={activeTab === "接口用例"}
      onTabChange={setActiveTab}
      projectScope="project"
      tabActions={
        activeTab === "接口资产" ? (
          <div className="flex items-center gap-2">
            <div className="relative w-64 max-w-full">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                aria-label="搜索 method、path、tag"
                className="h-8 bg-background pl-9"
                onChange={(event) => setSearchText(event.target.value)}
                placeholder="搜索"
                value={searchText}
              />
            </div>
            <Button disabled={busy} onClick={() => openImportDialog("file")}>
              <ImportIcon className="size-4" />
              导入
            </Button>
            <Button disabled={busy} onClick={() => refresh()} size="sm" variant="outline">
              {busy ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
              刷新
            </Button>
          </div>
        ) : null
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
                <div className="ml-auto flex items-center gap-2">
                  <Button
                    className="border-red-200 bg-red-50 text-red-700 hover:border-red-300 hover:bg-red-100 hover:text-red-800"
                    disabled={busy || selectedEndpointAssetIds.length === 0}
                    onClick={() => deleteEndpoints(selectedEndpointAssetIds)}
                    size="sm"
                    variant="outline"
                  >
                    <Trash2 className="size-4" />
                    删除{selectedEndpointAssetIds.length > 0 ? ` (${selectedEndpointAssetIds.length})` : ""}
                  </Button>
                  <Button disabled={busy || selectedEndpointAssetIds.length === 0} onClick={handleGenerate} size="sm">
                    {generateBusy ? <Loader2 className="size-4 animate-spin" /> : <WandSparkles className="size-4" />}
                    生成用例
                  </Button>
                </div>
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
                        "mb-1 flex w-full items-center gap-2 rounded-md border border-transparent bg-slate-100/70 px-2 py-1.5 text-left font-medium text-muted-foreground text-xs transition-colors hover:border-slate-200 hover:bg-slate-100 dark:bg-muted/25 dark:hover:border-border dark:hover:bg-muted/45",
                        hasActiveEndpoint &&
                          "border-sky-200 bg-sky-50/80 text-sky-800 dark:border-sky-500/35 dark:bg-sky-500/15 dark:text-sky-200",
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
                      <span className="rounded-full bg-sky-100 px-2 py-0.5 font-semibold text-sky-700 tabular-nums dark:bg-sky-500/20 dark:text-sky-200">
                        {rows.length}
                      </span>
                    </button>
                    {isCollapsed ? null : (
                      <div className="space-y-1">
                        {rows.map((endpoint) => (
                          <div
                            className={cn(
                              "flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-background dark:hover:bg-muted/30",
                              activeEndpoint?.id === endpoint.id &&
                                "bg-background shadow-xs ring-1 ring-border dark:bg-muted/35 dark:shadow-none",
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
                            <Badge
                              className="bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200"
                              key={tag}
                              variant="secondary"
                            >
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
                  <TableHead className="text-left">鉴权方式</TableHead>
                  <TableHead>超时</TableHead>
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
                    <TableCell className="text-left">
                      <EnvironmentAuthBadge authType={environment.auth_type} />
                    </TableCell>
                    <TableCell>{environment.timeout_seconds} 秒</TableCell>
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
                  <TableLoadingRow colSpan={7} label="环境列表加载中" />
                ) : null}
                {!busy && filteredEnvironments.length === 0 ? (
                  <TableRow>
                    <TableCell className="h-24 text-center text-muted-foreground" colSpan={7}>
                      暂无接口环境。新增环境后，可用于生成用例、生成脚本和执行接口自动化。
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>
        </ShellSection>
      )}

      {activeTab === "接口用例" && (
        <div className="grid min-h-[28rem] flex-1 overflow-hidden rounded-xl border bg-background xl:grid-cols-[360px_1fr]">
          <aside className="no-scrollbar flex min-h-0 flex-col overflow-y-auto overflow-x-hidden border-r bg-muted/20">
            <div className="border-b p-3">
              <div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    aria-label="选择当前接口列表"
                    checked={
                      visibleApiCaseEndpointIds.length > 0 &&
                      visibleApiCaseEndpointIds.every((id) => selectedApiCaseEndpointIds.includes(id))
                        ? true
                        : selectedVisibleApiCaseEndpointIds.length > 0
                          ? "indeterminate"
                          : false
                    }
                    disabled={busy || visibleApiCaseEndpointIds.length === 0}
                    onCheckedChange={(checked) => toggleVisibleApiCaseEndpoints(Boolean(checked))}
                  />
                  <div className="ml-auto flex items-center gap-2">
                    <Button
                      className="border-red-200 bg-red-50 text-red-700 hover:border-red-300 hover:bg-red-100 hover:text-red-800"
                      disabled={busy || selectedApiCaseEndpointIds.length === 0}
                      onClick={() => deleteApiCaseEndpoints(selectedApiCaseEndpointIds)}
                      size="sm"
                      variant="outline"
                    >
                      <Trash2 className="size-4" />
                      删除{selectedApiCaseEndpointIds.length > 0 ? ` (${selectedApiCaseEndpointIds.length})` : ""}
                    </Button>
                    <Button
                      disabled={busy || selectedApiCaseEndpointIds.length === 0}
                      onClick={() => setActiveTab("测试脚本")}
                      size="sm"
                    >
                      生成脚本
                    </Button>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex min-h-0 flex-1 flex-col p-2">
              {Object.entries(groupedApiCaseEndpoints).map(([group, rows]) => {
                const hasActiveEndpoint = rows.some((endpoint) => endpoint.id === activeApiCaseEndpoint?.id);
                const isCollapsed = !expandedApiCaseEndpointGroups.includes(group);
                const caseCount = rows.reduce(
                  (count, endpoint) => count + (apiCaseCountByEndpointId[endpoint.id] ?? 0),
                  0,
                );

                return (
                  <div className="mb-3" key={group}>
                    <button
                      aria-expanded={!isCollapsed}
                      aria-label={`${group} 分组，${caseCount} 条用例，${isCollapsed ? "展开" : "折叠"}`}
                      className={cn(
                        "mb-1 flex w-full items-center gap-2 rounded-md border border-transparent bg-slate-100/70 px-2 py-1.5 text-left font-medium text-muted-foreground text-xs transition-colors hover:border-slate-200 hover:bg-slate-100 dark:bg-muted/25 dark:hover:border-border dark:hover:bg-muted/45",
                        hasActiveEndpoint &&
                          "border-sky-200 bg-sky-50/80 text-sky-800 dark:border-sky-500/35 dark:bg-sky-500/15 dark:text-sky-200",
                      )}
                      onClick={() => toggleApiCaseEndpointGroup(group)}
                      type="button"
                    >
                      {isCollapsed ? (
                        <ChevronRight className="size-3.5 shrink-0" />
                      ) : (
                        <ChevronDown className="size-3.5 shrink-0" />
                      )}
                      <span className="min-w-0 flex-1 truncate">{group}</span>
                      <span className="rounded-full bg-sky-100 px-2 py-0.5 font-semibold text-sky-700 tabular-nums dark:bg-sky-500/20 dark:text-sky-200">
                        {caseCount}
                      </span>
                    </button>
                    {isCollapsed ? null : (
                      <div className="space-y-1">
                        {rows.map((endpoint) => (
                          <div
                            className={cn(
                              "flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-background dark:hover:bg-muted/30",
                              activeApiCaseEndpoint?.id === endpoint.id &&
                                "bg-background shadow-xs ring-1 ring-border dark:bg-muted/35 dark:shadow-none",
                            )}
                            key={endpoint.id}
                          >
                            <Checkbox
                              aria-label={`选择 ${endpoint.summary || endpoint.path}`}
                              checked={selectedApiCaseEndpointIds.includes(endpoint.id)}
                              disabled={busy}
                              onCheckedChange={(checked) => toggleApiCaseEndpoint(endpoint.id, Boolean(checked))}
                            />
                            <button
                              className="flex min-w-0 flex-1 items-center gap-2 text-left"
                              onClick={() => {
                                setActiveApiCaseEndpointId(endpoint.id);
                                setSelectedApiCaseIds([]);
                              }}
                              title={endpoint.path}
                              type="button"
                            >
                              <MethodBadge method={endpoint.method} />
                              <span className="min-w-0 flex-1 truncate text-xs">
                                {endpoint.summary || endpoint.path}
                              </span>
                            </button>
                            <span className="rounded-full bg-muted px-2 py-0.5 font-semibold text-muted-foreground text-xs tabular-nums">
                              {apiCaseCountByEndpointId[endpoint.id] ?? 0}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
              {apiCaseEndpoints.length === 0 ? (
                <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-6 py-6 text-center">
                  <Image
                    alt=""
                    aria-hidden="true"
                    className="h-32 w-44 object-contain"
                    height={180}
                    src="/illustrations/api-cases-empty-left.svg"
                    width={240}
                  />
                  <div className="mt-4">
                    <div className="font-medium text-foreground text-sm">暂无接口用例</div>
                    <div className="mt-2 text-muted-foreground text-sm">请先在接口资产页签选择接口并生成用例。</div>
                  </div>
                  <Button className="mt-5" onClick={() => setActiveTab("接口资产")} size="sm">
                    去选择接口
                  </Button>
                </div>
              ) : null}
            </div>
          </aside>

          <ShellSection className="flex min-h-0 min-w-0 flex-col rounded-none border-0">
            <ListToolbar
              actions={
                <Button disabled={busy} onClick={() => refresh()} variant="outline">
                  {busy ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
                  刷新
                </Button>
              }
              description={
                activeApiCaseEndpoint
                  ? `${activeApiCaseEndpoint.summary || activeApiCaseEndpoint.path} · ${activeApiCaseEndpoint.path}`
                  : ""
              }
              onBatchDelete={() => deleteApiTestCases(selectedApiCaseIds)}
              onSearch={setApiCaseSearchText}
              placeholder="搜索用例名称"
              selectedCount={selectedApiCaseIds.length}
              title="接口用例列表"
            />
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <Checkbox
                        aria-label="选择全部接口用例"
                        checked={allApiCasesSelected || (partiallyApiCasesSelected ? "indeterminate" : false)}
                        disabled={busy || filteredApiTestCases.length === 0}
                        onCheckedChange={(checked) => toggleAllApiCases(Boolean(checked))}
                      />
                    </TableHead>
                    <TableHead>用例名称</TableHead>
                    <TableHead>优先级</TableHead>
                    <TableHead>更新时间</TableHead>
                    <TableHead className="w-16">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredApiTestCases.map((item) => (
                    <TableRow data-state={selectedApiCaseIds.includes(item.id) ? "selected" : undefined} key={item.id}>
                      <TableCell>
                        <Checkbox
                          aria-label={`选择 ${item.title}`}
                          checked={selectedApiCaseIds.includes(item.id)}
                          onCheckedChange={(checked) => toggleApiCase(item.id, Boolean(checked))}
                        />
                      </TableCell>
                      <TableCell className="max-w-80 font-medium">
                        <button
                          className="block max-w-full truncate text-left hover:underline"
                          onClick={() => router.push(apiCaseDetailHref(projectId, item.id))}
                          title={item.title}
                          type="button"
                        >
                          {item.title}
                        </button>
                      </TableCell>
                      <TableCell>
                        <Badge className={cn("border", apiCasePriorityTone(item.priority))} variant="outline">
                          {item.priority || "P2"}
                        </Badge>
                      </TableCell>
                      <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                      <TableCell>
                        <RowActions
                          actions={[
                            {
                              label: "查看详情",
                              icon: Eye,
                              onSelect: () => router.push(apiCaseDetailHref(projectId, item.id)),
                            },
                            {
                              label: "删除",
                              icon: Trash2,
                              destructive: true,
                              onSelect: () => deleteApiTestCases([item.id]),
                            },
                          ]}
                          label={`打开 ${item.title} 操作菜单`}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {filteredApiTestCases.length === 0 ? (
                <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 px-6 py-6 text-center text-sm">
                  <Image
                    alt=""
                    aria-hidden="true"
                    className="h-36 w-48 object-contain"
                    height={180}
                    src="/illustrations/api-cases-empty-right.svg"
                    width={240}
                  />
                  <div>
                    <div className="font-medium text-foreground text-sm">暂无接口用例</div>
                    <div className="mt-1 text-muted-foreground">请在左侧选择接口进行展示测试用例。</div>
                  </div>
                </div>
              ) : null}
            </div>
          </ShellSection>
        </div>
      )}

      {activeTab === "测试脚本" && (
        <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">脚本生成</CardTitle>
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
              <Button disabled variant="outline">
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
              <AnimatedSelect
                id="api-environment-auth-type"
                placeholder="选择鉴权方式"
                setValue={(value) =>
                  setEnvironmentForm((current) => ({ ...current, authType: value as EnvironmentForm["authType"] }))
                }
                value={environmentForm.authType}
              >
                {authTypeOptions.map((option) => (
                  <SelectOption key={option.value} value={option.value}>
                    {option.label}
                  </SelectOption>
                ))}
              </AnimatedSelect>
            </div>
            <FieldText
              label="超时时间（秒）"
              onChange={(value) => setEnvironmentForm((current) => ({ ...current, timeoutSeconds: value }))}
              placeholder="30"
              value={environmentForm.timeoutSeconds}
            />
            {environmentForm.authType === "account_password" ? (
              <>
                <FieldText
                  label="用户名"
                  onChange={(value) => setEnvironmentForm((current) => ({ ...current, username: value }))}
                  placeholder="请输入账号"
                  value={environmentForm.username}
                />
                <FieldText
                  label="密码"
                  onChange={(value) => setEnvironmentForm((current) => ({ ...current, password: value }))}
                  placeholder={editingEnvironment ? "不填写则保留原密码" : "请输入密码"}
                  type="password"
                  value={environmentForm.password}
                />
              </>
            ) : null}
            {environmentForm.authType === "cybertron_agent" ? (
              <div className="grid gap-4 md:col-span-2">
                <FieldText
                  label="cybertron-robot-key"
                  mono
                  onChange={(value) => setEnvironmentForm((current) => ({ ...current, cybertronRobotKey: value }))}
                  placeholder={
                    editingEnvironment?.auth_config.cybertron_robot_key_saved
                      ? "已保存，不填写则保留"
                      : "请输入 robot key"
                  }
                  type="password"
                  value={environmentForm.cybertronRobotKey}
                />
                <FieldText
                  label="cybertron-robot-token"
                  mono
                  onChange={(value) => setEnvironmentForm((current) => ({ ...current, cybertronRobotToken: value }))}
                  placeholder={
                    editingEnvironment?.auth_config.cybertron_robot_token_saved
                      ? "已保存，不填写则保留"
                      : "请输入 robot token"
                  }
                  type="password"
                  value={environmentForm.cybertronRobotToken}
                />
                <FieldText
                  label="username"
                  mono
                  onChange={(value) => setEnvironmentForm((current) => ({ ...current, cybertronUsername: value }))}
                  placeholder="请输入 username"
                  value={environmentForm.cybertronUsername}
                />
              </div>
            ) : null}
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
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden p-0 sm:max-w-5xl">
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
                  <SelectTrigger className="w-full lg:w-56">
                    <SelectValue placeholder="选择接口环境" />
                  </SelectTrigger>
                  <SelectContent position="popper">
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
              {activeEndpoint && getParameterRows(activeEndpoint.parameters, "path").length > 0 ? (
                <DebugMapSection
                  fields={debugForm.pathParams}
                  onChange={(key, value) => updateDebugMapField("pathParams", key, value)}
                  rows={getParameterRows(activeEndpoint.parameters, "path")}
                  title="路径参数"
                />
              ) : null}
              {activeEndpoint && getParameterRows(activeEndpoint.parameters, "query").length > 0 ? (
                <DebugMapSection
                  className="lg:col-span-2"
                  fields={debugForm.queryParams}
                  onChange={(key, value) => updateDebugMapField("queryParams", key, value)}
                  rows={getParameterRows(activeEndpoint.parameters, "query")}
                  title="Query 参数"
                />
              ) : null}
              <DebugHeaderSection
                className="lg:col-span-2"
                rows={activeEndpoint ? getParameterRows(activeEndpoint.parameters, "header") : []}
              />
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
                  className="max-h-64 min-h-0 overflow-y-auto font-mono text-xs"
                  onChange={(event) => setDebugForm((current) => ({ ...current, bodyText: event.target.value }))}
                  placeholder='{"key":"value"}'
                  rows={getTextareaRows(debugForm.bodyText, 3, 12)}
                  value={debugForm.bodyText}
                />
              </div>
            ) : null}

            {debugResult ? (
              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50/60 p-4 shadow-sm">
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
                  <DebugResultBlock
                    title="请求信息"
                    value={formatPythonRequestsSnippet(debugResult.request)}
                    variant="PY"
                  />
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

function apiCaseDetailHref(projectId: string, caseId: string) {
  return `/projects/${projectId}/automation/api/cases/${caseId}`;
}

function apiCasePriorityTone(priority: string) {
  const normalized = priority.trim().toUpperCase();
  if (normalized === "P0") return "border-red-200 bg-red-50 text-red-700";
  if (normalized === "P1") return "border-amber-200 bg-amber-50 text-amber-700";
  if (normalized === "P2") return "border-blue-200 bg-blue-50 text-blue-700";
  return "border-slate-200 bg-slate-50 text-slate-700";
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
  className,
  title,
  rows,
  fields,
  onChange,
}: {
  className?: string;
  title: string;
  rows: ApiFieldRow[];
  fields: Record<string, string>;
  onChange: (key: string, value: string) => void;
}) {
  return (
    <div className={cn("space-y-2", className)}>
      <div className="font-medium text-sm">{title}</div>
      <div className="space-y-2 rounded-md border bg-muted/20 px-3 py-3">
        {rows.map((row) => (
          <div className="grid gap-2 sm:grid-cols-[minmax(140px,0.9fr)_1fr]" key={`${row.location}-${row.name}`}>
            <div className="flex min-w-0 items-center gap-2">
              <span className="min-w-0 truncate font-mono text-sm" title={row.name}>
                {row.name}
              </span>
              {row.required ? (
                <Badge className="bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-200" variant="secondary">
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
    </div>
  );
}

function DebugHeaderSection({ className, rows }: { className?: string; rows: ApiFieldRow[] }) {
  return (
    <div className={cn("space-y-2", className)}>
      <div className="font-medium text-sm">Header 参数</div>
      <div className="space-y-2 rounded-md border bg-muted/20 px-3 py-3">
        {rows.length > 0 ? (
          <div className="space-y-2">
            {rows.map((row) => (
              <div className="grid gap-2 sm:grid-cols-[minmax(140px,0.9fr)_1fr]" key={`${row.location}-${row.name}`}>
                <div className="flex min-w-0 items-center gap-2">
                  <span className="min-w-0 truncate font-mono text-sm" title={row.name}>
                    {row.name}
                  </span>
                  {row.required ? (
                    <Badge
                      className="bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-200"
                      variant="secondary"
                    >
                      必填
                    </Badge>
                  ) : null}
                </div>
                <Input className="font-mono text-muted-foreground text-xs" disabled value="已由环境填充" />
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function DebugResultBlock({ title, value, variant = "JSON" }: { title: string; value: string; variant?: string }) {
  const preClassName =
    "overflow-visible whitespace-pre-wrap break-words bg-white p-3 font-mono text-[12px] text-slate-800 leading-5 selection:bg-sky-100";

  return (
    <section className="min-w-0 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-slate-200 border-b bg-slate-50 px-3 py-2">
        <div className="font-medium text-slate-700 text-sm">{title}</div>
        <span className="rounded border border-slate-200 bg-white px-1.5 py-0.5 font-mono text-[10px] text-slate-500 uppercase">
          {variant}
        </span>
      </div>
      <pre className={preClassName}>{value}</pre>
    </section>
  );
}

function formatPythonRequestsSnippet(request: Record<string, unknown>) {
  const method = String(request.method ?? "GET").toLowerCase();
  const url = String(request.url ?? "");
  const queryParams = plainObject(request.query_params);
  const headers = plainObject(request.headers);
  const body = request.body;
  const hasParams = Object.keys(queryParams).length > 0;
  const hasHeaders = Object.keys(headers).length > 0;
  const hasBody = body !== null && body !== undefined && body !== "";
  const requestArgs: string[] = ["url"];

  const lines = ["import requests", "", `url = ${pythonLiteral(url)}`];

  if (hasParams) {
    lines.push("", `params = ${pythonLiteral(queryParams)}`);
    requestArgs.push("params=params");
  }

  if (hasHeaders) {
    lines.push("", `headers = ${pythonLiteral(headers)}`);
    requestArgs.push("headers=headers");
  }

  if (hasBody) {
    lines.push("", `payload = ${pythonLiteral(body)}`);
    requestArgs.push(isJsonLikeBody(body) ? "json=payload" : "data=payload");
  }

  const requestCall = isRequestsShortcutMethod(method)
    ? `requests.${method}(${requestArgs.join(", ")})`
    : `requests.request(${pythonLiteral(method.toUpperCase())}, ${requestArgs.join(", ")})`;

  lines.push("", `response = ${requestCall}`, "", "print(response.text)");
  return lines.join("\n");
}

function plainObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function isJsonLikeBody(value: unknown) {
  return Boolean(value) && typeof value === "object";
}

function isRequestsShortcutMethod(method: string) {
  return ["get", "post", "put", "patch", "delete", "head", "options"].includes(method);
}

function pythonLiteral(value: unknown): string {
  if (value === null || value === undefined) {
    return "None";
  }
  if (typeof value === "boolean") {
    return value ? "True" : "False";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : "None";
  }
  if (typeof value === "string") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return "[]";
    }
    return `[\n${value.map((item) => indentPythonLiteral(pythonLiteral(item))).join(",\n")}\n]`;
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) {
      return "{}";
    }
    return `{\n${entries
      .map(([key, item]) => `    ${JSON.stringify(key)}: ${indentContinuation(pythonLiteral(item))}`)
      .join(",\n")}\n}`;
  }
  return JSON.stringify(String(value));
}

function indentPythonLiteral(value: string) {
  return value
    .split("\n")
    .map((line) => `    ${line}`)
    .join("\n");
}

function indentContinuation(value: string) {
  return value.includes("\n") ? value.replace(/\n/g, "\n    ") : value;
}

function getTextareaRows(value: string, minRows: number, maxRows: number) {
  const lineCount = Math.max(1, value.split("\n").length);
  return Math.min(maxRows, Math.max(minRows, lineCount));
}

function authTypeLabel(value: string) {
  return authTypeOptions.find((option) => option.value === value)?.label ?? value;
}

function EnvironmentAuthBadge({ authType }: { authType: string }) {
  const className =
    {
      none: "border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300",
      account_password:
        "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300",
      cybertron_agent: "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900 dark:bg-sky-950/50 dark:text-sky-300",
    }[authType] ?? "border-border bg-background text-muted-foreground";

  return (
    <Badge className={cn("justify-start rounded-md border px-2.5 font-medium", className)} variant="outline">
      {authTypeLabel(authType)}
    </Badge>
  );
}

function formFromEndpoint(endpoint: ApiAutomationEndpoint, environmentId: string): EndpointDebugForm {
  const requestSchema = getRequestBodySchema(endpoint.request_body);
  const bodyExample =
    Object.keys(requestSchema).length > 0 ? JSON.stringify(exampleFromSchema(requestSchema), null, 2) : "";
  return {
    environmentId,
    pathParams: rowsToEmptyValues(getParameterRows(endpoint.parameters, "path")),
    queryParams: rowsToEmptyValues(getParameterRows(endpoint.parameters, "query")),
    headers: {},
    bodyText: bodyExample,
  };
}

function formFromEnvironment(environment: ApiAutomationEnvironment): EnvironmentForm {
  const authConfig = environment.auth_config ?? {};
  return {
    name: environment.name,
    apiBaseUrl: environment.api_base_url,
    authType: (authTypeOptions.some((option) => option.value === environment.auth_type)
      ? environment.auth_type
      : "none") as EnvironmentForm["authType"],
    username: environment.username,
    password: "",
    cybertronRobotKey: "",
    cybertronRobotToken: "",
    cybertronUsername: asString(authConfig.username),
    defaultHeaders: JSON.stringify(environment.default_headers ?? {}, null, 2),
    timeoutSeconds: String(environment.timeout_seconds),
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
      GET: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/35 dark:bg-emerald-500/15 dark:text-emerald-200",
      POST: "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-500/35 dark:bg-sky-500/15 dark:text-sky-200",
      PUT: "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/35 dark:bg-amber-500/15 dark:text-amber-200",
      PATCH:
        "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-500/35 dark:bg-violet-500/15 dark:text-violet-200",
      DELETE: "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/35 dark:bg-rose-500/15 dark:text-rose-200",
    }[upper] ??
    "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-500/35 dark:bg-slate-500/15 dark:text-slate-200";

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
        className="min-w-0 truncate font-mono font-semibold text-emerald-600 text-sm dark:text-emerald-300"
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
        <Badge className="w-fit bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-200" variant="secondary">
          必填
        </Badge>
      ) : (
        <span className="hidden md:block" />
      )}
      <div className="min-w-0 space-y-1">
        <p className="min-w-0 text-muted-foreground text-sm">{row.description || "暂无说明"}</p>
        {row.constraints.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {row.constraints.map((constraint) => (
              <Badge className="w-fit font-normal" key={constraint} variant="outline">
                {constraint}
              </Badge>
            ))}
          </div>
        ) : null}
      </div>
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
        constraints: getSchemaConstraints(schema),
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
        constraints: getSchemaConstraints(schema),
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
      constraints: getSchemaConstraints(propertySchema),
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

function getSchemaConstraints(schema: Record<string, unknown>): string[] {
  const constraints: string[] = [];
  const type = getSchemaType(schema);
  const minLength = asDisplayValue(schema.minLength);
  const maxLength = asDisplayValue(schema.maxLength);
  const pattern = asString(schema.pattern);
  const minimum = asDisplayValue(schema.minimum);
  const maximum = asDisplayValue(schema.maximum);
  const exclusiveMinimum = asDisplayValue(schema.exclusiveMinimum);
  const exclusiveMaximum = asDisplayValue(schema.exclusiveMaximum);
  const minItems = asDisplayValue(schema.minItems);
  const maxItems = asDisplayValue(schema.maxItems);
  const minProperties = asDisplayValue(schema.minProperties);
  const maxProperties = asDisplayValue(schema.maxProperties);
  const multipleOf = asDisplayValue(schema.multipleOf);
  const defaultValue = asDisplayValue(schema.default);
  const enumValues = Array.isArray(schema.enum) ? schema.enum.map(asDisplayValue).filter(Boolean) : [];

  if (minLength) {
    constraints.push(`Minimum string length: ${minLength}`);
  }
  if (maxLength) {
    constraints.push(`Maximum string length: ${maxLength}`);
  }
  if (pattern) {
    constraints.push(`Pattern: ${pattern}`);
  }
  if (minimum) {
    constraints.push(`Minimum: ${minimum}`);
  }
  if (maximum) {
    constraints.push(`Maximum: ${maximum}`);
  }
  if (exclusiveMinimum) {
    constraints.push(`Exclusive minimum: ${exclusiveMinimum}`);
  }
  if (exclusiveMaximum) {
    constraints.push(`Exclusive maximum: ${exclusiveMaximum}`);
  }
  if (minItems) {
    constraints.push(`Minimum items: ${minItems}`);
  }
  if (maxItems) {
    constraints.push(`Maximum items: ${maxItems}`);
  }
  if (minProperties) {
    constraints.push(`Minimum properties: ${minProperties}`);
  }
  if (maxProperties) {
    constraints.push(`Maximum properties: ${maxProperties}`);
  }
  if (multipleOf) {
    constraints.push(`Multiple of: ${multipleOf}`);
  }
  if (enumValues.length > 0) {
    constraints.push(`Allowed values: ${enumValues.join(", ")}`);
  }
  if (defaultValue) {
    constraints.push(`Default: ${defaultValue}`);
  }

  if (type.endsWith("[]")) {
    const itemConstraints = getSchemaConstraints(asRecord(schema.items));
    constraints.push(
      ...itemConstraints.map((constraint) => `Item ${constraint.charAt(0).toLowerCase()}${constraint.slice(1)}`),
    );
  }

  return constraints;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function asDisplayValue(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}
