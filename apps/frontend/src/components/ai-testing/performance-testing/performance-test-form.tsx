"use client";

import { useEffect, useRef, useState } from "react";

import { useRouter } from "next/navigation";

import { AlertTriangle, ArrowLeft, Check, FileText, Gauge, LoaderCircle, Settings, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { ShellSection } from "@/components/ai-testing/page-shell";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  type ApiAutomationEndpoint,
  type ApiAutomationEnvironment,
  type ApiProject,
  ApiRequestError,
  apiRequest,
  createPerformanceScenario,
  listApiAutomationEndpoints,
  listApiAutomationEnvironments,
  type PerformanceCircuitBreaker,
  type PerformanceDataConfig,
  type PerformanceLoadStage,
  type PerformanceRequestPreview,
  type PerformanceScenarioCreatePayload,
  previewPerformanceRequest,
} from "@/lib/api-client";

import { LoadStageEditor } from "./load-stage-editor";
import { PerformanceDataEditor } from "./performance-data-editor";

type NumericDraft = {
  waitMin: string;
  waitMax: string;
  timeout: string;
  maxFailPercent: string;
  maxAverageMs: string;
  users: string;
  spawnRate: string;
  warmup: string;
  measurement: string;
  stopTimeout: string;
};

const initialNumbers: NumericDraft = {
  waitMin: "1",
  waitMax: "3",
  timeout: "30",
  maxFailPercent: "0",
  maxAverageMs: "3000",
  users: "10",
  spawnRate: "1",
  warmup: "30",
  measurement: "60",
  stopTimeout: "10",
};

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

export function PerformanceTestForm({ initialProjectId = "" }: { initialProjectId?: string }) {
  const router = useRouter();
  const previewSequence = useRef(0);
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState(initialProjectId);
  const [endpoints, setEndpoints] = useState<ApiAutomationEndpoint[]>([]);
  const [environments, setEnvironments] = useState<ApiAutomationEnvironment[]>([]);
  const [endpointId, setEndpointId] = useState("");
  const [environmentId, setEnvironmentId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [pathJson, setPathJson] = useState("{}");
  const [queryJson, setQueryJson] = useState("{}");
  const [headersJson, setHeadersJson] = useState("{}");
  const [bodyJson, setBodyJson] = useState("null");
  const [successCodes, setSuccessCodes] = useState("200");
  const [mode, setMode] = useState<"fixed" | "staged">("fixed");
  const [stages, setStages] = useState<PerformanceLoadStage[]>([]);
  const [dataConfig, setDataConfig] = useState<PerformanceDataConfig>(initialDataConfig);
  const [circuitBreaker, setCircuitBreaker] = useState<PerformanceCircuitBreaker>(initialCircuitBreaker);
  const [numbers, setNumbers] = useState<NumericDraft>(initialNumbers);
  const [preview, setPreview] = useState<PerformanceRequestPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [requestTouched, setRequestTouched] = useState(false);

  useEffect(() => {
    apiRequest<ApiProject[]>("/projects")
      .then((rows) => {
        const active = rows.filter((project) => project.status === "active");
        setProjects(active);
        if (initialProjectId && active.some((project) => project.id === initialProjectId)) {
          setSelectedProjectId(initialProjectId);
        }
      })
      .catch((error) => toast.error(apiErrorMessage(error, "项目加载失败")));
  }, [initialProjectId]);

  useEffect(() => {
    setEndpoints([]);
    setEnvironments([]);
    setEndpointId("");
    setEnvironmentId("");
    setPreview(null);
    setRequestTouched(false);
    setPathJson("{}");
    setQueryJson("{}");
    setHeadersJson("{}");
    setBodyJson("null");
    setDataConfig(initialDataConfig);
    if (!selectedProjectId) return;
    let ignore = false;
    Promise.all([listApiAutomationEndpoints(selectedProjectId), listApiAutomationEnvironments(selectedProjectId)])
      .then(([endpointRows, environmentRows]) => {
        if (ignore) return;
        setEndpoints(endpointRows);
        setEnvironments(environmentRows);
        setEndpointId(endpointRows[0]?.id ?? "");
        setEnvironmentId(environmentRows[0]?.id ?? "");
        if (environmentRows[0]) {
          setNumbers((current) => ({ ...current, timeout: String(environmentRows[0].timeout_seconds) }));
        }
      })
      .catch((error) => toast.error(apiErrorMessage(error, "接口资产加载失败")));
    return () => {
      ignore = true;
    };
  }, [selectedProjectId]);

  useEffect(() => {
    if (!selectedProjectId || !endpointId) return;
    const sequence = ++previewSequence.current;
    setPreviewing(true);
    previewPerformanceRequest(selectedProjectId, {
      endpoint_id: endpointId,
      api_environment_id: environmentId || undefined,
    })
      .then((result) => {
        if (sequence !== previewSequence.current) return;
        setPreview(result);
        setPathJson(formatJson(result.request_config.path_parameters));
        setQueryJson(formatJson(result.request_config.query_parameters));
        setHeadersJson(formatJson(result.request_config.headers));
        setBodyJson(formatJson(result.request_config.body));
        const statusRule = result.success_rules.find((rule) => rule.kind === "status_code");
        setSuccessCodes((statusRule?.status_codes ?? [200]).join(", "));
        setRequestTouched(false);
        setName((current) => current.trim() || `${result.endpoint.name}性能测试`);
      })
      .catch((error) => {
        if (sequence === previewSequence.current) toast.error(apiErrorMessage(error, "请求配置预览失败"));
      })
      .finally(() => {
        if (sequence === previewSequence.current) setPreviewing(false);
      });
  }, [endpointId, environmentId, selectedProjectId]);

  function changeMode(nextMode: "fixed" | "staged") {
    setMode(nextMode);
    setStages(nextMode === "fixed" ? [] : defaultStages("gradient"));
  }

  function changeEndpoint(nextEndpointId: string) {
    if (requestTouched && !window.confirm("切换接口会重置当前请求配置，继续？")) return;
    setEndpointId(nextEndpointId);
  }

  function updateNumber(field: keyof NumericDraft, value: string) {
    setNumbers((current) => ({ ...current, [field]: value }));
  }

  async function submit() {
    if (!selectedProjectId || !name.trim() || !endpointId || !environmentId) {
      toast.error("请选择项目、环境和接口，并填写测试名称");
      return;
    }
    if (mode === "staged" && stages.length === 0) {
      toast.error("当前测试模式至少需要一个负载阶段");
      return;
    }
    setSaving(true);
    try {
      const loadProfile =
        mode === "fixed"
          ? {
              mode: "fixed",
              target_users: positiveNumber(numbers.users, "目标用户数"),
              spawn_rate: positiveNumber(numbers.spawnRate, "爬升速率"),
              warmup_seconds: nonNegativeInteger(numbers.warmup, "预热时长"),
              measurement_seconds: positiveNumber(numbers.measurement, "测量时长"),
              stop_timeout_seconds: nonNegativeInteger(numbers.stopTimeout, "停止超时"),
            }
          : {
              mode: "staged",
              stages: stages.map((stage) => ({
                name: stage.name,
                target_users: stage.target_users,
                spawn_rate: stage.spawn_rate,
                hold_seconds: stage.hold_seconds,
                record_metrics: true,
              })),
              stop_timeout_seconds: nonNegativeInteger(numbers.stopTimeout, "停止超时"),
            };
      const payload: PerformanceScenarioCreatePayload = {
        name: name.trim(),
        description: description.trim(),
        api_environment_id: environmentId,
        scenario_definition: {
          personas: [
            {
              id: "default",
              name: "默认用户",
              wait_time: {
                min_seconds: positiveNumber(numbers.waitMin, "最小等待时间"),
                max_seconds: positiveNumber(numbers.waitMax, "最大等待时间"),
              },
              steps: [
                {
                  type: "http",
                  endpoint_id: endpointId,
                  request: {
                    path_parameters: parseObject(pathJson, "Path 参数"),
                    query_parameters: parseObject(queryJson, "Query 参数"),
                    headers: parseObject(headersJson, "Headers"),
                    body: parseJson(bodyJson, "Request Body"),
                    timeout_seconds: positiveNumber(numbers.timeout, "请求超时"),
                  },
                  assertions: [
                    {
                      kind: "status_code",
                      status_codes: successCodes
                        .split(",")
                        .map((value) => Number(value.trim()))
                        .filter(Number.isInteger),
                    },
                  ],
                },
              ],
            },
          ],
        },
        load_profile: loadProfile,
        data_source: {
          source: dataConfig.source,
          selection_strategy: dataConfig.selection_strategy,
          rows: dataConfig.json_rows,
        },
        quality_gate: compactGoal(numbers),
        safety_policy: circuitBreaker,
      };
      await createPerformanceScenario(selectedProjectId, payload);
      toast.success("托管性能场景已创建");
      router.push(`/projects/${selectedProjectId}/performance-tests`);
    } catch (error) {
      toast.error(apiErrorMessage(error, "性能测试创建失败"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="w-full">
      <ShellSection className="overflow-hidden p-0">
        <FieldGroup className="grid gap-x-5 gap-y-4 p-5 md:grid-cols-2">
          {/* 头部：基础信息 + 操作按钮 */}
          <div className="flex items-center justify-between gap-2 border-b pb-2 md:col-span-2">
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
                创建托管性能场景
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
            <FieldLabel htmlFor="test-environment">环境 *</FieldLabel>
            <Select
              id="test-environment"
              placeholder="选择环境"
              setValue={(value) => setEnvironmentId(value)}
              value={environmentId}
            >
              <SelectOption value="">选择环境</SelectOption>
              {environments.map((environment) => (
                <SelectOption key={environment.id} value={environment.id}>
                  {environment.name}
                </SelectOption>
              ))}
            </Select>
          </Field>

          <Field>
            <FieldLabel htmlFor="test-endpoint">接口 *</FieldLabel>
            <Select
              id="test-endpoint"
              placeholder="选择接口"
              setValue={(value) => changeEndpoint(value)}
              value={endpointId}
            >
              <SelectOption value="">选择接口</SelectOption>
              {endpoints.map((endpoint) => (
                <SelectOption key={endpoint.id} value={endpoint.id}>
                  {`${endpoint.method} ${endpoint.path}${endpoint.summary ? ` · ${endpoint.summary}` : ""}`}
                </SelectOption>
              ))}
            </Select>
          </Field>

          <Field>
            <FieldLabel htmlFor="test-mode">负载计划</FieldLabel>
            <Select
              id="test-mode"
              placeholder="选择测试模式"
              setValue={(value) => changeMode(value as "fixed" | "staged")}
              value={mode}
            >
              <SelectOption value="fixed">固定负载</SelectOption>
              <SelectOption value="staged">阶段负载</SelectOption>
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
            <FieldLabel htmlFor="test-success-codes">成功状态码</FieldLabel>
            <Input
              id="test-success-codes"
              onChange={(event) => setSuccessCodes(event.target.value)}
              placeholder="200, 201"
              value={successCodes}
            />
          </Field>

          {mode === "fixed" ? (
            <>
              <Field>
                <FieldLabel htmlFor="test-users">目标用户数</FieldLabel>
                <Input
                  id="test-users"
                  min={1}
                  onChange={(event) => updateNumber("users", event.target.value)}
                  type="number"
                  value={numbers.users}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="test-spawn-rate">爬升速率（用户/秒）</FieldLabel>
                <Input
                  id="test-spawn-rate"
                  min={0.1}
                  onChange={(event) => updateNumber("spawnRate", event.target.value)}
                  step={0.1}
                  type="number"
                  value={numbers.spawnRate}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="test-warmup">预热时长（秒）</FieldLabel>
                <Input
                  id="test-warmup"
                  min={0}
                  onChange={(event) => updateNumber("warmup", event.target.value)}
                  type="number"
                  value={numbers.warmup}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="test-measurement">测量时长（秒）</FieldLabel>
                <Input
                  id="test-measurement"
                  min={1}
                  onChange={(event) => updateNumber("measurement", event.target.value)}
                  type="number"
                  value={numbers.measurement}
                />
              </Field>
            </>
          ) : null}

          <Field>
            <FieldLabel htmlFor="test-stop-timeout">停止超时（秒）</FieldLabel>
            <Input
              id="test-stop-timeout"
              min={0}
              onChange={(event) => updateNumber("stopTimeout", event.target.value)}
              type="number"
              value={numbers.stopTimeout}
            />
          </Field>

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

          <Field>
            <FieldLabel htmlFor="test-wait-min">最小等待时间（秒）</FieldLabel>
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
            <FieldLabel htmlFor="test-wait-max">最大等待时间（秒）</FieldLabel>
            <Input
              id="test-wait-max"
              min={0.1}
              onChange={(event) => updateNumber("waitMax", event.target.value)}
              step={1}
              type="number"
              value={numbers.waitMax}
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="test-timeout">请求超时（秒）</FieldLabel>
            <Input
              id="test-timeout"
              min={0.1}
              onChange={(event) => updateNumber("timeout", event.target.value)}
              step={1}
              type="number"
              value={numbers.timeout}
            />
          </Field>

          <Field className="md:col-span-2">
            <LoadStageEditor mode={mode === "staged" ? "gradient" : "fixed"} onChange={setStages} stages={stages} />
          </Field>

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

function defaultStages(mode: "gradient" | "spike" | "endurance"): PerformanceLoadStage[] {
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

function nonNegativeInteger(value: string, label: string) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0) throw new Error(`${label} 必须是非负整数`);
  return parsed;
}

function compactGoal(numbers: NumericDraft) {
  const goal: Record<string, number> = {};
  if (numbers.maxFailPercent) goal.max_fail_ratio = Number(numbers.maxFailPercent) / 100;
  if (numbers.maxAverageMs)
    goal.max_average_response_time_ms = positiveNumber(numbers.maxAverageMs, "最大平均响应时间");
  return goal;
}

function apiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiRequestError) return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}
