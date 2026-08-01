"use client";

import { useEffect, useState } from "react";

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
import { Drawer, DrawerContent, DrawerFooter, DrawerHandle, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { OneClipboard } from "@/components/ui/one-clipboard";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type {
  ApiAutomationEndpoint,
  ApiAutomationScenarioStep,
  ApiScenarioAiPlan,
  ApiScenarioAiPlanAccepted,
} from "@/lib/api-client";
import { cn } from "@/lib/utils";

import { buildAiPlanPresentation } from "./api-scenario-ai-plan-view.mjs";
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
  const [aiDrawerOpen, setAiDrawerOpen] = useState(false);
  const [aiSourceEndpointIds, setAiSourceEndpointIds] = useState<string[]>([]);

  useEffect(() => {
    if (editor.aiPlan) setAiDrawerOpen(true);
  }, [editor.aiPlan]);
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
          <Button
            onClick={() => {
              setAiSourceEndpointIds([]);
              setAiDrawerOpen(true);
            }}
            size="sm"
            variant="outline"
          >
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
            onClick={() => void editor.actions.executeScenario()}
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
        onAiOrchestration={(endpointIds) => {
          setAiSourceEndpointIds(endpointIds);
          setAiDrawerOpen(true);
        }}
        onConfirm={editor.actions.addEndpointSteps}
        onOpenChange={setAssetPickerOpen}
        open={assetPickerOpen}
      />
      <AiOrchestrationDrawer
        busy={editor.aiBusy}
        endpoints={editor.endpoints}
        lifecycleStatus={editor.aiLifecycleStatus}
        selectedEndpointIds={aiSourceEndpointIds}
        onApply={() => void editor.actions.applyAiPlan()}
        onDiscard={editor.actions.discardAiPlan}
        onGenerate={(goal, options) => editor.actions.generateAiPlan(goal, aiSourceEndpointIds, options)}
        onOpenChange={setAiDrawerOpen}
        open={aiDrawerOpen}
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

function AiOrchestrationDrawer({
  busy,
  endpoints,
  lifecycleStatus,
  onApply,
  onDiscard,
  onGenerate,
  onOpenChange,
  open,
  plan,
  selectedEndpointIds,
}: {
  busy: boolean;
  endpoints: ApiAutomationEndpoint[];
  lifecycleStatus: "generating" | "completed" | "failed" | "expired" | null;
  onApply: () => void;
  onDiscard: () => void;
  onGenerate: (goal: string, options: { requireCleanup: boolean }) => Promise<ApiScenarioAiPlanAccepted | null>;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  plan: ApiScenarioAiPlan | null;
  selectedEndpointIds: string[];
}) {
  const [goal, setGoal] = useState("");
  const [requireCleanup, setRequireCleanup] = useState(false);
  const selectedEndpoints = selectedEndpointIds
    .map((endpointId) => endpoints.find((endpoint) => endpoint.id === endpointId))
    .filter((endpoint): endpoint is ApiAutomationEndpoint => Boolean(endpoint));
  const presentation = plan ? buildAiPlanPresentation(plan, endpoints, goal) : null;

  return (
    <Drawer direction="right" handleOnly open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="grid h-full w-full grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden bg-background p-0 data-[vaul-drawer-direction=right]:w-[min(92vw,760px)] data-[vaul-drawer-direction=right]:sm:max-w-[760px]">
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
                  生成草稿
                </Badge>
              </div>
            </div>
            {plan ? (
              <div className="ml-auto flex w-full items-center justify-end gap-2 sm:w-auto sm:pl-2">
                <OneClipboard copiedLabel="计划已复制" label="复制计划" text={formatAiPlanForClipboard(plan)} />
                <Button className="h-7 px-2 text-xs" disabled={busy} onClick={onDiscard} variant="outline">
                  放弃计划
                </Button>
                <Button className="h-7 px-2.5 text-xs" disabled={busy || !plan.validation.valid} onClick={onApply}>
                  {busy ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}
                  覆盖当前草稿
                </Button>
              </div>
            ) : null}
          </div>
          <div className="absolute inset-y-0 left-0 z-10 flex w-3 items-center justify-center">
            <DrawerHandle
              aria-label="拖动关闭抽屉"
              className="h-12! w-1.5! cursor-ew-resize touch-none rounded-full bg-border!"
            />
          </div>
        </DrawerHeader>
        {!plan ? (
          <div className="select-text! min-h-0 space-y-5 overflow-y-auto px-5 py-5 sm:px-6 sm:py-6">
            <div className="rounded-lg border border-primary/15 bg-primary/5 px-3.5 py-3 text-muted-foreground text-xs">
              AI 只会在已选接口范围内推测执行路径，并为前后步骤补充参数依赖；应用前不会修改当前场景。
            </div>
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-sm">已选接口</div>
                  <div className="mt-1 text-muted-foreground text-xs">
                    {selectedEndpoints.length} 个接口作为分析范围
                  </div>
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
        ) : (
          <div className="select-text! min-h-0 space-y-4 overflow-y-auto bg-muted/10 px-5 py-5 sm:px-6">
            <div className="flex gap-2 rounded-lg border border-amber-300/60 bg-amber-50/60 p-3.5 text-amber-900 text-xs dark:bg-amber-500/10 dark:text-amber-200">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
              <span>应用后将使用 AI 编排结果完整替换当前草稿步骤，当前草稿中的步骤修改不会保留。</span>
            </div>
            <div data-testid="ai-plan-readable-preview">
              <section className="border-b bg-card px-5 py-5 sm:px-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="mb-2 flex items-center gap-2 font-medium text-[11px] text-muted-foreground uppercase">
                      <GitBranch className="size-3.5 text-primary" />
                      调用目标
                    </div>
                    <h3 className="font-semibold text-base leading-6">{presentation?.goal}</h3>
                    <p className="mt-1.5 text-muted-foreground text-xs leading-5">
                      将按下面的顺序执行 {plan.nodes.length} 个步骤。前一步的输出会在运行时自动传给依赖它的步骤。
                    </p>
                  </div>
                  <Badge
                    className={cn(
                      "h-6 shrink-0",
                      plan.validation.valid &&
                        "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/35 dark:bg-emerald-500/15 dark:text-emerald-200",
                    )}
                    variant={plan.validation.valid ? "outline" : "destructive"}
                  >
                    {plan.validation.valid ? (
                      <CheckCircle2 className="size-3.5" />
                    ) : (
                      <AlertTriangle className="size-3.5" />
                    )}
                    {plan.validation.valid ? "可以保存" : `${plan.validation.errors.length} 个问题待处理`}
                  </Badge>
                </div>
              </section>

              <section className="border-b px-5 py-5 sm:px-6">
                <div className="mb-3 flex items-end justify-between gap-3">
                  <div>
                    <h3 className="font-semibold text-sm">执行步骤</h3>
                    <p className="mt-1 text-muted-foreground text-xs">方法、路径和参数按实际请求归到对应步骤。</p>
                  </div>
                  <span className="shrink-0 text-[11px] text-muted-foreground">
                    置信度 {Math.round(plan.confidence * 100)}%
                  </span>
                </div>
                <div className="overflow-hidden rounded-lg border bg-card">
                  {presentation?.steps.map((step) => (
                    <details className="group border-b last:border-b-0" key={step.id}>
                      <summary className="flex cursor-pointer list-none items-start gap-3 px-4 py-3.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset">
                        <span className="grid size-7 shrink-0 place-items-center rounded-full border bg-background font-semibold text-[11px] text-primary">
                          {step.index}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h4 className="font-semibold text-sm">{step.name}</h4>
                            <Badge
                              className={cn("h-5 font-mono text-[10px]", methodTone[step.method])}
                              variant="outline"
                            >
                              {step.method}
                            </Badge>
                          </div>
                          <code className="mt-1.5 block break-all font-mono text-[11px] text-muted-foreground">
                            {step.path}
                          </code>
                          {step.purpose !== step.name ? (
                            <p className="mt-2 text-muted-foreground text-xs leading-5">作用：{step.purpose}</p>
                          ) : null}
                          {step.dependencies.map((dependency) => (
                            <div
                              className="mt-2 flex items-start gap-2 rounded-md border border-sky-200 bg-sky-50 px-2.5 py-2 text-sky-800 text-xs dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-200"
                              key={`${dependency.stepId}-${dependency.target}`}
                            >
                              <ArrowDown className="mt-0.5 size-3.5 shrink-0" />
                              <span>
                                接收步骤「{dependency.stepName}」输出的 {dependency.variable}，填入 {dependency.target}
                              </span>
                            </div>
                          ))}
                        </div>
                        <span className="shrink-0 pt-1 text-[11px] text-muted-foreground group-open:hidden">配置</span>
                        <span className="hidden shrink-0 pt-1 text-[11px] text-muted-foreground group-open:inline">
                          收起
                        </span>
                      </summary>
                      {step.parameters.length ? (
                        <div className="border-t bg-muted/10 px-4 py-3">
                          <div className="mb-2 font-medium text-[11px] text-muted-foreground">本步骤请求参数</div>
                          <div className="divide-y">
                            {step.parameters.map((parameter) => (
                              <div
                                className="grid gap-1.5 py-2 first:pt-0 last:pb-0 sm:grid-cols-[minmax(120px,0.7fr)_minmax(0,1.3fr)] sm:gap-4"
                                key={parameter.key}
                              >
                                <div className="min-w-0">
                                  <code className="break-all font-mono text-xs">{parameter.name}</code>
                                  <div className="mt-0.5 text-[10px] text-muted-foreground">{parameter.location}</div>
                                </div>
                                <div className="min-w-0">
                                  <code className="block whitespace-pre-wrap break-all font-mono text-xs leading-5">
                                    {parameter.value}
                                  </code>
                                  <div className="mt-0.5 text-[10px] text-muted-foreground">{parameter.source}</div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      <div className="border-t bg-muted/20 px-4 py-3">
                        <div className="mb-2 font-medium text-[11px] text-muted-foreground">AI 完整步骤配置</div>
                        <pre className="max-h-72 overflow-auto rounded-md border bg-background p-3 font-mono text-[11px] leading-5">
                          {JSON.stringify(step.rawNode, null, 2)}
                        </pre>
                      </div>
                    </details>
                  ))}
                </div>
              </section>

              {presentation?.commonParameters.length ? (
                <section className="border-b bg-card px-5 py-5 sm:px-6">
                  <div className="mb-3 flex items-center gap-2">
                    <Braces className="size-4 text-primary" />
                    <div>
                      <h3 className="font-semibold text-sm">公共请求配置</h3>
                      <p className="mt-1 text-muted-foreground text-xs">以下配置被多个步骤复用，只展示一次。</p>
                    </div>
                  </div>
                  <div className="divide-y border-y">
                    {presentation.commonParameters.map((parameter) => (
                      <div
                        className="grid gap-1.5 py-2.5 sm:grid-cols-[minmax(120px,0.7fr)_minmax(0,1.3fr)] sm:gap-4"
                        key={parameter.key}
                      >
                        <div>
                          <code className="break-all font-mono text-xs">{parameter.name}</code>
                          <div className="mt-0.5 text-[10px] text-muted-foreground">{parameter.location}</div>
                        </div>
                        <div className="min-w-0">
                          <code className="block whitespace-pre-wrap break-all font-mono text-xs leading-5">
                            {parameter.value}
                          </code>
                          <div className="mt-0.5 text-[10px] text-muted-foreground">
                            {parameter.source} · 用于 {parameter.usedBy.join("、")}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}

              {presentation?.actionItems.length ? (
                <section className="border-b px-5 py-5 sm:px-6">
                  <div className="mb-3 flex items-center gap-2">
                    <Variable className="size-4 text-amber-700 dark:text-amber-300" />
                    <div>
                      <h3 className="font-semibold text-sm">运行时输入</h3>
                      <p className="mt-1 text-muted-foreground text-xs">
                        这里直接说明要填什么，以及这个值会被用在哪里。
                      </p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    {presentation.actionItems.map((item) => (
                      <div
                        className="rounded-lg border border-amber-300/60 bg-amber-50/60 px-3.5 py-3 dark:bg-amber-500/10"
                        key={item.name}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="font-medium text-sm">{item.label}</div>
                          <Badge variant={item.value === "尚未填写" ? "outline" : "secondary"}>
                            {item.value === "尚未填写" ? "运行前填写" : "已有默认值"}
                          </Badge>
                        </div>
                        <code className="mt-2 block whitespace-pre-wrap break-all font-mono text-xs leading-5">
                          {item.value}
                        </code>
                        <p className="mt-1.5 text-muted-foreground text-xs leading-5">{item.description}</p>
                        <p className="mt-1 text-[10px] text-muted-foreground">填写位置：{item.targets.join("；")}</p>
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}

              <details className="group bg-card px-5 py-4 sm:px-6">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 font-medium text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  <span>技术详情：参数来源与编译诊断</span>
                  <span className="text-[11px] text-muted-foreground group-open:hidden">展开</span>
                  <span className="hidden text-[11px] text-muted-foreground group-open:inline">收起</span>
                </summary>
                <div className="mt-4 space-y-4 border-t pt-4">
                  <div className="space-y-2">
                    {plan.nodes.flatMap((node) =>
                      (node.bindings ?? []).map((binding) => (
                        <div
                          className="flex items-start gap-2 text-xs"
                          key={`${node.id}-${binding.target.location}-${binding.target.path}`}
                        >
                          <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">
                            {node.name || node.id} · {formatBindingTarget(binding.target)}
                          </span>
                          <span className="text-muted-foreground">←</span>
                          <span className="min-w-0 flex-1 text-muted-foreground">
                            {formatBindingSource(binding.source)}
                          </span>
                        </div>
                      )),
                    )}
                  </div>
                  {presentation?.diagnostics.length ? (
                    <div className="space-y-1.5 border-t pt-3 text-amber-800 text-xs dark:text-amber-200">
                      {presentation.diagnostics.map((item) => (
                        <div className="flex gap-2" key={item}>
                          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
                          <span>{item}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="border-t pt-3 text-muted-foreground text-xs">没有额外编译诊断。</div>
                  )}
                </div>
              </details>
            </div>
          </div>
        )}
        {!plan ? (
          <DrawerFooter className="mx-0 mb-0 min-h-16 items-center rounded-none border-t bg-background px-5 py-3 sm:justify-between sm:px-6">
            <div className="hidden items-center gap-2 text-[11px] text-muted-foreground sm:flex">
              <ShieldCheck className="size-3.5 text-primary" />
              应用前可预览并校验全部步骤
            </div>
            <div className="flex w-full gap-2 sm:w-auto">
              <Button className="flex-1 sm:flex-none" onClick={() => onOpenChange(false)} variant="outline">
                {busy ? "关闭" : "取消"}
              </Button>
              <Button
                className="flex-1 px-4 shadow-sm sm:flex-none"
                disabled={busy || !goal.trim()}
                onClick={async () => {
                  await onGenerate(goal.trim(), { requireCleanup });
                }}
              >
                {busy ? <Loader2 className="animate-spin" /> : <Sparkles />}
                {busy ? "正在生成" : "生成编排草稿"}
              </Button>
            </div>
          </DrawerFooter>
        ) : null}
      </DrawerContent>
    </Drawer>
  );
}

function formatAiPlanForClipboard(plan: ApiScenarioAiPlan) {
  return JSON.stringify(plan, null, 2);
}

function formatBindingSource(source: unknown) {
  if (!source || typeof source !== "object") return "未确定来源";
  const value = source as {
    type?: string;
    key?: string;
    name?: string;
    step_id?: string;
    variable?: string;
    generator?: string;
    value?: unknown;
  };
  if (value.type === "step_output") return `前序步骤 ${value.step_id ?? ""} 的输出`;
  if (value.type === "environment" || value.type === "secret") {
    return `${value.type === "secret" ? "密钥" : "运行环境"} · ${value.key ?? value.name ?? "变量"}`;
  }
  if (value.type === "scenario" || value.type === "user_input") {
    return `${value.type === "user_input" ? "用户输入" : "场景变量"} · ${value.name ?? value.variable ?? "变量"}`;
  }
  if (value.type === "literal") return `固定值 · ${String(value.value ?? "")}`;
  if (value.type === "generated") return `自动生成 · ${value.generator ?? "值"}`;
  return value.type ?? "未确定来源";
}

function formatBindingTarget(target: { location?: string; path?: string } | string) {
  if (typeof target === "string") return target;
  return `${target.location ?? "请求"}${target.path ?? ""}`;
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
        {[...new Set(items)].map((item) => (
          <li key={`${tone}-${item}`}>• {item}</li>
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
