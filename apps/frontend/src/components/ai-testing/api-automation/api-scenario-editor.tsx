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
  CircleDot,
  Clock3,
  GitBranch,
  GripVertical,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Save,
  Settings2,
  ShieldCheck,
  Trash2,
  Variable,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import type { ApiAutomationEndpoint, ApiAutomationScenarioStep } from "@/lib/api-client";
import { cn } from "@/lib/utils";

import { ApiScenarioAssetPicker } from "./api-scenario-asset-picker";
import { ApiScenarioRunDrawer } from "./api-scenario-run-drawer";
import { ApiScenarioStepConfig } from "./api-scenario-step-config";
import { ApiScenarioVersionPanel } from "./api-scenario-version-panel";
import { useApiScenarioEditor } from "./use-api-scenario-editor";

type ApiScenarioEditorProps = { projectId: string; scenarioId?: string };
type EditorView = "orchestration" | "variables" | "versions" | "settings";

const methodTone: Record<string, string> = {
  GET: "border-blue-200 bg-blue-50 text-blue-700",
  POST: "border-emerald-200 bg-emerald-50 text-emerald-700",
  PUT: "border-amber-200 bg-amber-50 text-amber-700",
  PATCH: "border-violet-200 bg-violet-50 text-violet-700",
  DELETE: "border-red-200 bg-red-50 text-red-700",
};

export function ApiScenarioEditor({ projectId, scenarioId }: ApiScenarioEditorProps) {
  const editor = useApiScenarioEditor(projectId, scenarioId);
  const [view, setView] = useState<EditorView>("orchestration");
  const [assetPickerOpen, setAssetPickerOpen] = useState(false);
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
    <section className="overflow-hidden rounded-2xl border border-border/90 bg-card shadow-[0_24px_70px_color-mix(in_srgb,var(--primary),transparent_88%)]">
      <header className="flex min-h-[70px] flex-wrap items-center justify-between gap-3 border-b bg-card/95 px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <Button asChild size="icon-sm" variant="outline">
            <Link href={`/projects/${projectId}/automation/api?tab=scenarios`}>
              <ArrowLeft />
            </Link>
          </Button>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Input
                className="h-8 min-w-52 border-transparent bg-transparent px-1 font-semibold text-sm shadow-none hover:border-border focus-visible:border-border"
                onChange={(event) => editor.actions.updateScenarioMeta({ name: event.target.value })}
                placeholder="请输入场景名称"
                value={editor.draft.name}
              />
              <Badge
                className={
                  editor.scenario?.status === "ready" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                }
                variant="secondary"
              >
                {editor.scenario?.status === "ready" ? `已发布 v${editor.scenario.revision}` : "草稿"}
              </Badge>
            </div>
            <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
              <span>{editor.draft.steps.length} 个步骤</span>
              <CircleDot className="size-2" />
              {editor.scenario?.asset_changes.length ? (
                <span className="flex items-center gap-1 text-amber-700">
                  <AlertTriangle className="size-3" />
                  {editor.scenario.asset_changes.length} 项接口资产变更待确认
                </span>
              ) : (
                <span>{editor.dirty ? "存在未保存修改" : "草稿已同步"}</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
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

      <nav className="flex h-11 items-stretch gap-6 border-b bg-muted/15 px-5">
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
        <NavButton active={view === "settings"} icon={Settings2} label="场景设置" onClick={() => setView("settings")} />
      </nav>

      {view === "orchestration" ? (
        <div className="grid min-h-[620px] grid-cols-[minmax(330px,390px)_minmax(0,1fr)]">
          <aside className="border-r bg-[linear-gradient(180deg,color-mix(in_srgb,var(--muted),white_72%),color-mix(in_srgb,var(--background),white_35%))]">
            <div className="flex h-[70px] items-center justify-between border-b px-4">
              <div>
                <h2 className="font-semibold text-sm">执行链路</h2>
                <p className="mt-1 text-[11px] text-muted-foreground">从上到下依次执行</p>
              </div>
              <div className="flex items-center gap-2">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      className="border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100"
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
            <div className="max-h-[550px] space-y-2 overflow-y-auto p-3">
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
      {view === "settings" ? (
        <SettingsPanel
          description={editor.draft.description}
          onChange={(description) => editor.actions.updateScenarioMeta({ description })}
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
      <footer className="flex h-11 items-center justify-between bg-[linear-gradient(90deg,#172a3d,#244b66)] px-4 text-[11px] text-slate-200">
        <div className="flex items-center gap-3">
          <span
            className={cn(
              "size-2 rounded-full",
              editor.latestRunId ? "bg-emerald-400 shadow-[0_0_0_4px_rgba(52,211,153,.12)]" : "bg-slate-500",
            )}
          />
          <span>
            {editor.latestRunId
              ? `运行 ${editor.latestRunId} · ${runStatusLabel(editor.latestRunStatus)}`
              : "尚未运行当前场景"}
          </span>
        </div>
        <button
          className="text-sky-200 transition-colors hover:text-white disabled:cursor-default disabled:text-slate-400"
          disabled={!editor.latestRunId}
          onClick={() => editor.actions.setRunDrawerOpen(true)}
          type="button"
        >
          {editor.scenarioRunResult
            ? `${editor.scenarioRunResult.steps.filter((step) => step.status === "passed").length}/${editor.scenarioRunResult.steps.length} 步通过 · ${Math.round(editor.scenarioRunResult.duration_ms)} ms · 展开结果`
            : editor.latestRunId
              ? "查看运行进度"
              : "运行结果将在此处展开"}
        </button>
      </footer>
      <ApiScenarioAssetPicker
        endpoints={editor.endpoints}
        onConfirm={editor.actions.addEndpointSteps}
        onOpenChange={setAssetPickerOpen}
        open={assetPickerOpen}
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
        <Button aria-label="拖动步骤" size="icon-xs" variant="ghost">
          <GripVertical />
        </Button>
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
        success && "bg-emerald-50 text-emerald-700",
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
      <span className="grid size-7 place-items-center rounded-lg bg-amber-50 text-amber-700">
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
    <div className="min-h-[620px] p-6">
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

function SettingsPanel({ description, onChange }: { description: string; onChange: (description: string) => void }) {
  return (
    <div className="min-h-[620px] p-6">
      <div className="mx-auto max-w-3xl">
        <h2 className="font-semibold text-lg">场景设置</h2>
        <p className="mt-1 text-muted-foreground text-sm">低频元数据集中在这里，不占用编排主工作区。</p>
        <label className="mt-6 block" htmlFor="scenario-description">
          <span className="mb-2 block font-medium text-sm">场景描述</span>
          <Textarea
            className="min-h-36"
            id="scenario-description"
            onChange={(event) => onChange(event.target.value)}
            placeholder="描述该业务链路覆盖的目标、前置条件和注意事项"
            value={description}
          />
        </label>
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
        tone === "warning" && "border-amber-200 bg-amber-50 text-amber-800",
        tone === "success" && "border-emerald-200 bg-emerald-50 text-emerald-800",
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
