"use client";

import { useState } from "react";

import Link from "next/link";

import {
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  Braces,
  CheckCircle2,
  Clock3,
  GitBranch,
  LayoutDashboard,
  ListTree,
  Loader2,
  PanelRightClose,
  PanelRightOpen,
  Play,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  Trash2,
  Variable,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { ApiAutomationEndpoint, ApiAutomationScenarioStep, ApiScenarioAiPlan } from "@/lib/api-client";
import { cn } from "@/lib/utils";

import { ApiScenarioAssetPicker } from "./api-scenario-asset-picker";
import { ApiScenarioCanvas } from "./api-scenario-canvas";
import { ApiScenarioRunDrawer } from "./api-scenario-run-drawer";
import { ApiScenarioStepConfig } from "./api-scenario-step-config";
import { ApiScenarioVersionPanel } from "./api-scenario-version-panel";
import { useApiScenarioEditor } from "./use-api-scenario-editor";

type ApiScenarioEditorProps = { projectId: string; scenarioId?: string };
type EditorView = "orchestration" | "variables" | "versions";
type OrchestrationMode = "canvas" | "list";

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
  const [orchestrationMode, setOrchestrationMode] = useState<OrchestrationMode>("canvas");
  const [configPanelOpen, setConfigPanelOpen] = useState(false);
  const [assetPickerOpen, setAssetPickerOpen] = useState(false);
  const [aiDialogOpen, setAiDialogOpen] = useState(false);
  const activeIndex = editor.draft.steps.findIndex((step) => step.id === editor.activeStepId);
  const precedingSteps = activeIndex < 0 ? [] : editor.draft.steps.slice(0, activeIndex);

  if (editor.loading)
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
                className={
                  editor.scenario?.status === "ready"
                    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200"
                    : "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-200"
                }
                variant="secondary"
              >
                {editor.scenario?.status === "ready" ? `已发布 v${editor.scenario.revision}` : "草稿"}
              </Badge>
              {editor.scenario?.asset_changes.length ? (
                <span className="flex shrink-0 items-center gap-1 whitespace-nowrap text-[11px] text-amber-700 dark:text-amber-300">
                  <AlertTriangle className="size-3" />
                  {editor.scenario.asset_changes.length} 项接口资产变更待确认
                </span>
              ) : editor.dirty ? (
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
          <Button onClick={() => setAiDialogOpen(true)} size="sm" variant="outline">
            <Sparkles />
            AI 编排
          </Button>
          <Select onValueChange={editor.actions.setSelectedEnvironmentId} value={editor.selectedEnvironmentId}>
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
          <Button disabled={editor.busy} onClick={() => void editor.actions.saveScenario()} size="sm" variant="outline">
            <Save />
            保存
          </Button>
          <Button
            disabled={!editor.scenario || editor.busy}
            onClick={() => void editor.actions.validateScenario()}
            size="sm"
            variant="outline"
          >
            <ShieldCheck />
            检查
          </Button>
          <Button
            disabled={!editor.scenario || editor.busy}
            onClick={() => void editor.actions.publishScenario()}
            size="sm"
            variant="outline"
          >
            <GitBranch />
            发布
          </Button>
          {editor.scenario?.status === "ready" ? (
            <Button disabled={editor.busy} onClick={() => void editor.actions.executeScenario("published")} size="sm">
              <Play />
              运行场景
            </Button>
          ) : (
            <Button
              disabled={!editor.scenario || editor.busy}
              onClick={() => void editor.actions.executeScenario("draft")}
              size="sm"
            >
              <Play />
              运行当前草稿
            </Button>
          )}
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
                <div className="text-[10px] text-muted-foreground">
                  {orchestrationMode === "canvas" ? "以依赖关系查看场景" : "按执行顺序查看场景"}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {orchestrationMode === "canvas" ? (
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
              ) : null}
              <div className="flex items-center rounded-lg border bg-muted/25 p-0.5">
                <Button
                  aria-label="画布视图"
                  className="h-8 gap-1.5 px-2.5 text-xs"
                  onClick={() => setOrchestrationMode("canvas")}
                  size="sm"
                  variant={orchestrationMode === "canvas" ? "secondary" : "ghost"}
                >
                  <LayoutDashboard className="size-3.5" />
                  画布
                </Button>
                <Button
                  aria-label="列表视图"
                  className="h-8 gap-1.5 px-2.5 text-xs"
                  onClick={() => setOrchestrationMode("list")}
                  size="sm"
                  variant={orchestrationMode === "list" ? "secondary" : "ghost"}
                >
                  <ListTree className="size-3.5" />
                  列表
                </Button>
              </div>
            </div>
          </div>
          {orchestrationMode === "canvas" ? (
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
                onOpenAssetPicker={() => setAssetPickerOpen(true)}
                onSelectStep={(stepId) => {
                  editor.actions.setActiveStepId(stepId);
                  setConfigPanelOpen(true);
                }}
                steps={editor.draft.steps}
              />
              {configPanelOpen ? (
                <div className="min-h-0 min-w-0 border-l">
                  <ApiScenarioStepConfig
                    activeStep={editor.activeStep}
                    endpoints={editor.endpoints}
                    environment={editor.selectedEnvironment}
                    onUpdateStep={editor.actions.updateStep}
                    precedingSteps={precedingSteps}
                    scenarioVariables={editor.draft.variables}
                  />
                </div>
              ) : null}
            </div>
          ) : (
            <div className="grid min-h-0 flex-1 grid-cols-[minmax(330px,390px)_minmax(0,1fr)] overflow-hidden">
              <aside className="flex min-h-0 flex-col border-r bg-[linear-gradient(180deg,color-mix(in_srgb,var(--muted),white_72%),color-mix(in_srgb,var(--background),white_35%))] dark:bg-[linear-gradient(180deg,color-mix(in_srgb,var(--muted),black_8%),var(--background))]">
                <div className="flex h-[70px] items-center justify-between border-b px-4">
                  <div>
                    <h2 className="font-semibold text-sm">执行链路</h2>
                  </div>
                  <div className="flex items-center gap-2">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          className="border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100 dark:border-amber-500/35 dark:bg-amber-500/15 dark:text-amber-200 dark:hover:bg-amber-500/25"
                          size="sm"
                          variant="outline"
                        >
                          <GitBranch />
                          辅助步骤
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-60">
                        <DropdownMenuLabel>增强线性编排</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <UtilityMenuItem
                          icon={Variable}
                          label="数据赋值"
                          onClick={() => editor.actions.addUtilityStep("assign")}
                        />
                        <UtilityMenuItem
                          icon={GitBranch}
                          label="条件判断"
                          onClick={() => editor.actions.addUtilityStep("condition")}
                        />
                        <UtilityMenuItem
                          icon={Clock3}
                          label="固定等待"
                          onClick={() => editor.actions.addUtilityStep("wait")}
                        />
                        <UtilityMenuItem
                          icon={RefreshCw}
                          label="轮询等待"
                          onClick={() => editor.actions.addUtilityStep("poll")}
                        />
                      </DropdownMenuContent>
                    </DropdownMenu>
                    <Button onClick={() => setAssetPickerOpen(true)} size="sm">
                      <Plus />
                      从接口资产添加
                    </Button>
                  </div>
                </div>
                <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
                  {editor.draft.steps.length === 0 ? (
                    <button
                      className="grid min-h-52 w-full place-items-center rounded-xl border border-dashed bg-card/60 p-6 text-center"
                      onClick={() => setAssetPickerOpen(true)}
                      type="button"
                    >
                      <div>
                        <Plus className="mx-auto size-7 text-primary" />
                        <div className="mt-3 font-medium text-sm">添加第一个接口步骤</div>
                        <p className="mt-2 text-muted-foreground text-xs leading-5">
                          从接口资产中选择登录、创建、查询等接口，组成业务链路。
                        </p>
                      </div>
                    </button>
                  ) : (
                    editor.draft.steps.map((step, index) => (
                      <StepCard
                        endpoint={editor.endpoints.find((endpoint) => endpoint.id === step.endpoint_id)}
                        index={index}
                        isActive={editor.activeStepId === step.id}
                        key={step.id}
                        onMove={(offset) => {
                          const target = editor.draft.steps[index + offset];
                          if (target) editor.actions.reorderSteps(step.id, target.id);
                        }}
                        onRemove={() => editor.actions.removeStep(step.id)}
                        onSelect={() => editor.actions.setActiveStepId(step.id)}
                        step={step}
                      />
                    ))
                  )}
                </div>
              </aside>
              <ApiScenarioStepConfig
                activeStep={editor.activeStep}
                endpoints={editor.endpoints}
                environment={editor.selectedEnvironment}
                onUpdateStep={editor.actions.updateStep}
                precedingSteps={precedingSteps}
                scenarioVariables={editor.draft.variables}
              />
            </div>
          )}
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
      {editor.validation ? (
        <div className="grid gap-2 border-t bg-muted/20 p-3 md:grid-cols-2">
          {editor.validation.errors.length ? (
            <IssueBox items={editor.validation.errors} title="检查错误" tone="error" />
          ) : (
            <IssueBox items={["场景检查通过"]} title="检查结果" tone="success" />
          )}
          {editor.validation.warnings.length ? (
            <IssueBox items={editor.validation.warnings} title="检查提醒" tone="warning" />
          ) : null}
        </div>
      ) : null}
      {editor.latestRunId ? (
        <footer className="flex h-11 items-center justify-between bg-[linear-gradient(90deg,#172a3d,#244b66)] px-4 text-[11px] text-slate-200">
          <div className="flex items-center gap-3">
            <span className="size-2 rounded-full bg-emerald-400 shadow-[0_0_0_4px_rgba(52,211,153,.12)]" />
            <span>{`运行 ${editor.latestRunId} · ${runStatusLabel(editor.latestRunStatus)}`}</span>
          </div>
          <button
            className="text-sky-200 transition-colors hover:text-white"
            onClick={() => editor.actions.setRunDrawerOpen(true)}
            type="button"
          >
            {editor.scenarioRunResult
              ? `${editor.scenarioRunResult.steps.filter((step) => step.status === "passed").length}/${editor.scenarioRunResult.steps.length} 步通过 · ${Math.round(editor.scenarioRunResult.duration_ms)} ms · 展开结果`
              : "查看运行进度"}
          </button>
        </footer>
      ) : null}
      <ApiScenarioAssetPicker
        endpoints={editor.endpoints}
        onConfirm={editor.actions.addEndpointSteps}
        onOpenChange={setAssetPickerOpen}
        open={assetPickerOpen}
      />
      <AiOrchestrationDialog
        busy={editor.aiBusy}
        onApply={() => void editor.actions.applyAiPlan()}
        onDiscard={editor.actions.discardAiPlan}
        onGenerate={editor.actions.generateAiPlan}
        onOpenChange={setAiDialogOpen}
        open={aiDialogOpen}
        plan={editor.aiPlan}
      />
      <ApiScenarioRunDrawer
        onJumpToStep={(stepId) => {
          setView("orchestration");
          editor.actions.setActiveStepId(stepId);
        }}
        onOpenChange={editor.actions.setRunDrawerOpen}
        open={editor.runDrawerOpen}
        result={editor.scenarioRunResult}
        runId={editor.latestRunId}
        status={editor.latestRunStatus}
      />
    </section>
  );
}

function AiOrchestrationDialog({
  busy,
  onApply,
  onDiscard,
  onGenerate,
  onOpenChange,
  open,
  plan,
}: {
  busy: boolean;
  onApply: () => void;
  onDiscard: () => void;
  onGenerate: (goal: string, allowWrite: boolean, maxSteps: number) => Promise<ApiScenarioAiPlan | null>;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  plan: ApiScenarioAiPlan | null;
}) {
  const [goal, setGoal] = useState("");
  const [allowWrite, setAllowWrite] = useState(false);
  const [maxSteps, setMaxSteps] = useState(8);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="top-0 left-0 h-dvh max-h-dvh w-screen max-w-none translate-x-0 translate-y-0 auto-rows-max content-start overflow-y-auto rounded-none bg-white sm:top-1/2 sm:left-1/2 sm:h-auto sm:max-h-[85vh] sm:w-full sm:max-w-3xl sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-xl dark:bg-zinc-950">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="size-4 text-primary" />
            AI 编排接口场景
          </DialogTitle>
          <DialogDescription>AI 只生成可审阅草稿，应用后仍需检查和发布。</DialogDescription>
        </DialogHeader>
        {!plan ? (
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="font-medium text-sm" htmlFor="ai-scenario-goal">
                业务目标
              </label>
              <Textarea
                id="ai-scenario-goal"
                onChange={(event) => setGoal(event.target.value)}
                placeholder="例如：登录后创建订单，提取订单 ID，并验证订单状态"
                rows={6}
                value={goal}
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-2 text-sm" htmlFor="ai-scenario-max-steps">
                <span className="font-medium">最大步骤数</span>
                <Input
                  id="ai-scenario-max-steps"
                  max={100}
                  min={1}
                  onChange={(event) => setMaxSteps(Number(event.target.value) || 1)}
                  type="number"
                  value={maxSteps}
                />
              </label>
              <label
                className="flex items-center gap-2 self-end rounded-md border px-3 py-2.5 text-sm"
                htmlFor="ai-scenario-allow-write"
              >
                <input
                  id="ai-scenario-allow-write"
                  checked={allowWrite}
                  className="size-4 accent-primary"
                  onChange={(event) => setAllowWrite(event.target.checked)}
                  type="checkbox"
                />
                允许 POST、PUT、PATCH、DELETE 写操作
              </label>
            </div>
            <div className="flex justify-end">
              <Button
                disabled={busy || !goal.trim()}
                onClick={() => void onGenerate(goal.trim(), allowWrite, maxSteps)}
              >
                {busy ? <Loader2 className="animate-spin" /> : <Sparkles />}
                生成编排草稿
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/25 p-3">
              <div>
                <div className="font-semibold text-sm">{plan.scenario_name}</div>
                <div className="mt-1 text-muted-foreground text-xs">
                  {plan.nodes.length} 个步骤 · 置信度 {Math.round(plan.confidence * 100)}%
                </div>
              </div>
              <Badge variant={plan.validation.valid ? "secondary" : "destructive"}>
                {plan.validation.valid ? "校验通过" : `${plan.validation.errors.length} 个错误`}
              </Badge>
            </div>
            <div className="space-y-2">
              {plan.nodes.map((node, index) => (
                <div className="flex items-center gap-3 rounded-md border p-3" key={node.id}>
                  <span className="grid size-6 shrink-0 place-items-center rounded bg-muted text-xs">{index + 1}</span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-sm">{node.name || node.id}</div>
                    <div className="truncate text-muted-foreground text-xs">
                      {node.type} · {node.endpoint_id ?? "辅助节点"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            {[...plan.validation.errors, ...plan.validation.warnings].length ? (
              <div className="space-y-1 rounded-md border border-amber-300/60 bg-amber-50/60 p-3 text-amber-900 text-xs dark:bg-amber-500/10 dark:text-amber-200">
                {[...plan.validation.errors, ...plan.validation.warnings].map((item) => (
                  <div key={item}>{item}</div>
                ))}
              </div>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button disabled={busy} onClick={onDiscard} variant="outline">
                放弃计划
              </Button>
              <Button disabled={busy || !plan.validation.valid} onClick={onApply}>
                {busy ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}
                应用到草稿
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function runStatusLabel(status: string) {
  return (
    {
      queued: "排队中",
      running: "运行中",
      passed: "已通过",
      failed: "失败",
      cancelled: "已取消",
      interrupted: "已中断",
    }[status] ?? "已启动"
  );
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

function StepCard({
  step,
  endpoint,
  index,
  isActive,
  onSelect,
  onMove,
  onRemove,
}: {
  step: ApiAutomationScenarioStep;
  endpoint?: ApiAutomationEndpoint;
  index: number;
  isActive: boolean;
  onSelect: () => void;
  onMove: (offset: number) => void;
  onRemove: () => void;
}) {
  return (
    <article
      className={cn(
        "group relative grid grid-cols-[28px_1fr_auto] gap-2 rounded-xl border bg-card/90 p-3 shadow-sm transition-all",
        isActive &&
          "border-primary/60 bg-card shadow-[0_10px_28px_color-mix(in_srgb,var(--primary),transparent_84%)] before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-full before:bg-primary",
      )}
    >
      <button
        className="grid size-6 place-items-center rounded-md bg-muted font-semibold text-[11px] text-muted-foreground"
        onClick={onSelect}
        type="button"
      >
        {index + 1}
      </button>
      <button className="min-w-0 text-left" onClick={onSelect} type="button">
        <div className="flex items-center gap-2">
          <Badge
            className={cn("h-5 min-w-11 justify-center font-mono text-[9px]", methodTone[endpoint?.method ?? ""])}
            variant="outline"
          >
            {endpoint?.method ?? step.step_type.toUpperCase()}
          </Badge>
          <span className="truncate font-medium text-sm">{step.name}</span>
        </div>
        <div className="mt-1 truncate font-mono text-[10px] text-muted-foreground">{endpoint?.path ?? "辅助步骤"}</div>
        <div className="mt-2 flex flex-wrap gap-1">
          {step.bindings.length ? <MiniTag icon={Variable} text={`引用 ${step.bindings.length}`} /> : null}
          {step.extractors.length ? <MiniTag icon={Braces} text={`输出 ${step.extractors.length}`} /> : null}
          {step.assertions.length ? (
            <MiniTag icon={CheckCircle2} text={`${step.assertions.length} 个断言`} success />
          ) : null}
        </div>
      </button>
      <div className="flex flex-col opacity-20 transition-opacity group-hover:opacity-100">
        <Button disabled={index === 0} onClick={() => onMove(-1)} size="icon-xs" variant="ghost">
          <ArrowUp />
        </Button>
        <Button onClick={() => onMove(1)} size="icon-xs" variant="ghost">
          <ArrowDown />
        </Button>
        <Button onClick={onRemove} size="icon-xs" variant="ghost">
          <Trash2 />
        </Button>
      </div>
    </article>
  );
}

function MiniTag({ icon: Icon, text, success }: { icon: typeof Variable; text: string; success?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded bg-primary/8 px-1.5 py-0.5 text-[9px] text-primary",
        success && "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200",
      )}
    >
      <Icon className="size-2.5" />
      {text}
    </span>
  );
}

function UtilityMenuItem({
  icon: Icon,
  label,
  onClick,
}: {
  icon: typeof Variable;
  label: string;
  onClick: () => void;
}) {
  return (
    <DropdownMenuItem className="gap-3 py-2.5" onClick={onClick}>
      <span className="grid size-7 place-items-center rounded-lg bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-200">
        <Icon className="size-3.5" />
      </span>
      <span>{label}</span>
    </DropdownMenuItem>
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

function IssueBox({ title, items, tone }: { title: string; items: string[]; tone: "error" | "warning" | "success" }) {
  return (
    <div
      className={cn(
        "rounded-lg border p-3 text-xs",
        tone === "error" && "border-destructive/30 bg-destructive/5 text-destructive",
        tone === "warning" &&
          "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-500/35 dark:bg-amber-500/15 dark:text-amber-200",
        tone === "success" &&
          "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-500/35 dark:bg-emerald-500/15 dark:text-emerald-200",
      )}
    >
      <div className="font-semibold">{title}</div>
      <ul className="mt-2 space-y-1">
        {items.map((item) => (
          <li key={item}>• {item}</li>
        ))}
      </ul>
    </div>
  );
}
function parseVariable(value: string) {
  if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value);
  if (value === "true") return true;
  if (value === "false") return false;
  return value;
}
