"use client";

import { useState } from "react";

import Link from "next/link";

import {
  AlertTriangle,
  ArrowLeft,
  Clock3,
  GitBranch,
  Loader2,
  PanelRightClose,
  PanelRightOpen,
  Play,
  Plus,
  Save,
  ShieldCheck,
  Sparkles,
  Trash2,
  Variable,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { ApiAutomationEndpoint, ApiScenarioAiPlanAccepted } from "@/lib/api-client";
import { cn } from "@/lib/utils";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./api-orchestration-select";
import { ApiScenarioAiReviewDrawer } from "./api-scenario-ai-review-drawer";
import { ApiScenarioAssetPicker } from "./api-scenario-asset-picker";
import { ApiScenarioCanvas } from "./api-scenario-canvas";
import { ApiScenarioRunDrawer } from "./api-scenario-run-drawer";
import { ApiScenarioStepConfig } from "./api-scenario-step-config";
import { ApiScenarioVersionPanel } from "./api-scenario-version-panel";
import { useApiScenarioEditor } from "./use-api-scenario-editor";

type ApiScenarioEditorProps = { projectId: string; scenarioId?: string };
type EditorView = "orchestration" | "variables" | "versions";
type AiDrawerMode = "closed" | "generation" | "review";

const methodTone: Record<string, string> = {
  GET: "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-500/35 dark:bg-blue-500/15 dark:text-blue-200",
  POST: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/35 dark:bg-emerald-500/15 dark:text-emerald-200",
  PUT: "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/35 dark:bg-amber-500/15 dark:text-amber-200",
  PATCH:
    "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-500/35 dark:bg-violet-500/15 dark:text-violet-200",
  DELETE: "border-red-200 bg-red-50 text-red-700 dark:border-red-500/35 dark:bg-red-500/15 dark:text-red-200",
};

export function ApiScenarioEditor({ projectId, scenarioId }: ApiScenarioEditorProps) {
  const editor = useApiScenarioEditor(projectId, scenarioId);
  const [view, setView] = useState<EditorView>("orchestration");
  const [configPanelOpen, setConfigPanelOpen] = useState(false);
  const [assetPickerOpen, setAssetPickerOpen] = useState(false);
  const [aiDrawerMode, setAiDrawerMode] = useState<AiDrawerMode>("closed");
  const [aiSourceEndpointIds, setAiSourceEndpointIds] = useState<string[]>([]);
  const selectedEnvironment = editor.environments.find((item) => item.id === editor.selectedEnvironmentId);

  const activeIndex = editor.draft.steps.findIndex((step) => step.id === editor.activeStepId);
  const precedingSteps = activeIndex < 0 ? [] : editor.draft.steps.slice(0, activeIndex);

  if (editor.loading === true)
    return (
      <div className="grid min-h-[520px] place-items-center rounded-2xl border bg-card">
        <Loader2 className="size-6 animate-spin text-primary" />
      </div>
    );
  if (editor.loadError)
    return (
      <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-8 text-center">
        <p className="text-destructive text-sm">{editor.loadError}</p>
        <Button asChild className="mt-4" variant="outline">
          <Link href={`/projects/${projectId}/automation/api?tab=scenarios`}>返回场景列表</Link>
        </Button>
      </div>
    );

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-border/90 bg-card shadow-[0_24px_70px_color-mix(in_srgb,var(--primary),transparent_88%)]">
      <header className="flex min-h-[70px] shrink-0 flex-wrap items-center justify-between gap-3 border-b bg-card/95 px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <Button asChild size="icon-sm" variant="outline">
            <Link href={`/projects/${projectId}/automation/api?tab=scenarios`}>
              <ArrowLeft />
            </Link>
          </Button>
          <div className="min-w-0">
            <div className="flex flex-nowrap items-center gap-2">
              <Input
                className="h-8 w-72 min-w-52 max-w-[32vw] flex-none border-transparent bg-transparent px-1 font-semibold text-sm shadow-none hover:border-border focus-visible:border-border"
                onChange={(event) => editor.actions.updateScenarioMeta({ name: event.target.value })}
                placeholder="请输入场景名称"
                value={editor.draft.name}
              />
              <Badge
                className="bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200"
                variant="secondary"
              >
                {editor.scenario?.revision ? `当前 v${editor.scenario.revision}` : "未保存版本"}
              </Badge>
              {editor.scenario?.asset_changes.length ? (
                <span className="flex shrink-0 items-center gap-1 whitespace-nowrap text-[11px] text-amber-700 dark:text-amber-300">
                  <AlertTriangle className="size-3" />
                  {editor.scenario.asset_changes.length} 项接口资产变更待确认
                </span>
              ) : editor.dirty === true ? (
                <span className="shrink-0 whitespace-nowrap text-[11px] text-amber-700 dark:text-amber-300">
                  存在未保存修改
                </span>
              ) : null}
              <span className="shrink-0 whitespace-nowrap text-[11px] text-muted-foreground">
                {editor.draft.steps.length} 个步骤
              </span>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            onClick={() => {
              setAiSourceEndpointIds([]);
              setAiDrawerMode(editor.aiPlan ? "review" : "generation");
            }}
            size="sm"
            variant="outline"
          >
            <Sparkles />
            AI 编排
          </Button>
          <Select
            disabled={editor.environmentSaving}
            onValueChange={editor.actions.persistSelectedEnvironment}
            value={editor.selectedEnvironmentId}
          >
            <SelectTrigger className="w-40">
              <SelectValue placeholder="选择运行环境" />
            </SelectTrigger>
            <SelectContent>
              {editor.environments.map((environment) => (
                <SelectItem key={environment.id} value={environment.id}>
                  {environment.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {editor.latestRunId ? (
            <Button
              className={cn(
                "gap-2",
                isFailedRunStatus(editor.latestRunStatus) &&
                  "border-red-200 bg-red-50 text-red-700 hover:bg-red-100 hover:text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200",
                editor.latestRunStatus === "passed" &&
                  "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 hover:text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200",
              )}
              onClick={() => {
                setConfigPanelOpen(false);
                editor.actions.setRunDrawerOpen(true);
              }}
              size="sm"
              title="查看最近一次运行结果"
              variant="outline"
            >
              {isFailedRunStatus(editor.latestRunStatus) ? (
                <AlertTriangle className="size-4" />
              ) : editor.latestRunStatus === "passed" ? (
                <ShieldCheck className="size-4" />
              ) : (
                <Loader2 className="size-4 animate-spin" />
              )}
              {runStatusLabel(editor.latestRunStatus)}
              {editor.scenarioRunResult ? (
                <span className="font-mono text-[10px] opacity-70">
                  {editor.scenarioRunResult.steps.filter((step) => step.status === "passed").length}/
                  {editor.scenarioRunResult.steps.length}
                </span>
              ) : null}
            </Button>
          ) : null}
          <Button
            disabled={!editor.scenario || editor.busy || !editor.dirty}
            onClick={() => void editor.actions.saveScenario()}
            size="sm"
            variant="outline"
          >
            <Save />
            保存版本
          </Button>
          <Button
            disabled={!editor.scenario || editor.busy}
            onClick={() => {
              setConfigPanelOpen(false);
              void editor.actions.executeScenario();
            }}
            size="sm"
          >
            <Play />
            运行场景
          </Button>
        </div>
      </header>

      <nav className="flex h-11 shrink-0 items-stretch gap-6 border-b bg-muted/15 px-5">
        <NavButton
          active={view === "orchestration"}
          icon={GitBranch}
          label="编排"
          onClick={() => setView("orchestration")}
        />
        <NavButton
          active={view === "variables"}
          count={Object.keys(editor.draft.variables).length}
          icon={Variable}
          label="场景变量"
          onClick={() => setView("variables")}
        />
        <NavButton active={view === "versions"} icon={Clock3} label="版本记录" onClick={() => setView("versions")} />
      </nav>

      {view === "orchestration" ? (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="flex h-12 shrink-0 items-center justify-between border-b bg-card/80 px-4">
            <div className="flex items-center gap-2">
              <div className="grid size-7 place-items-center rounded-lg bg-primary/10 text-primary">
                <GitBranch className="size-3.5" />
              </div>
              <div>
                <div className="font-semibold text-sm">执行链路</div>
                <div className="text-[10px] text-muted-foreground">以依赖关系查看场景</div>
              </div>
            </div>
            <Button
              aria-label={configPanelOpen ? "隐藏节点配置" : "显示节点配置"}
              className="h-8 gap-1.5 px-2.5 text-xs"
              onClick={() => setConfigPanelOpen((current) => !current)}
              size="sm"
              title={configPanelOpen ? "隐藏节点配置" : "显示节点配置"}
              variant="outline"
            >
              {configPanelOpen ? <PanelRightClose className="size-3.5" /> : <PanelRightOpen className="size-3.5" />}
              {configPanelOpen ? "隐藏配置" : "显示配置"}
            </Button>
          </div>
          <div
            className={cn(
              "grid min-h-0 flex-1 overflow-hidden",
              configPanelOpen ? "grid-cols-[minmax(0,1fr)_clamp(360px,32vw,500px)]" : "grid-cols-1",
            )}
          >
            <ApiScenarioCanvas
              activeStepId={editor.activeStepId}
              endpoints={editor.endpoints}
              onAddUtilityStep={editor.actions.addUtilityStep}
              onClearSelection={() => {
                editor.actions.setActiveStepId("");
                setConfigPanelOpen(false);
              }}
              onDeleteStep={(stepId) => {
                editor.actions.removeStep(stepId);
                setConfigPanelOpen(false);
              }}
              onOpenAssetPicker={() => setAssetPickerOpen(true)}
              onSelectStep={(stepId) => {
                editor.actions.setActiveStepId(stepId);
                setConfigPanelOpen(true);
              }}
              steps={editor.draft.steps}
            />
            {configPanelOpen ? (
              <div className="flex min-h-0 min-w-0 flex-col overflow-hidden border-l">
                <ApiScenarioStepConfig
                  activeStep={editor.activeStep}
                  endpoints={editor.endpoints}
                  environment={editor.selectedEnvironment}
                  onUpdateStep={editor.actions.updateStep}
                  precedingSteps={precedingSteps}
                  projectId={projectId}
                  scenarioVariables={editor.draft.variables}
                />
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
      {view === "variables" ? (
        <VariablesPanel
          onChange={(variables) => editor.actions.updateScenarioMeta({ variables })}
          variables={editor.draft.variables}
        />
      ) : null}
      {view === "versions" ? (
        <ApiScenarioVersionPanel
          busy={editor.busy}
          currentRevision={editor.scenario?.revision ?? 0}
          onRestore={editor.actions.restoreRevision}
          revisions={editor.revisions}
        />
      ) : null}
      <ApiScenarioAssetPicker
        endpoints={editor.endpoints}
        onAiOrchestration={(endpointIds) => {
          setAiSourceEndpointIds(endpointIds);
          setAiDrawerMode(editor.aiPlan ? "review" : "generation");
        }}
        onConfirm={editor.actions.addEndpointSteps}
        onOpenChange={setAssetPickerOpen}
        open={assetPickerOpen}
      />
      {editor.aiPlan ? (
        <ApiScenarioAiReviewDrawer
          busy={editor.aiBusy}
          onApply={async () => {
            const applied = await editor.actions.applyAiPlan();
            if (applied) setAiDrawerMode("closed");
          }}
          onChangeField={editor.actions.updateAiReviewField}
          onConfirmAll={editor.actions.confirmAllAiReviewFields}
          onConfirmField={editor.actions.confirmAiReviewField}
          onConfirmStep={editor.actions.confirmAiReviewStep}
          onDiscard={() => {
            editor.actions.discardAiPlan();
            setAiDrawerMode("closed");
          }}
          onMoveStep={editor.actions.reorderAiReviewStep}
          onOpenChange={(open) => setAiDrawerMode(open ? "review" : "closed")}
          open={aiDrawerMode === "review"}
          plan={editor.aiPlan}
          environmentVariableNames={Object.keys(selectedEnvironment?.variables ?? {})}
          scenarioVariableNames={Object.keys(editor.draft.variables)}
        />
      ) : (
        <AiOrchestrationDrawer
          busy={editor.aiBusy}
          endpoints={editor.endpoints}
          lifecycleStatus={editor.aiLifecycleStatus}
          selectedEndpointIds={aiSourceEndpointIds}
          onGenerate={async (goal, options) => {
            const accepted = await editor.actions.generateAiPlan(goal, aiSourceEndpointIds, options);
            if (accepted) setAiDrawerMode("closed");
            return accepted;
          }}
          onOpenChange={(open) => setAiDrawerMode(open ? "generation" : "closed")}
          open={aiDrawerMode === "generation"}
        />
      )}
      <ApiScenarioRunDrawer
        busy={editor.busy}
        onJumpToStep={(stepId) => {
          setView("orchestration");
          editor.actions.setActiveStepId(stepId);
          setConfigPanelOpen(true);
        }}
        onOpenChange={editor.actions.setRunDrawerOpen}
        onRerun={() => void editor.actions.executeScenario()}
        open={editor.runDrawerOpen}
        result={editor.scenarioRunResult}
        runId={editor.latestRunId}
        status={editor.latestRunStatus}
        stepConfigs={editor.draft.steps}
      />
    </section>
  );
}

function AiOrchestrationDrawer({
  busy,
  endpoints,
  lifecycleStatus,
  onGenerate,
  onOpenChange,
  open,
  selectedEndpointIds,
}: {
  busy: boolean;
  endpoints: ApiAutomationEndpoint[];
  lifecycleStatus: "generating" | "completed" | "failed" | "expired" | null;
  onGenerate: (goal: string, options: { requireCleanup: boolean }) => Promise<ApiScenarioAiPlanAccepted | null>;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  selectedEndpointIds: string[];
}) {
  const [goal, setGoal] = useState("");
  const [requireCleanup, setRequireCleanup] = useState(false);
  const selectedEndpoints = selectedEndpointIds
    .map((endpointId) => endpoints.find((endpoint) => endpoint.id === endpointId))
    .filter((endpoint): endpoint is ApiAutomationEndpoint => Boolean(endpoint));

  return (
    <Drawer direction="right" handleOnly open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="grid h-full w-full grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden bg-background p-0 data-[vaul-drawer-direction=right]:w-[min(92vw,760px)] data-[vaul-drawer-direction=right]:sm:max-w-[760px]">
        <DrawerHeader className="relative border-b bg-muted/20 px-5 py-4 sm:px-6">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative grid size-8 shrink-0 place-items-center rounded-md border border-primary/20 bg-primary/8 text-primary shadow-xs">
              <GitBranch className="size-4" />
              <Sparkles className="absolute -top-1 -right-1 size-3 rounded-full bg-background p-0.5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <DrawerTitle className="font-semibold text-base leading-6 sm:text-lg">AI 编排接口场景</DrawerTitle>
                <Badge
                  className="h-5 border-primary/20 bg-primary/8 px-2 font-medium text-[10px] text-primary"
                  variant="outline"
                >
                  生成方案
                </Badge>
              </div>
              <div className="mt-1 hidden items-center gap-2 text-[11px] text-muted-foreground sm:flex">
                <ShieldCheck className="size-3.5 text-primary" />
                应用前可预览并校验全部步骤
              </div>
            </div>
            <div className="ml-auto flex w-full items-center justify-end gap-2 sm:w-auto sm:pl-2">
              <Button className="h-8 px-3 text-xs" onClick={() => onOpenChange(false)} variant="outline">
                {busy ? "关闭" : "取消"}
              </Button>
              <Button
                className="h-8 px-3 text-xs shadow-sm"
                disabled={busy || !goal.trim()}
                onClick={async () => {
                  await onGenerate(goal.trim(), { requireCleanup });
                }}
              >
                {busy ? <Loader2 className="animate-spin" /> : <Sparkles />}
                {busy ? "正在生成" : "生成编排方案"}
              </Button>
            </div>
          </div>
          <div className="absolute inset-y-0 left-0 z-10 flex w-3 items-center justify-center">
            <DrawerHandle
              aria-label="拖动关闭抽屉"
              className="h-12! w-1.5! cursor-ew-resize touch-none rounded-full bg-border!"
            />
          </div>
        </DrawerHeader>
        <div className="select-text! min-h-0 space-y-5 overflow-y-auto px-5 py-5 sm:px-6 sm:py-6">
          <div className="rounded-lg border border-primary/15 bg-primary/5 px-3.5 py-3 text-muted-foreground text-xs">
            AI 只会在已选接口范围内推测执行路径，并为前后步骤补充参数依赖；应用前不会修改当前场景。
          </div>
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-sm">已选接口</div>
                <div className="mt-1 text-muted-foreground text-xs">{selectedEndpoints.length} 个接口作为分析范围</div>
              </div>
              <Badge variant="secondary">范围锁定</Badge>
            </div>
            <div className="space-y-1.5 rounded-lg border bg-card p-2.5">
              {selectedEndpoints.length ? (
                selectedEndpoints.map((endpoint) => (
                  <div className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs" key={endpoint.id}>
                    <Badge
                      className={cn("h-5 w-12 justify-center font-mono text-[10px]", methodTone[endpoint.method])}
                      variant="outline"
                    >
                      {endpoint.method}
                    </Badge>
                    <span className="min-w-0 flex-1 truncate font-medium">{endpoint.summary || endpoint.path}</span>
                    <span className="max-w-[45%] truncate font-mono text-[10px] text-muted-foreground">
                      {endpoint.path}
                    </span>
                  </div>
                ))
              ) : (
                <div className="px-2 py-3 text-muted-foreground text-xs">
                  未选择接口时，将按业务目标选择最多 12 个候选接口。
                </div>
              )}
            </div>
          </div>
          <div className="space-y-2.5">
            <div className="flex items-center justify-between gap-3">
              <label className="font-semibold text-sm" htmlFor="ai-scenario-goal">
                业务目标
              </label>
              <span className="text-[11px] text-muted-foreground">AI 仅使用已导入的接口资产</span>
            </div>
            <Textarea
              className="min-h-36 resize-none bg-card px-3.5 py-3 leading-6 shadow-xs placeholder:leading-6 sm:min-h-40"
              id="ai-scenario-goal"
              onChange={(event) => setGoal(event.target.value)}
              placeholder="例如：用户登录后创建订单，提取订单 ID，再查询并验证订单状态为待支付"
              rows={5}
              value={goal}
            />
          </div>
          <div className="flex items-center justify-between rounded-lg border bg-card px-3.5 py-3">
            <div>
              <div className="font-medium text-sm">生成清理步骤</div>
              <div className="mt-1 text-muted-foreground text-xs">若存在创建/写入操作，优先补充可逆的 cleanup</div>
            </div>
            <Switch checked={requireCleanup} onCheckedChange={setRequireCleanup} />
          </div>
          {lifecycleStatus === "generating" ? (
            <div className="flex items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3.5 py-3 text-sky-800 text-xs dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-200">
              <Loader2 className="size-3.5 animate-spin" /> 正在分析接口依赖并编译方案…
            </div>
          ) : null}
        </div>
      </DrawerContent>
    </Drawer>
  );
}

function runStatusLabel(status: string) {
  return (
    {
      queued: "排队中",
      running: "运行中",
      passed: "已通过",
      observed: "已通过",
      failed: "失败",
      cancelled: "已取消",
      interrupted: "已中断",
    }[status] ?? "已启动"
  );
}

function isFailedRunStatus(status: string) {
  return ["failed", "cancelled", "interrupted"].includes(status);
}

function NavButton({
  active,
  count,
  icon: Icon,
  label,
  onClick,
}: {
  active: boolean;
  count?: number;
  icon: typeof GitBranch;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className={cn(
        "relative flex items-center gap-1.5 text-muted-foreground text-xs",
        active && "font-medium text-primary after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-primary",
      )}
      onClick={onClick}
      type="button"
    >
      <Icon className="size-3.5" />
      {label}
      {count !== undefined ? <span className="rounded-full bg-muted px-1.5 text-[10px]">{count}</span> : null}
    </button>
  );
}

function VariablesPanel({
  variables,
  onChange,
}: {
  variables: Record<string, unknown>;
  onChange: (variables: Record<string, unknown>) => void;
}) {
  const entries = Object.entries(variables);
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-lg">场景变量</h2>
            <p className="mt-1 text-muted-foreground text-sm">
              维护跨步骤复用的固定数据，接口响应输出不需要在这里重复声明。
            </p>
          </div>
          <Button onClick={() => onChange({ ...variables, [`variable${entries.length + 1}`]: "" })} size="sm">
            <Plus />
            添加变量
          </Button>
        </div>
        <div className="mt-5 overflow-hidden rounded-xl border">
          {entries.length === 0 ? (
            <div className="p-10 text-center text-muted-foreground text-sm">暂无场景变量</div>
          ) : (
            entries.map(([name, value]) => (
              <div className="grid grid-cols-[220px_1fr_40px] gap-3 border-b p-3 last:border-b-0" key={name}>
                <Input
                  onBlur={(event) => {
                    const nextName = event.target.value.trim();
                    if (!nextName || nextName === name) return;
                    const next = { ...variables };
                    delete next[name];
                    next[nextName] = value;
                    onChange(next);
                  }}
                  defaultValue={name}
                />
                <Input
                  onChange={(event) => onChange({ ...variables, [name]: parseVariable(event.target.value) })}
                  value={String(value ?? "")}
                />
                <Button
                  onClick={() => {
                    const next = { ...variables };
                    delete next[name];
                    onChange(next);
                  }}
                  size="icon-sm"
                  variant="ghost"
                >
                  <Trash2 />
                </Button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function parseVariable(value: string) {
  if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value);
  if (value === "true") return true;
  if (value === "false") return false;
  return value;
}
