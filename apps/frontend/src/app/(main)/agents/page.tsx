"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import dynamic from "next/dynamic";
import Link from "next/link";

import {
  BarChart3,
  Bot,
  Braces,
  ClipboardCheck,
  Database,
  ExternalLink,
  FileSearch,
  FileText,
  Gauge,
  Globe2,
  LayoutGrid,
  List,
  ListChecks,
  MonitorPlay,
  Network,
  RefreshCw,
  ScanText,
  X,
} from "lucide-react";

import { PageShell } from "@/components/ai-testing/page-shell";
import {
  buildOfficeAgents,
  type SiliconEmployee,
  tasksForEmployee,
} from "@/components/ai-testing/silicon-office/agent-roster";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type ApiTaskItem, apiRequest, formatDateTime } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectContextStore } from "@/stores/project-context-store";

const OfficeCanvas = dynamic(
  () => import("@/components/ai-testing/silicon-office/office-canvas").then((module) => module.SiliconOfficeCanvas),
  { ssr: false },
);

const POLL_INTERVAL_MS = 2_000;
const EMPLOYEE_POLL_INTERVAL_MS = 10_000;
const employeeIcons = {
  document_editor: FileText,
  requirement_standardization: ScanText,
  requirement_analysis: FileSearch,
  knowledge_query: Database,
  test_case_generation: ClipboardCheck,
  test_point_generation: ListChecks,
  api_test_generation: Braces,
  api_scenario_orchestration: Network,
  ui_test_generation: MonitorPlay,
  page_exploration: Globe2,
  performance_script_generation: Gauge,
  performance_report_analysis: BarChart3,
} as const;

export default function SiliconEmployeesPage() {
  const { currentProjectId, hasHydrated: projectHydrated, hydrate, scope } = useProjectContextStore();
  const { hasHydrated: authHydrated, hydrate: hydrateAuth, token } = useAuthStore();
  const [employees, setEmployees] = useState<SiliconEmployee[]>([]);
  const [tasks, setTasks] = useState<ApiTaskItem[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [viewMode, setViewMode] = useState<"cards" | "list">("cards");
  const [detailOpen, setDetailOpen] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [syncedAt, setSyncedAt] = useState<Date | null>(null);

  useEffect(() => hydrate(), [hydrate]);
  useEffect(() => hydrateAuth(), [hydrateAuth]);

  const loadEmployees = useCallback(async () => {
    const employeeResult = await apiRequest<SiliconEmployee[]>("/agents/employees");
    setEmployees(employeeResult);
    setSelectedId((current) =>
      employeeResult.some((employee) => employee.id === current) ? current : (employeeResult[0]?.id ?? ""),
    );
  }, []);

  const loadTasks = useCallback(async () => {
    const query = scope === "project" && currentProjectId ? `?project_id=${encodeURIComponent(currentProjectId)}` : "";
    const result = await apiRequest<ApiTaskItem[]>(`/tasks/running${query}`);
    setTasks(result);
    setSyncedAt(new Date());
  }, [currentProjectId, scope]);

  const loadWorkspace = useCallback(async () => {
    if (!authHydrated || !projectHydrated || !token) return;

    setLoading(true);
    try {
      await Promise.all([loadEmployees(), loadTasks()]);
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "员工工作空间加载失败");
    } finally {
      setLoading(false);
    }
  }, [authHydrated, loadEmployees, loadTasks, projectHydrated, token]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  useEffect(() => {
    if (!authHydrated || !projectHydrated || !token) return;
    const timer = window.setInterval(() => {
      void loadTasks().catch((requestError: unknown) => {
        setError(requestError instanceof Error ? requestError.message : "员工状态同步失败");
      });
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [authHydrated, loadTasks, projectHydrated, token]);

  useEffect(() => {
    if (!authHydrated || !projectHydrated || !token) return;
    const timer = window.setInterval(() => {
      void loadEmployees().catch((requestError: unknown) => {
        setError(requestError instanceof Error ? requestError.message : "员工配置同步失败");
      });
    }, EMPLOYEE_POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [authHydrated, loadEmployees, projectHydrated, token]);

  const officeAgents = useMemo(() => buildOfficeAgents(employees, tasks), [employees, tasks]);
  const handleAgentSelect = useCallback((agentId: string) => {
    setSelectedId(agentId);
    setDetailOpen(true);
  }, []);
  const selectedEmployee = employees.find((employee) => employee.id === selectedId) ?? employees[0];
  const selectedTasks = useMemo(
    () => (selectedEmployee ? tasksForEmployee(selectedEmployee, tasks) : []),
    [selectedEmployee, tasks],
  );
  const workingEmployees = useMemo(
    () => employees.filter((employee) => tasksForEmployee(employee, tasks).length > 0).length,
    [employees, tasks],
  );
  return (
    <PageShell breadcrumbs={moduleBreadcrumbs("agents")} fillViewport projectScope="all" title="硅基员工">
      <section className="relative min-h-[680px] flex-1 overflow-hidden rounded-lg bg-[#eef1f4] shadow-[0_18px_55px_rgba(38,51,65,0.14)]">
        <div className="absolute top-0 right-0 left-0 z-20 flex items-start justify-between gap-4 p-5 sm:p-7">
          <div className="min-w-0 rounded-md bg-white/78 px-3 py-2 backdrop-blur-md">
            <h1 className="font-semibold text-[#17212b] text-xl">智能体工作空间</h1>
            <p className="mt-1 truncate text-[#687584] text-xs">
              点击智能体查看详情与实时状态
              {syncedAt ? ` · ${syncedAt.toLocaleTimeString("zh-CN", { hour12: false })} 同步` : ""}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2 rounded-md bg-white/84 p-1.5 shadow-[0_8px_28px_rgba(40,52,66,0.12)] backdrop-blur-md">
            <button
              className={cn(
                "flex h-8 items-center gap-1.5 rounded px-3 text-xs transition-colors",
                viewMode === "cards" ? "bg-[#eaf2ff] font-medium text-[#246ee8]" : "text-[#6f7b88] hover:bg-white",
              )}
              onClick={() => setViewMode("cards")}
              type="button"
            >
              <LayoutGrid className="size-3.5" />
              卡片视图
            </button>
            <button
              className={cn(
                "flex h-8 items-center gap-1.5 rounded px-3 text-xs transition-colors",
                viewMode === "list" ? "bg-[#eaf2ff] font-medium text-[#246ee8]" : "text-[#6f7b88] hover:bg-white",
              )}
              onClick={() => setViewMode("list")}
              type="button"
            >
              <List className="size-3.5" />
              列表视图
            </button>
            <Button
              aria-label="刷新员工状态"
              className="text-[#66727f]"
              disabled={loading}
              onClick={() => void loadWorkspace()}
              size="icon-sm"
              variant="ghost"
            >
              <RefreshCw className={cn("size-4", loading && "animate-spin")} />
            </Button>
          </div>
        </div>

        {error ? (
          <div className="absolute top-24 right-5 left-5 z-30 rounded-md bg-red-50/95 px-4 py-2 text-red-600 text-xs shadow-sm">
            {error}
          </div>
        ) : null}

        <div className="h-full min-h-[680px]">
          {viewMode === "cards" ? (
            officeAgents.length > 0 ? (
              <OfficeCanvas agents={officeAgents} onAgentSelect={handleAgentSelect} />
            ) : (
              <div className="flex h-full min-h-[680px] items-center justify-center bg-white/60 text-[#77828e] text-sm">
                {loading ? "正在注册智能体员工…" : "暂无已注册智能体。"}
              </div>
            )
          ) : (
            <EmployeeListView employees={employees} onSelect={handleAgentSelect} tasks={tasks} />
          )}
        </div>

        <div className="pointer-events-none absolute right-5 bottom-5 z-20 flex items-center gap-3 rounded-md bg-white/80 px-3 py-2 text-[#65717d] text-xs backdrop-blur-md">
          <span>
            <strong className="font-semibold text-[#1f2a35]">{workingEmployees}</strong> 运行中
          </span>
          <span className="text-[#b2bbc4]">/</span>
          <span>
            <strong className="font-semibold text-[#1f2a35]">{Math.max(employees.length - workingEmployees, 0)}</strong>{" "}
            空闲
          </span>
        </div>

        {detailOpen && selectedEmployee ? (
          <>
            <button
              aria-label="关闭员工详情"
              className="absolute inset-0 z-30 bg-[#17212b]/12 backdrop-blur-[1px]"
              onClick={() => setDetailOpen(false)}
              type="button"
            />
            <aside className="absolute top-0 right-0 bottom-0 z-40 w-full max-w-[380px] border-white/70 border-l bg-white/94 shadow-[-20px_0_50px_rgba(28,39,52,0.16)] backdrop-blur-xl">
              <EmployeeDetail employee={selectedEmployee} tasks={selectedTasks} onClose={() => setDetailOpen(false)} />
            </aside>
          </>
        ) : null}
      </section>
    </PageShell>
  );
}

function EmployeeListView({
  employees,
  tasks,
  onSelect,
}: {
  employees: SiliconEmployee[];
  tasks: ApiTaskItem[];
  onSelect: (employeeId: string) => void;
}) {
  return (
    <div className="h-full min-h-[680px] overflow-auto bg-[#eef2f6]/92 px-5 pt-28 pb-8 sm:px-8">
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {employees.map((employee) => {
          const Icon = employeeIcons[employee.id as keyof typeof employeeIcons] ?? Bot;
          const currentTask = tasksForEmployee(employee, tasks)[0];
          return (
            <button
              className="flex min-w-0 items-center gap-4 rounded-md border border-white/80 bg-white/86 p-4 text-left shadow-[0_8px_24px_rgba(42,56,70,0.08)] transition hover:-translate-y-0.5 hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2e7cf6]"
              key={employee.id}
              onClick={() => onSelect(employee.id)}
              type="button"
            >
              <span
                className="flex size-11 shrink-0 items-center justify-center rounded-md text-white"
                style={{ backgroundColor: employee.accent_color }}
              >
                <Icon className="size-5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold text-[#1e2935] text-sm">{employee.name}</span>
                <span className="mt-1 block truncate text-[#7b8793] text-xs">{employee.capability_name}</span>
              </span>
              <span
                className={cn(
                  "shrink-0 rounded px-2 py-1 text-[11px]",
                  currentTask ? "bg-blue-50 text-blue-600" : "bg-[#f0f2f4] text-[#8a949e]",
                )}
              >
                {currentTask ? "运行中" : "空闲"}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function EmployeeDetail({
  employee,
  tasks,
  onClose,
}: {
  employee: SiliconEmployee;
  tasks: ApiTaskItem[];
  onClose: () => void;
}) {
  const currentTask = tasks[0];
  const Icon = employeeIcons[employee.id as keyof typeof employeeIcons] ?? Bot;

  return (
    <div className="flex h-full min-h-[320px] flex-col">
      <div className="flex items-center justify-between border-[#e5e9e9] border-b px-5 py-4">
        <span className="font-medium text-[#48564d] text-sm">智能体详情</span>
        <button
          aria-label="关闭员工详情"
          className="rounded p-1 text-[#68756d] transition-colors hover:bg-[#edf2ee]"
          onClick={onClose}
          type="button"
        >
          <X className="size-4" />
        </button>
      </div>
      <div className="border-[#e5e9e9] border-b p-4">
        <div className="flex items-start gap-3">
          <span
            className="flex size-10 shrink-0 items-center justify-center rounded-md text-white"
            style={{ backgroundColor: employee.accent_color }}
          >
            <Icon className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-semibold text-sm">{employee.name}</h2>
              <Badge variant={currentTask ? "default" : "secondary"}>{currentTask ? "工作中" : "空闲"}</Badge>
            </div>
            <p className="mt-1 text-muted-foreground text-xs">
              {employee.department} · {employee.capability_name}
            </p>
            <p className="mt-2 text-muted-foreground text-xs leading-5">{employee.description}</p>
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-5 overflow-auto p-4">
        <section className="grid grid-cols-2 gap-3 text-xs">
          <DetailFact label="员工 ID" value={employee.id} />
          <DetailFact label="注册状态" value={employee.registered ? "已注册" : "未注册"} />
        </section>

        <section>
          <h3 className="mb-2 font-medium text-xs">当前任务</h3>
          {currentTask ? (
            <div className="space-y-2 border-primary border-l-2 pl-3">
              <div className="font-medium text-sm leading-5">{currentTask.title}</div>
              <div className="flex flex-wrap items-center gap-2 text-muted-foreground text-xs">
                <span>{currentTask.project_name}</span>
                <span>·</span>
                <span>{currentTask.module_label}</span>
              </div>
              <Badge variant="outline">{currentTask.status_label}</Badge>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">当前没有执行中的任务。</p>
          )}
        </section>

        {currentTask ? (
          <section>
            <h3 className="mb-3 font-medium text-xs">实时运行步骤</h3>
            <ol className="space-y-3">
              <RunStep label="任务已接收" time={currentTask.created_at} />
              <RunStep active label={currentTask.status_label} time={currentTask.updated_at} />
              {currentTask.summary ? <RunStep label={currentTask.summary} time={currentTask.updated_at} /> : null}
            </ol>
          </section>
        ) : null}

        {tasks.length > 1 ? (
          <section>
            <h3 className="mb-2 font-medium text-xs">并行任务</h3>
            <div className="divide-y border-y">
              {tasks.slice(1, 4).map((task) => (
                <div className="py-2.5" key={task.id}>
                  <div className="truncate font-medium text-xs">{task.title}</div>
                  <div className="mt-1 text-muted-foreground text-xs">
                    {task.project_name} · {task.status_label}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {currentTask?.detail_url ? (
          <Button asChild className="w-full" variant="outline">
            <Link href={currentTask.detail_url}>
              打开任务详情
              <ExternalLink className="size-4" />
            </Link>
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function DetailFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-l pl-3">
      <div className="text-muted-foreground">{label}</div>
      <div className="mt-1 truncate font-medium" title={value}>
        {value}
      </div>
    </div>
  );
}

function RunStep({ label, time, active = false }: { label: string; time: string; active?: boolean }) {
  return (
    <li className="grid grid-cols-[12px_minmax(0,1fr)] gap-2.5">
      <span
        className={cn(
          "mt-1 size-2 rounded-full bg-muted-foreground/40",
          active && "bg-emerald-500 ring-4 ring-emerald-500/10",
        )}
      />
      <div className="min-w-0">
        <p className="break-words text-xs leading-5">{label}</p>
        <time className="text-[11px] text-muted-foreground">{formatDateTime(time)}</time>
      </div>
    </li>
  );
}
