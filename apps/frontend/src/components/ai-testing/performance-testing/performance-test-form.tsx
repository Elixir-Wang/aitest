"use client";

import { useEffect, useRef, useState } from "react";

import { useRouter } from "next/navigation";

import {
  AlertTriangle,
  ArrowLeft,
  Check,
  CircleHelp,
  FileText,
  Gauge,
  LoaderCircle,
  Settings,
  Sparkles,
} from "lucide-react";

import { ShellSection } from "@/components/ai-testing/page-shell";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  type ApiAutomationEndpoint,
  type ApiAutomationEnvironment,
  type ApiAutomationScenario,
  type ApiProject,
  ApiRequestError,
  apiRequest,
  createPerformanceTest,
  generatePerformanceScript,
  getPerformanceTest,
  listApiAutomationEndpoints,
  listApiAutomationEnvironments,
  listApiAutomationScenarios,
  type PerformanceCircuitBreaker,
  type PerformanceDataConfig,
  type PerformanceLoadConfig,
  type PerformanceLoadStage,
  type PerformanceRequestPreview,
  type PerformanceSseConfig,
  type PerformanceSseMetricGoal,
  previewPerformanceRequest,
  updatePerformanceTest,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";

import { LoadStageEditor } from "./load-stage-editor";
import { PerformanceDataEditor } from "./performance-data-editor";
import { PerformanceSseMetricsConfig } from "./performance-sse-metrics-config";

type NumericDraft = {
  users: string;
  spawnRate: string;
  duration: string;
  waitMin: string;
  waitMax: string;
  timeout: string;
  stressStartUsers: string;
  stressMaxUsers: string;
  stressStepUsers: string;
  stressHoldSeconds: string;
  maxFailPercent: string;
  maxAverageMs: string;
};

const initialNumbers: NumericDraft = {
  users: "10",
  spawnRate: "1",
  duration: "60",
  waitMin: "1",
  waitMax: "3",
  timeout: "30",
  stressStartUsers: "10",
  stressMaxUsers: "100",
  stressStepUsers: "10",
  stressHoldSeconds: "180",
  maxFailPercent: "0",
  maxAverageMs: "3000",
};

function LoadConfigFieldLabel({
  htmlFor,
  label,
  description,
}: {
  htmlFor: string;
  label: string;
  description: string;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <FieldLabel htmlFor={htmlFor}>{label}</FieldLabel>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            aria-label={`${label}说明`}
            className="inline-flex size-4 items-center justify-center rounded-full text-muted-foreground hover:text-foreground"
            type="button"
          >
            <CircleHelp className="size-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-80 leading-relaxed" side="top">
          {description}
        </TooltipContent>
      </Tooltip>
    </div>
  );
}

const initialDataConfig: PerformanceDataConfig = {
  source: "fixed",
  selection_strategy: "sequential_loop",
  json_rows: [],
  csv_file_name: "",
  csv_file_path: "",
};

const initialCircuitBreaker: PerformanceCircuitBreaker = {
  enabled: false,
  window_seconds: 10,
  max_fail_ratio: 0.5,
  consecutive_windows: 3,
};

type PerformanceTestFormProps = {
  editTestId?: string;
  projectIdForEdit?: string;
};

export function PerformanceTestForm({ editTestId, projectIdForEdit }: PerformanceTestFormProps) {
  const router = useRouter();
  const previewSequence = useRef(0);
  const preserveEditedRequest = useRef(Boolean(editTestId));
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [endpoints, setEndpoints] = useState<ApiAutomationEndpoint[]>([]);
  const [scenarios, setScenarios] = useState<ApiAutomationScenario[]>([]);
  const [environments, setEnvironments] = useState<ApiAutomationEnvironment[]>([]);
  const [targetType, setTargetType] = useState<"endpoint" | "scenario">("endpoint");
  const [endpointId, setEndpointId] = useState("");
  const [scenarioId, setScenarioId] = useState("");
  const [scenarioSseStepId, setScenarioSseStepId] = useState("");
  const [environmentId, setEnvironmentId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [pathJson, setPathJson] = useState("{}");
  const [queryJson, setQueryJson] = useState("{}");
  const [headersJson, setHeadersJson] = useState("{}");
  const [bodyJson, setBodyJson] = useState("null");
  const [transport, setTransport] = useState<"http" | "sse">("http");
  const [sseMaxStreamSeconds, setSseMaxStreamSeconds] = useState("60");
  const [sseConfig, setSseConfig] = useState<PerformanceSseConfig | null>(null);
  const [sseGoalTargets, setSseGoalTargets] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<PerformanceLoadConfig["mode"]>("fixed");
  const [stages, setStages] = useState<PerformanceLoadStage[]>([]);
  const [dataConfig, setDataConfig] = useState<PerformanceDataConfig>(initialDataConfig);
  const [circuitBreaker, setCircuitBreaker] = useState<PerformanceCircuitBreaker>(initialCircuitBreaker);
  const [numbers, setNumbers] = useState<NumericDraft>(initialNumbers);
  const [preview, setPreview] = useState<PerformanceRequestPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [requestTouched, setRequestTouched] = useState(false);
  const [editLoaded, setEditLoaded] = useState(!editTestId);

  useEffect(() => {
    if (projectIdForEdit) setSelectedProjectId(projectIdForEdit);
  }, [projectIdForEdit]);

  useEffect(() => {
    apiRequest<ApiProject[]>("/projects")
      .then((rows) => {
        const active = rows.filter((project) => project.status === "active");
        setProjects(active);
      })
      .catch((error) => toast.error(apiErrorMessage(error, "项目加载失败")));
  }, []);

  useEffect(() => {
    setEndpoints([]);
    setScenarios([]);
    setEnvironments([]);
    setEndpointId("");
    setScenarioId("");
    setScenarioSseStepId("");
    setEnvironmentId("");
    setPreview(null);
    setRequestTouched(false);
    setPathJson("{}");
    setQueryJson("{}");
    setHeadersJson("{}");
    setBodyJson("null");
    setSseConfig(null);
    setSseGoalTargets({});
    setDataConfig(initialDataConfig);
    if (!selectedProjectId) return;
    let ignore = false;
    Promise.all([
      listApiAutomationEndpoints(selectedProjectId),
      listApiAutomationScenarios(selectedProjectId),
      listApiAutomationEnvironments(selectedProjectId),
    ])
      .then(([endpointRows, scenarioRows, environmentRows]) => {
        if (ignore) return;
        setEndpoints(endpointRows);
        setScenarios(scenarioRows);
        setEnvironments(environmentRows);
      })
      .catch((error) => toast.error(apiErrorMessage(error, "接口资产加载失败")));
    return () => {
      ignore = true;
    };
  }, [selectedProjectId]);

  useEffect(() => {
    if (!editTestId || !selectedProjectId) return;
    getPerformanceTest(selectedProjectId, editTestId)
      .then((item) => {
        const r = item.request_config,
          l = item.load_config,
          g = item.performance_goal;
        setName(item.name);
        setDescription(item.description);
        setTargetType(item.target_type);
        setEndpointId(item.endpoint_id ?? "");
        setScenarioId(item.scenario_id ?? "");
        setEnvironmentId(item.api_environment_id ?? "");
        preserveEditedRequest.current = true;
        setPathJson(formatJson(r.path_parameters));
        setQueryJson(formatJson(r.query_parameters));
        setHeadersJson(formatJson(r.headers));
        setBodyJson(formatJson(r.body));
        setTransport(r.transport);
        setScenarioSseStepId(r.scenario_step_id ?? "");
        setSseConfig(r.sse);
        setSseMaxStreamSeconds(String(r.sse?.max_stream_seconds ?? 60));
        setMode(l.mode);
        setStages(l.stages);
        setDataConfig(item.data_config);
        setCircuitBreaker(item.circuit_breaker);
        setNumbers({
          users: String(l.users),
          spawnRate: String(l.spawn_rate),
          duration: String(l.measurement_duration_seconds),
          waitMin: String(l.wait_time_min_seconds),
          waitMax: String(l.wait_time_max_seconds),
          timeout: String(l.request_timeout_seconds),
          stressStartUsers: String(l.stress_start_users ?? 10),
          stressMaxUsers: String(l.stress_max_users ?? 100),
          stressStepUsers: String(l.stress_step_users ?? 10),
          stressHoldSeconds: String(l.stress_hold_seconds ?? 180),
          maxFailPercent: String((g.max_fail_ratio ?? 0) * 100),
          maxAverageMs: String(g.max_average_response_time_ms ?? 3000),
        });
        setSseGoalTargets(
          Object.fromEntries(
            (g.sse_metric_goals ?? []).map((x) => [`${x.metric_id}:${x.percentile}`, String(x.target_ms)]),
          ),
        );
        setRequestTouched(false);
        setEditLoaded(true);
      })
      .catch((error) => toast.error(apiErrorMessage(error, "性能测试加载失败")));
  }, [editTestId, selectedProjectId]);

  useEffect(() => {
    if (targetType !== "endpoint" || !selectedProjectId || !endpointId) return;
    const sequence = ++previewSequence.current;
    setPreview(null);
    setPreviewing(true);
    previewPerformanceRequest(selectedProjectId, {
      endpoint_id: endpointId,
      api_environment_id: environmentId || undefined,
    })
      .then((result) => {
        if (sequence !== previewSequence.current) return;
        setPreview(result);
        if (preserveEditedRequest.current) {
          preserveEditedRequest.current = false;
          return;
        }
        setPathJson(formatJson(result.request_config.path_parameters));
        setQueryJson(formatJson(result.request_config.query_parameters));
        setHeadersJson(formatJson(result.request_config.headers));
        setBodyJson(formatJson(result.request_config.body));
        setRequestTouched(false);
      })
      .catch((error) => {
        if (sequence === previewSequence.current) toast.error(apiErrorMessage(error, "请求配置预览失败"));
      })
      .finally(() => {
        if (sequence === previewSequence.current) setPreviewing(false);
      });
  }, [endpointId, environmentId, selectedProjectId, targetType]);

  function changeMode(nextMode: PerformanceLoadConfig["mode"]) {
    setMode(nextMode);
    setStages(defaultStages(nextMode));
    if (nextMode === "stress") {
      setNumbers((current) => ({
        ...current,
        spawnRate: "2",
        stressStartUsers: "10",
        stressMaxUsers: "100",
        stressStepUsers: "10",
        stressHoldSeconds: "180",
      }));
      setCircuitBreaker({ enabled: true, window_seconds: 30, max_fail_ratio: 0.1, consecutive_windows: 3 });
    }
  }

  function changeEndpoint(nextEndpointId: string) {
    if (requestTouched && !window.confirm("切换接口会重置当前请求配置，继续？")) return;
    setEndpointId(nextEndpointId);
    setSseConfig(null);
    setSseGoalTargets({});
  }

  function changeTargetType(nextTargetType: "endpoint" | "scenario") {
    if (requestTouched && targetType === "endpoint" && !window.confirm("切换压测对象会重置当前请求配置，继续？"))
      return;
    setTargetType(nextTargetType);
    setEndpointId("");
    setScenarioId("");
    setScenarioSseStepId("");
    setPreview(null);
    setRequestTouched(false);
    setSseConfig(null);
    setSseGoalTargets({});
  }

  function changeScenario(nextScenarioId: string) {
    setScenarioId(nextScenarioId);
    setScenarioSseStepId("");
    setSseConfig(null);
    setSseGoalTargets({});
    const scenario = scenarios.find((item) => item.id === nextScenarioId);
    if (scenario?.api_environment_id) changeEnvironment(scenario.api_environment_id);
  }

  function changeEnvironment(nextEnvironmentId: string) {
    setEnvironmentId(nextEnvironmentId);
    setSseConfig(null);
    setSseGoalTargets({});
    const environment = environments.find((item) => item.id === nextEnvironmentId);
    if (environment) {
      setNumbers((current) => ({ ...current, timeout: String(environment.timeout_seconds) }));
    }
  }

  function changeScenarioSseStep(nextStepId: string) {
    setScenarioSseStepId(nextStepId);
    setSseConfig(null);
    setSseGoalTargets({});
  }

  function updateNumber(field: keyof NumericDraft, value: string) {
    setNumbers((current) => ({ ...current, [field]: value }));
  }

  function changeSseConfig(next: PerformanceSseConfig) {
    const metricIds = new Set(next.metrics.map((metric) => metric.id));
    setSseConfig(next);
    setSseGoalTargets((current) =>
      Object.fromEntries(Object.entries(current).filter(([key]) => metricIds.has(key.split(":", 1)[0]))),
    );
  }

  function updateSseGoal(metricId: string, percentile: "p95" | "p99", value: string) {
    setSseGoalTargets((current) => ({ ...current, [`${metricId}:${percentile}`]: value }));
  }

  async function submit() {
    const targetId = targetType === "endpoint" ? endpointId : scenarioId;
    if (!selectedProjectId || !name.trim() || !targetId || !environmentId) {
      toast.error("请选择项目、环境和压测对象，并填写测试名称");
      return;
    }
    if (targetType === "endpoint" && (!preview || preview.endpoint.id !== endpointId)) {
      toast.error("请求配置预览尚未完成，请稍后重试");
      return;
    }
    if (mode !== "fixed" && stages.length === 0) {
      toast.error("当前测试模式至少需要一个负载阶段");
      return;
    }
    if (transport === "sse" && targetType === "scenario" && !scenarioSseStepId) {
      toast.error("请选择场景中的 SSE 接口步骤");
      return;
    }
    setSaving(true);
    try {
      let sse: PerformanceSseConfig | null = null;
      if (transport === "sse") {
        sse = {
          ...(sseConfig ?? { end_rule: null, metrics: [] }),
          max_stream_seconds: positiveNumber(sseMaxStreamSeconds, "SSE 流超时"),
        };
      }
      const savedPayload = {
        name: name.trim(),
        description: description.trim(),
        target_type: targetType,
        endpoint_id: targetType === "endpoint" ? endpointId : null,
        scenario_id: targetType === "scenario" ? scenarioId : null,
        api_environment_id: environmentId,
        request_config: {
          path_parameters: targetType === "endpoint" ? parseObject(pathJson, "Path 参数") : {},
          query_parameters: targetType === "endpoint" ? parseObject(queryJson, "Query 参数") : {},
          headers: targetType === "endpoint" ? parseObject(headersJson, "Headers") : {},
          body: targetType === "endpoint" ? parseJson(bodyJson, "Request Body") : null,
          random_seed: null,
          transport,
          sse,
          scenario_step_id: targetType === "scenario" && transport === "sse" ? scenarioSseStepId : null,
        },
        load_config: {
          mode,
          users: positiveInteger(numbers.users, "用户数"),
          spawn_rate: positiveNumber(numbers.spawnRate, "启动速率"),
          measurement_duration_seconds: positiveInteger(numbers.duration, "运行时长"),
          wait_time_min_seconds: positiveNumber(numbers.waitMin, "最小等待时间"),
          wait_time_max_seconds: positiveNumber(numbers.waitMax, "最大等待时间"),
          request_timeout_seconds: positiveNumber(numbers.timeout, "请求超时"),
          stress_start_users: positiveInteger(numbers.stressStartUsers, "初始用户数"),
          stress_max_users: positiveInteger(numbers.stressMaxUsers, "最大用户数"),
          stress_step_users: positiveInteger(numbers.stressStepUsers, "每级增加用户数"),
          stress_hold_seconds: positiveInteger(numbers.stressHoldSeconds, "每级观察时间"),
          stages: mode === "fixed" || mode === "stress" ? [] : stages,
        },
        data_config: dataConfig,
        circuit_breaker: circuitBreaker,
        performance_goal: compactGoal(numbers, buildSseMetricGoals(sse, sseGoalTargets)),
      };
      const saved = editTestId
        ? await updatePerformanceTest(selectedProjectId, editTestId, savedPayload)
        : await createPerformanceTest(selectedProjectId, savedPayload);
      const script = await generatePerformanceScript(selectedProjectId, saved.id);
      toast.success(editTestId ? "性能测试已更新，Locust 脚本已重新生成" : "性能测试已创建，Locust 脚本已生成");
      router.push(`/projects/${selectedProjectId}/performance-tests/${saved.id}/scripts/${script.id}`);
    } catch (error) {
      toast.error(apiErrorMessage(error, "性能测试创建失败"));
    } finally {
      setSaving(false);
    }
  }

  const scenarioRequestSteps =
    scenarios
      .find((scenario) => scenario.id === scenarioId)
      ?.steps.filter((step) => step.enabled && step.step_type === "api_request" && step.endpoint_id) ?? [];

  if (!editLoaded) return null;

  return (
    <div className="w-full">
      <ShellSection className="overflow-hidden p-0">
        <FieldGroup className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-x-5 gap-y-4 p-5 md:grid-cols-2 [&>*]:min-w-0">
          {/* 头部：基础信息 + 操作按钮 */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-2 md:col-span-2">
            <div className="flex items-center gap-2">
              <FileText className="size-4 text-muted-foreground" />
              <h3 className="font-semibold text-base">基础信息</h3>
            </div>
            <div className="flex items-center gap-2">
              <Button onClick={() => router.back()} variant="outline">
                <ArrowLeft className="size-4" />
                返回
              </Button>
              <Button disabled={saving || previewing} onClick={() => void submit()}>
                {saving ? <LoaderCircle className="animate-spin" /> : <Check />}
                保存并生成 Locust 脚本
              </Button>
            </div>
          </div>

          <Field>
            <FieldLabel htmlFor="test-name">测试名称 *</FieldLabel>
            <Input
              id="test-name"
              maxLength={120}
              onChange={(event) => setName(event.target.value)}
              placeholder="接口性能测试"
              value={name}
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="test-project">项目 *</FieldLabel>
            <Select
              id="test-project"
              placeholder="选择项目"
              setValue={(value) => setSelectedProjectId(value)}
              value={selectedProjectId}
            >
              <SelectOption value="">选择项目</SelectOption>
              {projects.map((project) => (
                <SelectOption key={project.id} value={project.id}>
                  {project.name}
                </SelectOption>
              ))}
            </Select>
          </Field>

          <Field>
            <FieldLabel htmlFor="test-target-type">压测对象 *</FieldLabel>
            <Select
              id="test-target-type"
              placeholder="选择压测对象"
              setValue={(value) => changeTargetType(value as "endpoint" | "scenario")}
              value={targetType}
            >
              <SelectOption value="endpoint">单接口</SelectOption>
              <SelectOption value="scenario">接口场景</SelectOption>
            </Select>
          </Field>

          <Field>
            <FieldLabel htmlFor="test-environment">环境 *</FieldLabel>
            <Select id="test-environment" placeholder="选择环境" setValue={changeEnvironment} value={environmentId}>
              <SelectOption value="">选择环境</SelectOption>
              {environments.map((environment) => (
                <SelectOption key={environment.id} value={environment.id}>
                  {environment.name}
                </SelectOption>
              ))}
            </Select>
          </Field>

          {targetType === "endpoint" ? (
            <Field>
              <FieldLabel htmlFor="test-endpoint">接口 *</FieldLabel>
              <Select id="test-endpoint" placeholder="选择接口" setValue={changeEndpoint} value={endpointId}>
                <SelectOption value="">选择接口</SelectOption>
                {endpoints.map((endpoint) => (
                  <SelectOption key={endpoint.id} value={endpoint.id}>
                    {`${endpoint.method} ${endpoint.path}${endpoint.summary ? ` · ${endpoint.summary}` : ""}`}
                  </SelectOption>
                ))}
              </Select>
            </Field>
          ) : (
            <Field>
              <FieldLabel htmlFor="test-scenario">接口场景 *</FieldLabel>
              <Select id="test-scenario" placeholder="选择接口场景" setValue={changeScenario} value={scenarioId}>
                <SelectOption value="">选择接口场景</SelectOption>
                {scenarios
                  .filter((scenario) => scenario.revision > 0)
                  .map((scenario) => (
                    <SelectOption key={scenario.id} value={scenario.id}>
                      {scenario.name}
                    </SelectOption>
                  ))}
              </Select>
            </Field>
          )}

          <Field>
            <FieldLabel htmlFor="test-mode">测试模式</FieldLabel>
            <Select
              id="test-mode"
              placeholder="选择测试模式"
              setValue={(value) => changeMode(value as PerformanceLoadConfig["mode"])}
              value={mode}
            >
              <SelectOption value="fixed">固定负载</SelectOption>
              <SelectOption value="gradient">手动梯度</SelectOption>
              <SelectOption value="stress">压力测试</SelectOption>
              <SelectOption value="spike">峰值测试</SelectOption>
              <SelectOption value="endurance">耐久测试</SelectOption>
            </Select>
          </Field>

          <Field className="md:col-span-2">
            <FieldLabel htmlFor="test-description">说明</FieldLabel>
            <Textarea
              id="test-description"
              onChange={(event) => setDescription(event.target.value)}
              placeholder="补充说明本次性能测试的目标和场景"
              rows={2}
              value={description}
            />
          </Field>

          {targetType === "endpoint" ? (
            <>
              {/* 请求配置区块 */}
              <div className="flex items-center gap-2 border-b pb-2 md:col-span-2">
                <Settings className="size-4 text-muted-foreground" />
                <h3 className="font-semibold text-base">请求配置</h3>
              </div>

              {previewing ? <p className="text-muted-foreground text-xs md:col-span-2">正在生成请求预览</p> : null}
              {preview?.warnings.map((warning) => (
                <div
                  className="mb-2 flex items-start gap-2 bg-amber-50 px-3 py-2 text-amber-800 text-xs md:col-span-2"
                  key={warning}
                >
                  <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
                  {warning}
                </div>
              ))}

              {hasEntries(preview?.request_config.path_parameters) ? (
                <Field className="md:col-span-2">
                  <FieldLabel htmlFor="test-path-params">Path 参数</FieldLabel>
                  <Textarea
                    id="test-path-params"
                    className="min-h-20 resize-y font-mono text-xs"
                    onChange={(event) => {
                      setPathJson(event.target.value);
                      setRequestTouched(true);
                    }}
                    spellCheck={false}
                    value={pathJson}
                  />
                </Field>
              ) : null}

              {hasEntries(preview?.request_config.query_parameters) ? (
                <Field className="md:col-span-2">
                  <FieldLabel htmlFor="test-query-params">Query 参数</FieldLabel>
                  <Textarea
                    id="test-query-params"
                    className="min-h-20 resize-y font-mono text-xs"
                    onChange={(event) => {
                      setQueryJson(event.target.value);
                      setRequestTouched(true);
                    }}
                    spellCheck={false}
                    value={queryJson}
                  />
                </Field>
              ) : null}

              {hasEntries(preview?.request_config.headers) ? (
                <Field className="md:col-span-2">
                  <FieldLabel htmlFor="test-headers">Headers</FieldLabel>
                  <Textarea
                    id="test-headers"
                    className="min-h-20 resize-y font-mono text-xs"
                    onChange={(event) => {
                      setHeadersJson(event.target.value);
                      setRequestTouched(true);
                    }}
                    spellCheck={false}
                    value={headersJson}
                  />
                </Field>
              ) : null}

              {hasBody(preview?.request_config.body) ? (
                <Field className="md:col-span-2">
                  <FieldLabel htmlFor="test-body">Request Body</FieldLabel>
                  <Textarea
                    id="test-body"
                    className="min-h-20 resize-y font-mono text-xs"
                    onChange={(event) => {
                      setBodyJson(event.target.value);
                      setRequestTouched(true);
                    }}
                    spellCheck={false}
                    value={bodyJson}
                  />
                </Field>
              ) : null}

              <Field>
                <FieldLabel htmlFor="test-transport">响应传输</FieldLabel>
                <Select
                  id="test-transport"
                  placeholder="选择响应传输"
                  setValue={(value) => setTransport(value as "http" | "sse")}
                  value={transport}
                >
                  <SelectOption value="http">普通 HTTP</SelectOption>
                  <SelectOption value="sse">SSE 流式响应</SelectOption>
                </Select>
              </Field>

              {transport === "sse" ? (
                <>
                  <Field>
                    <FieldLabel htmlFor="sse-max-stream">SSE 流超时（秒）</FieldLabel>
                    <Input
                      id="sse-max-stream"
                      min={0.1}
                      onChange={(event) => setSseMaxStreamSeconds(event.target.value)}
                      step={1}
                      type="number"
                      value={sseMaxStreamSeconds}
                    />
                  </Field>
                  <PerformanceSseMetricsConfig
                    endpointId={endpointId}
                    environmentId={environmentId}
                    getRequestValues={() => ({
                      path_parameters: parseObject(pathJson, "Path 参数"),
                      query_parameters: parseObject(queryJson, "Query 参数"),
                      headers: parseObject(headersJson, "Headers"),
                      body: parseJson(bodyJson, "Request Body"),
                    })}
                    maxStreamSeconds={Number(sseMaxStreamSeconds)}
                    onChange={changeSseConfig}
                    projectId={selectedProjectId}
                    targetType="endpoint"
                    value={sseConfig}
                  />
                </>
              ) : null}
            </>
          ) : (
            <>
              <div className="flex items-center gap-2 border-b pb-2 md:col-span-2">
                <Settings className="size-4 text-muted-foreground" />
                <h3 className="font-semibold text-base">请求配置</h3>
              </div>
              <Field>
                <FieldLabel htmlFor="test-transport">响应传输</FieldLabel>
                <Select
                  id="test-transport"
                  placeholder="选择响应传输"
                  setValue={(value) => {
                    setTransport(value as "http" | "sse");
                    setSseConfig(null);
                    setSseGoalTargets({});
                  }}
                  value={transport}
                >
                  <SelectOption value="http">普通 HTTP</SelectOption>
                  <SelectOption value="sse">SSE 流式响应</SelectOption>
                </Select>
              </Field>
              {transport === "sse" ? (
                <>
                  <Field>
                    <FieldLabel htmlFor="scenario-sse-step">SSE 接口步骤</FieldLabel>
                    <Select
                      id="scenario-sse-step"
                      placeholder="选择 SSE 接口步骤"
                      setValue={changeScenarioSseStep}
                      value={scenarioSseStepId}
                    >
                      <SelectOption value="">选择 SSE 接口步骤</SelectOption>
                      {scenarioRequestSteps.map((step) => (
                        <SelectOption key={step.id} value={step.id}>
                          {step.name}
                        </SelectOption>
                      ))}
                    </Select>
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="sse-max-stream">SSE 流超时（秒）</FieldLabel>
                    <Input
                      id="sse-max-stream"
                      min={0.1}
                      onChange={(event) => setSseMaxStreamSeconds(event.target.value)}
                      step={1}
                      type="number"
                      value={sseMaxStreamSeconds}
                    />
                  </Field>
                  <PerformanceSseMetricsConfig
                    environmentId={environmentId}
                    getRequestValues={() => ({
                      path_parameters: {},
                      query_parameters: {},
                      headers: {},
                      body: null,
                    })}
                    maxStreamSeconds={Number(sseMaxStreamSeconds)}
                    onChange={changeSseConfig}
                    projectId={selectedProjectId}
                    scenarioId={scenarioId}
                    scenarioStepId={scenarioSseStepId}
                    targetType="scenario"
                    value={sseConfig}
                  />
                </>
              ) : null}
            </>
          )}

          {/* 测试数据区块 */}
          <div className="flex items-center gap-2 border-b pb-2 md:col-span-2">
            <FileText className="size-4 text-muted-foreground" />
            <h3 className="font-semibold text-base">测试数据</h3>
          </div>

          <Field className="md:col-span-2">
            <PerformanceDataEditor onChange={setDataConfig} value={dataConfig} />
          </Field>

          {/* 负载配置区块 */}
          <div className="flex items-center gap-2 border-b pb-2 md:col-span-2">
            <Gauge className="size-4 text-muted-foreground" />
            <h3 className="font-semibold text-base">负载配置</h3>
          </div>

          {mode !== "stress" ? (
            <Field>
              <LoadConfigFieldLabel
                description="压测需要启动的虚拟用户总数。每个用户会循环执行测试任务。"
                htmlFor="test-users"
                label="用户数"
              />
              <Input
                id="test-users"
                min={1}
                onChange={(event) => updateNumber("users", event.target.value)}
                step={1}
                type="number"
                value={numbers.users}
              />
            </Field>
          ) : (
            <Field>
              <LoadConfigFieldLabel
                description="容量探测开始时的虚拟用户数，作为预热和首个观察级别。"
                htmlFor="test-stress-start-users"
                label="初始用户数"
              />
              <Input
                id="test-stress-start-users"
                min={1}
                onChange={(event) => updateNumber("stressStartUsers", event.target.value)}
                step={1}
                type="number"
                value={numbers.stressStartUsers}
              />
            </Field>
          )}

          <Field>
            <LoadConfigFieldLabel
              description="每秒启动的虚拟用户数量，必须大于 0。压力测试的所有阶梯使用同一速率。"
              htmlFor="test-spawn-rate"
              label="启动速率（用户/秒）"
            />
            <Input
              id="test-spawn-rate"
              min={0.1}
              onChange={(event) => updateNumber("spawnRate", event.target.value)}
              step={0.1}
              type="number"
              value={numbers.spawnRate}
            />
          </Field>

          {mode !== "stress" ? (
            <Field>
              <LoadConfigFieldLabel
                description="从压测启动开始计算的总运行时间，包含用户逐步启动的爬升时间。"
                htmlFor="test-duration"
                label="运行时长（秒）"
              />
              <Input
                id="test-duration"
                min={1}
                onChange={(event) => updateNumber("duration", event.target.value)}
                step={1}
                type="number"
                value={numbers.duration}
              />
            </Field>
          ) : (
            <>
              <Field>
                <LoadConfigFieldLabel
                  description="容量探测允许达到的最高虚拟用户数；未触发熔断时运行到此上限。"
                  htmlFor="test-stress-max-users"
                  label="最大用户数"
                />
                <Input
                  id="test-stress-max-users"
                  min={2}
                  onChange={(event) => updateNumber("stressMaxUsers", event.target.value)}
                  step={1}
                  type="number"
                  value={numbers.stressMaxUsers}
                />
              </Field>
              <Field>
                <LoadConfigFieldLabel
                  description="每完成一个稳定观察阶段后增加的虚拟用户数。"
                  htmlFor="test-stress-step-users"
                  label="每级增加用户数"
                />
                <Input
                  id="test-stress-step-users"
                  min={1}
                  onChange={(event) => updateNumber("stressStepUsers", event.target.value)}
                  step={1}
                  type="number"
                  value={numbers.stressStepUsers}
                />
              </Field>
              <Field>
                <LoadConfigFieldLabel
                  description="到达每个目标用户数后保持负载并采集稳定指标的时间。"
                  htmlFor="test-stress-hold-seconds"
                  label="每级观察时间（秒）"
                />
                <Input
                  id="test-stress-hold-seconds"
                  min={1}
                  onChange={(event) => updateNumber("stressHoldSeconds", event.target.value)}
                  step={1}
                  type="number"
                  value={numbers.stressHoldSeconds}
                />
              </Field>
              <div className="flex items-end text-muted-foreground text-sm">
                系统将按固定启动速率自动生成压力阶梯，触发熔断或达到最大用户数后停止。
              </div>
            </>
          )}

          <Field>
            <LoadConfigFieldLabel
              description="单个请求超过该时间仍未完成时，将被记录为超时失败。"
              htmlFor="test-timeout"
              label="请求超时（秒）"
            />
            <Input
              id="test-timeout"
              min={0.1}
              onChange={(event) => updateNumber("timeout", event.target.value)}
              step={1}
              type="number"
              value={numbers.timeout}
            />
          </Field>
          <Field>
            <LoadConfigFieldLabel
              description="用户完成一次任务后，再次执行前的最短等待时间，不能小于 0.1 秒。"
              htmlFor="test-wait-min"
              label="最小等待时间（秒）"
            />
            <Input
              id="test-wait-min"
              min={0.1}
              onChange={(event) => updateNumber("waitMin", event.target.value)}
              step={1}
              type="number"
              value={numbers.waitMin}
            />
          </Field>

          <Field>
            <LoadConfigFieldLabel
              description="用户完成一次任务后，再次执行前的最长等待时间，不能小于最小等待时间。"
              htmlFor="test-wait-max"
              label="最大等待时间（秒）"
            />
            <Input
              id="test-wait-max"
              min={0.1}
              onChange={(event) => updateNumber("waitMax", event.target.value)}
              step={1}
              type="number"
              value={numbers.waitMax}
            />
          </Field>

          {mode !== "stress" ? (
            <Field className="md:col-span-2">
              <LoadStageEditor mode={mode} onChange={setStages} stages={stages} />
            </Field>
          ) : null}

          {/* 性能目标区块 */}
          <div className="flex items-center gap-2 border-b pb-2 md:col-span-2">
            <Sparkles className="size-4 text-muted-foreground" />
            <h3 className="font-semibold text-base">性能目标</h3>
          </div>

          <Field>
            <FieldLabel htmlFor="test-max-fail-percent">最大失败率（%）</FieldLabel>
            <Input
              id="test-max-fail-percent"
              min={0}
              onChange={(event) => updateNumber("maxFailPercent", event.target.value)}
              step={0.1}
              type="number"
              value={numbers.maxFailPercent}
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="test-max-avg-ms">最大平均响应（ms）</FieldLabel>
            <Input
              id="test-max-avg-ms"
              min={0}
              onChange={(event) => updateNumber("maxAverageMs", event.target.value)}
              type="number"
              value={numbers.maxAverageMs}
            />
          </Field>

          {transport === "sse" && sseConfig?.metrics.length ? (
            <section className="space-y-3 border-t pt-4 md:col-span-2" aria-labelledby="sse-goals-heading">
              <div>
                <h4 className="font-medium text-sm" id="sse-goals-heading">
                  SSE 事件指标目标
                </h4>
                <p className="mt-1 text-muted-foreground text-xs">留空表示仅观测，不参与通过判定。</p>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                {sseConfig.metrics.map((metric) => (
                  <div className="grid grid-cols-2 gap-3 border-t pt-3" key={metric.id}>
                    <p className="col-span-2 truncate font-medium text-sm" title={metric.name}>
                      {metric.name}
                    </p>
                    {(["p95", "p99"] as const).map((percentile) => (
                      <Field key={percentile}>
                        <FieldLabel htmlFor={`sse-goal-${metric.id}-${percentile}`}>
                          {percentile.toUpperCase()} 上限（ms）
                        </FieldLabel>
                        <Input
                          id={`sse-goal-${metric.id}-${percentile}`}
                          min={0.1}
                          onChange={(event) => updateSseGoal(metric.id, percentile, event.target.value)}
                          placeholder="不设目标"
                          step={1}
                          type="number"
                          value={sseGoalTargets[`${metric.id}:${percentile}`] ?? ""}
                        />
                      </Field>
                    ))}
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {/* 安全熔断区块 */}
          <div className="flex items-center gap-2 border-b pb-2 md:col-span-2">
            <Settings className="size-4 text-muted-foreground" />
            <h3 className="font-semibold text-base">安全熔断</h3>
          </div>

          <Field className="md:col-span-2">
            <label className="flex items-center gap-2">
              <input
                checked={circuitBreaker.enabled}
                onChange={(event) => setCircuitBreaker((current) => ({ ...current, enabled: event.target.checked }))}
                type="checkbox"
              />
              <span className="text-sm">启用失败率安全熔断</span>
            </label>
          </Field>

          {circuitBreaker.enabled ? (
            <>
              <Field>
                <FieldLabel htmlFor="test-cb-window">检测窗口（秒）</FieldLabel>
                <Input
                  id="test-cb-window"
                  min={1}
                  onChange={(event) =>
                    setCircuitBreaker((current) => ({ ...current, window_seconds: Number(event.target.value) }))
                  }
                  type="number"
                  value={circuitBreaker.window_seconds}
                />
              </Field>

              <Field>
                <FieldLabel htmlFor="test-cb-max-fail">最大失败率（%）</FieldLabel>
                <Input
                  id="test-cb-max-fail"
                  min={0}
                  onChange={(event) =>
                    setCircuitBreaker((current) => ({
                      ...current,
                      max_fail_ratio: Number(event.target.value) / 100,
                    }))
                  }
                  step={0.1}
                  type="number"
                  value={circuitBreaker.max_fail_ratio * 100}
                />
              </Field>

              <Field>
                <FieldLabel htmlFor="test-cb-consecutive">连续超标次数</FieldLabel>
                <Input
                  id="test-cb-consecutive"
                  min={1}
                  onChange={(event) =>
                    setCircuitBreaker((current) => ({
                      ...current,
                      consecutive_windows: Number(event.target.value),
                    }))
                  }
                  type="number"
                  value={circuitBreaker.consecutive_windows}
                />
              </Field>
            </>
          ) : null}
        </FieldGroup>
      </ShellSection>
    </div>
  );
}

function defaultStages(mode: PerformanceLoadConfig["mode"]): PerformanceLoadStage[] {
  if (mode === "fixed" || mode === "stress") return [];
  if (mode === "spike") {
    return [
      { name: "正常负载", target_users: 20, spawn_rate: 5, hold_seconds: 180, order: 0 },
      { name: "突发峰值", target_users: 200, spawn_rate: 100, hold_seconds: 60, order: 1 },
      { name: "恢复负载", target_users: 20, spawn_rate: 100, hold_seconds: 180, order: 2 },
    ];
  }
  if (mode === "endurance") {
    return [{ name: "耐久阶段", target_users: 100, spawn_rate: 10, hold_seconds: 3600, order: 0 }];
  }
  return [
    { name: "阶段 1", target_users: 10, spawn_rate: 2, hold_seconds: 60, order: 0 },
    { name: "阶段 2", target_users: 50, spawn_rate: 5, hold_seconds: 180, order: 1 },
    { name: "阶段 3", target_users: 100, spawn_rate: 10, hold_seconds: 300, order: 2 },
  ];
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function hasEntries(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value) && Object.keys(value).length > 0;
}

function hasBody(value: unknown) {
  if (value === null || value === undefined || value === "") return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value).length > 0;
  return true;
}

function parseJson(value: string, label: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    throw new Error(`${label} 必须是有效 JSON`);
  }
}

function parseObject(value: string, label: string): Record<string, unknown> {
  const parsed = parseJson(value, label);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error(`${label} 必须是 JSON 对象`);
  return parsed as Record<string, unknown>;
}

function positiveNumber(value: string, label: string) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) throw new Error(`${label} 必须大于 0`);
  return parsed;
}

function positiveInteger(value: string, label: string) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) throw new Error(`${label} 必须是大于 0 的整数`);
  return parsed;
}

function compactGoal(numbers: NumericDraft, sseMetricGoals: PerformanceSseMetricGoal[]) {
  const goal: Record<string, number | PerformanceSseMetricGoal[]> = {};
  if (numbers.maxFailPercent) goal.max_fail_ratio = Number(numbers.maxFailPercent) / 100;
  if (numbers.maxAverageMs)
    goal.max_average_response_time_ms = positiveNumber(numbers.maxAverageMs, "最大平均响应时间");
  if (sseMetricGoals.length) goal.sse_metric_goals = sseMetricGoals;
  return goal;
}

function buildSseMetricGoals(
  sse: PerformanceSseConfig | null,
  targets: Record<string, string>,
): PerformanceSseMetricGoal[] {
  if (!sse) return [];
  return sse.metrics.flatMap((metric) =>
    (["p95", "p99"] as const).flatMap((percentile) => {
      const raw = targets[`${metric.id}:${percentile}`]?.trim();
      if (!raw) return [];
      return [
        {
          metric_id: metric.id,
          percentile,
          operator: "lte" as const,
          target_ms: positiveNumber(raw, `${metric.name} ${percentile.toUpperCase()} 上限`),
        },
      ];
    }),
  );
}

function apiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiRequestError) return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}
