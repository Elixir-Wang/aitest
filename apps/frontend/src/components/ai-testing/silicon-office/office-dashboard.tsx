"use client";

import { type ComponentType, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import Image from "next/image";
import { useRouter } from "next/navigation";

import {
  Bot,
  Building2,
  CircleAlert,
  Clock3,
  ExternalLink,
  MapPin,
  PlayCircle,
  RefreshCw,
  UsersRound,
  X,
} from "lucide-react";

import { AI_TASK_STARTED_EVENT } from "@/lib/ai-task-events";
import { type ApiTaskItem, apiRequest, formatDateTime } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import { usePreferencesStore } from "@/stores/preferences/preferences-provider";
import { useProjectContextStore } from "@/stores/project-context-store";

import {
  buildOfficeEmployeeViewModels,
  buildOfficeMetrics,
  type EmployeeRuntimeState,
  type OfficeEmployeeViewModel,
  type SiliconEmployee,
} from "./employee-projection";
import styles from "./office-dashboard.module.css";

type OfficeEmployee = OfficeEmployeeViewModel & {
  characterId: BuiltInCharacterId;
  left: number;
  top: number;
  size: number;
};

type OfficeRoomData = {
  id: string;
  name: string;
  capacity: number;
  image: string;
  deskForeground?: string;
  monitorForeground?: string;
  employees: OfficeEmployee[];
  executive?: boolean;
};

type Metric = {
  label: string;
  value: number | string;
  suffix: string;
  hint: string;
  tone: "blue" | "green" | "red";
  icon: ComponentType<{ "aria-hidden"?: boolean }>;
};

const ASSET_ROOT = "/assets/silicon-office-v2";
const POLL_INTERVAL_MS = 2_000;
const EMPLOYEE_POLL_INTERVAL_MS = 10 * 60 * 1_000;
const ROOM_CAPACITY = 4;
const CEO_ID = "office-ceo";
const CEO_PROFILE = {
  id: CEO_ID,
  displayName: "王总",
  role: "AI 测试负责人",
  departmentName: "管理中心",
  seatCode: "CEO-01",
  avatar: `${ASSET_ROOT}/portraits/ceo-wang-avatar.png`,
  responsibilities: ["战略规划", "团队管理"],
} as const;

const BUILT_IN_CHARACTER_IDS = [
  "document_editor",
  "requirement_standardization",
  "requirement_analysis",
  "knowledge_query",
  "test_case_generation",
  "test_point_generation",
  "api_test_generation",
  "api_scenario_orchestration",
  "ui_test_generation",
  "page_exploration",
  "performance_script_generation",
  "performance_report_analysis",
  "character_13",
  "character_14",
  "character_15",
  "character_16",
  "character_17",
  "character_18",
  "character_19",
  "character_20",
] as const;

type BuiltInCharacterId = (typeof BUILT_IN_CHARACTER_IDS)[number];

const PERSON_BODY_ASSETS: Record<BuiltInCharacterId, string> = {
  document_editor: `${ASSET_ROOT}/people/document_editor-body.png`,
  requirement_standardization: `${ASSET_ROOT}/people/requirement_standardization-body.png`,
  requirement_analysis: `${ASSET_ROOT}/people/requirement_analysis-body.png`,
  knowledge_query: `${ASSET_ROOT}/people/knowledge_query-body.png`,
  test_case_generation: `${ASSET_ROOT}/people/test_case_generation-body.png`,
  test_point_generation: `${ASSET_ROOT}/people/test_point_generation-body.png`,
  api_test_generation: `${ASSET_ROOT}/people/api_test_generation-body.png`,
  api_scenario_orchestration: `${ASSET_ROOT}/people/api_scenario_orchestration-body.png`,
  ui_test_generation: `${ASSET_ROOT}/people/ui_test_generation-body.png`,
  page_exploration: `${ASSET_ROOT}/people/page_exploration-body.png`,
  performance_script_generation: `${ASSET_ROOT}/people/performance_script_generation-body.png`,
  performance_report_analysis: `${ASSET_ROOT}/people/performance_report_analysis-body.png`,
  character_13: `${ASSET_ROOT}/people/character_13-body.png`,
  character_14: `${ASSET_ROOT}/people/character_14-body.png`,
  character_15: `${ASSET_ROOT}/people/character_15-body.png`,
  character_16: `${ASSET_ROOT}/people/character_16-body.png`,
  character_17: `${ASSET_ROOT}/people/character_17-body.png`,
  character_18: `${ASSET_ROOT}/people/character_18-body.png`,
  character_19: `${ASSET_ROOT}/people/character_19-body.png`,
  character_20: `${ASSET_ROOT}/people/character_20-body.png`,
};

const PERSON_HANDS_ASSETS: Record<BuiltInCharacterId, string> = {
  document_editor: `${ASSET_ROOT}/people/document_editor-hands.png`,
  requirement_standardization: `${ASSET_ROOT}/people/requirement_standardization-hands.png`,
  requirement_analysis: `${ASSET_ROOT}/people/requirement_analysis-hands.png`,
  knowledge_query: `${ASSET_ROOT}/people/knowledge_query-hands.png`,
  test_case_generation: `${ASSET_ROOT}/people/test_case_generation-hands.png`,
  test_point_generation: `${ASSET_ROOT}/people/test_point_generation-hands.png`,
  api_test_generation: `${ASSET_ROOT}/people/api_test_generation-hands.png`,
  api_scenario_orchestration: `${ASSET_ROOT}/people/api_scenario_orchestration-hands.png`,
  ui_test_generation: `${ASSET_ROOT}/people/ui_test_generation-hands.png`,
  page_exploration: `${ASSET_ROOT}/people/page_exploration-hands.png`,
  performance_script_generation: `${ASSET_ROOT}/people/performance_script_generation-hands.png`,
  performance_report_analysis: `${ASSET_ROOT}/people/performance_report_analysis-hands.png`,
  character_13: `${ASSET_ROOT}/people/character_13-hands.png`,
  character_14: `${ASSET_ROOT}/people/character_14-hands.png`,
  character_15: `${ASSET_ROOT}/people/character_15-hands.png`,
  character_16: `${ASSET_ROOT}/people/character_16-hands.png`,
  character_17: `${ASSET_ROOT}/people/character_17-hands.png`,
  character_18: `${ASSET_ROOT}/people/character_18-hands.png`,
  character_19: `${ASSET_ROOT}/people/character_19-hands.png`,
  character_20: `${ASSET_ROOT}/people/character_20-hands.png`,
};

const PERSON_PORTRAIT_ASSETS: Record<BuiltInCharacterId, string> = {
  document_editor: `${ASSET_ROOT}/people/document_editor-portrait.png`,
  requirement_standardization: `${ASSET_ROOT}/people/requirement_standardization-portrait.png`,
  requirement_analysis: `${ASSET_ROOT}/people/requirement_analysis-portrait.png`,
  knowledge_query: `${ASSET_ROOT}/people/knowledge_query-portrait.png`,
  test_case_generation: `${ASSET_ROOT}/people/test_case_generation-portrait.png`,
  test_point_generation: `${ASSET_ROOT}/people/test_point_generation-portrait.png`,
  api_test_generation: `${ASSET_ROOT}/people/api_test_generation-portrait.png`,
  api_scenario_orchestration: `${ASSET_ROOT}/people/api_scenario_orchestration-portrait.png`,
  ui_test_generation: `${ASSET_ROOT}/people/ui_test_generation-portrait.png`,
  page_exploration: `${ASSET_ROOT}/people/page_exploration-portrait.png`,
  performance_script_generation: `${ASSET_ROOT}/people/performance_script_generation-portrait.png`,
  performance_report_analysis: `${ASSET_ROOT}/people/performance_report_analysis-portrait.png`,
  character_13: `${ASSET_ROOT}/people/character_13-portrait.png`,
  character_14: `${ASSET_ROOT}/people/character_14-portrait.png`,
  character_15: `${ASSET_ROOT}/people/character_15-portrait.png`,
  character_16: `${ASSET_ROOT}/people/character_16-portrait.png`,
  character_17: `${ASSET_ROOT}/people/character_17-portrait.png`,
  character_18: `${ASSET_ROOT}/people/character_18-portrait.png`,
  character_19: `${ASSET_ROOT}/people/character_19-portrait.png`,
  character_20: `${ASSET_ROOT}/people/character_20-portrait.png`,
};

const ROOM_CONFIGS = [
  roomConfig("requirement", "需求工程组", ROOM_CAPACITY, "requirement"),
  roomConfig("test-design", "测试设计组", ROOM_CAPACITY, "test-design"),
  roomConfig("automation", "自动化工程组", ROOM_CAPACITY, "automation"),
  roomConfig("operations", "运行与分析组", ROOM_CAPACITY, "operations"),
  roomConfig("ai-center", "AI能力中枢", ROOM_CAPACITY, "ai-center"),
  roomConfig("ceo", "CEO办公室", 1, `${ASSET_ROOT}/rooms/ceo-office-unified.png`, true),
] as const;

const ROOM_SEAT_LAYOUTS = {
  requirement: [
    { left: 29.3, top: 24.4, size: 18.6 },
    { left: 69.3, top: 24.4, size: 18.6 },
    { left: 29.3, top: 56.5, size: 19.8 },
    { left: 69.3, top: 56.5, size: 19.8 },
  ],
  "test-design": [
    { left: 29.3, top: 24.4, size: 18.6 },
    { left: 69.3, top: 24.4, size: 18.6 },
    { left: 29.3, top: 56.5, size: 19.8 },
    { left: 69.3, top: 56.5, size: 19.8 },
  ],
  automation: [
    { left: 29.3, top: 24.4, size: 18.6 },
    { left: 69.3, top: 24.4, size: 18.6 },
    { left: 29.3, top: 56.5, size: 19.8 },
    { left: 69.3, top: 56.5, size: 19.8 },
  ],
  operations: [
    { left: 29.3, top: 24.4, size: 18.6 },
    { left: 69.3, top: 24.4, size: 18.6 },
    { left: 29.3, top: 56.5, size: 19.8 },
    { left: 69.3, top: 56.5, size: 19.8 },
  ],
  "ai-center": [
    { left: 29.3, top: 24.4, size: 18.6 },
    { left: 69.3, top: 24.4, size: 18.6 },
    { left: 29.3, top: 56.5, size: 19.8 },
    { left: 69.3, top: 56.5, size: 19.8 },
  ],
} as const;

export function SiliconOfficeDashboard({ embedded = false }: { embedded?: boolean }) {
  const { currentProjectId, hasHydrated: projectHydrated, hydrate, scope } = useProjectContextStore();
  const { hasHydrated: authHydrated, hydrate: hydrateAuth, token } = useAuthStore();
  const isDarkMode = usePreferencesStore((state) => state.themeMode === "dark");
  const [employees, setEmployees] = useState<SiliconEmployee[]>([]);
  const [tasks, setTasks] = useState<ApiTaskItem[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusUnknown, setStatusUnknown] = useState(false);
  const employeeRequestRef = useRef(0);
  const taskRequestRef = useRef(0);

  useEffect(() => hydrate(), [hydrate]);
  useEffect(() => hydrateAuth(), [hydrateAuth]);

  const loadEmployees = useCallback(async () => {
    employeeRequestRef.current += 1;
    const requestId = employeeRequestRef.current;
    const result = await apiRequest<SiliconEmployee[]>("/agents/employees");
    if (requestId !== employeeRequestRef.current) return;
    setEmployees(result);
    setSelectedId((current) =>
      current === CEO_ID || result.some((employee) => employee.id === current) ? current : (result[0]?.id ?? ""),
    );
  }, []);

  const loadTasks = useCallback(async () => {
    taskRequestRef.current += 1;
    const requestId = taskRequestRef.current;
    const query = scope === "project" && currentProjectId ? `?project_id=${encodeURIComponent(currentProjectId)}` : "";
    try {
      const result = await apiRequest<ApiTaskItem[]>(`/tasks/running${query}`);
      if (requestId !== taskRequestRef.current) return;
      setTasks(result);
      setStatusUnknown(false);
      setError("");
    } catch (requestError) {
      if (requestId !== taskRequestRef.current) return;
      setStatusUnknown(true);
      setError(requestError instanceof Error ? requestError.message : "员工状态加载失败");
    }
  }, [currentProjectId, scope]);

  const loadWorkspace = useCallback(async () => {
    if (!authHydrated || !projectHydrated || !token) {
      setEmployees([]);
      setTasks([]);
      setLoading(false);
      setError("");
      setStatusUnknown(false);
      return;
    }

    setLoading(true);
    try {
      await Promise.all([loadEmployees(), loadTasks()]);
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
    const timer = window.setInterval(() => void loadTasks(), POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [authHydrated, loadTasks, projectHydrated, token]);

  useEffect(() => {
    if (!authHydrated || !projectHydrated || !token) return;
    const timer = window.setInterval(() => void loadEmployees(), EMPLOYEE_POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [authHydrated, loadEmployees, projectHydrated, token]);

  useEffect(() => {
    const handleTaskStarted = () => void loadTasks();
    window.addEventListener(AI_TASK_STARTED_EVENT, handleTaskStarted);
    return () => window.removeEventListener(AI_TASK_STARTED_EVENT, handleTaskStarted);
  }, [loadTasks]);

  const employeeViewModels = useMemo(() => buildOfficeEmployeeViewModels(employees, tasks), [employees, tasks]);
  const metrics = useMemo(() => buildOfficeMetrics(employeeViewModels), [employeeViewModels]);
  const rooms = useMemo(() => buildOfficeRooms(employeeViewModels), [employeeViewModels]);
  const selectedEmployee = useMemo(
    () => employeeViewModels.find((employee) => employee.id === selectedId) ?? employeeViewModels[0] ?? null,
    [employeeViewModels, selectedId],
  );
  const executiveSelected = selectedId === CEO_ID;
  const metricCards = useMemo<Metric[]>(
    () => [
      {
        label: "员工总数",
        value: metrics.total,
        suffix: "人",
        hint: "真实注册智能体",
        tone: "blue",
        icon: UsersRound,
      },
      {
        label: "工作中",
        value: statusUnknown ? "-" : metrics.working,
        suffix: statusUnknown ? "" : "人",
        hint: statusUnknown ? "状态未知" : `${tasks.length} 个运行任务`,
        tone: "green",
        icon: PlayCircle,
      },
      {
        label: "空闲",
        value: statusUnknown ? "-" : metrics.idle,
        suffix: statusUnknown ? "" : "人",
        hint: statusUnknown ? "等待重新连接" : "等待任务",
        tone: "red",
        icon: Clock3,
      },
    ],
    [metrics, statusUnknown, tasks.length],
  );

  return (
    <main className={[styles.dashboard, embedded ? styles.embedded : "", isDarkMode ? styles.darkTheme : ""].join(" ")}>
      <section className={styles.workspace}>
        <div className={styles.leftColumn}>
          <section aria-label="硅基员工状态概览" className={styles.metricsSection}>
            <div className={styles.metrics}>
              {metricCards.map((metric) => (
                <MetricCard key={metric.label} metric={metric} />
              ))}
            </div>
          </section>
          <div className={styles.officeFloor}>
            <div className={styles.roomGrid}>
              {rooms.map((room) => (
                <OfficeRoom
                  key={room.id}
                  onSelect={setSelectedId}
                  room={room}
                  selectedId={selectedId}
                  statusUnknown={statusUnknown}
                />
              ))}
            </div>
            <StatusLegend statusUnknown={statusUnknown} />
          </div>
        </div>
        {executiveSelected ? (
          <ExecutiveDetailPanel onClose={() => setSelectedId("")} />
        ) : (
          <EmployeeDetailPanel
            employee={selectedEmployee}
            error={error}
            loading={loading}
            onClose={() => setSelectedId("")}
            onRefresh={() => void loadWorkspace()}
            statusUnknown={statusUnknown}
          />
        )}
      </section>
    </main>
  );
}

function StatusLegend({ statusUnknown }: { statusUnknown: boolean }) {
  return (
    <section aria-label="员工状态图例" className={styles.statusLegend}>
      <span data-status="running">
        <i />
        工作中
      </span>
      <span data-status="idle">
        <i />
        空闲
      </span>
      {statusUnknown ? (
        <span data-status="error">
          <i />
          状态未知
        </span>
      ) : null}
    </section>
  );
}

function MetricCard({ metric }: { metric: Metric }) {
  const Icon = metric.icon;
  return (
    <article className={styles.metricCard} data-tone={metric.tone}>
      <span className={styles.metricIcon}>
        <Icon aria-hidden={true} />
      </span>
      <div className={styles.metricCopy}>
        <span className={styles.metricLabel}>{metric.label}</span>
        <div className={styles.metricValueRow}>
          <strong>{metric.value}</strong>
          <span>{metric.suffix}</span>
        </div>
        <span className={styles.metricHint}>{metric.hint}</span>
      </div>
    </article>
  );
}

function OfficeRoom({
  room,
  selectedId,
  statusUnknown,
  onSelect,
}: {
  room: OfficeRoomData;
  selectedId: string;
  statusUnknown: boolean;
  onSelect: (employeeId: string) => void;
}) {
  return (
    <article className={styles.room} data-executive={room.executive ? "true" : "false"}>
      <header className={styles.roomHeader}>
        <h2>{room.name}</h2>
        <span>
          <UsersRound aria-hidden="true" /> {room.executive ? "视觉占位" : `${room.employees.length}/${room.capacity}`}
        </span>
      </header>
      <div className={styles.roomScene}>
        <Image
          alt=""
          className={styles.roomBackground}
          fill
          priority={room.id === "requirement" || room.id === "test-design"}
          sizes="(max-width: 1200px) 24vw, 280px"
          src={room.image}
        />
        {!room.executive
          ? room.employees.map((employee) => (
              <Workstation
                employee={employee}
                key={employee.id}
                onSelect={onSelect}
                selected={employee.id === selectedId}
                statusUnknown={statusUnknown}
              />
            ))
          : null}
        {room.deskForeground ? (
          <Image
            alt=""
            className={styles.deskForeground}
            fill
            sizes="(max-width: 1200px) 24vw, 280px"
            src={room.deskForeground}
          />
        ) : null}
        {room.monitorForeground ? (
          <Image
            alt=""
            className={styles.monitorForeground}
            fill
            sizes="(max-width: 1200px) 24vw, 280px"
            src={room.monitorForeground}
          />
        ) : null}
        {room.executive ? (
          <button
            aria-label={`查看${CEO_PROFILE.displayName}详情`}
            className={[styles.executiveHotspot, styles.idle, selectedId === CEO_ID ? styles.selected : ""].join(" ")}
            onClick={(event) => {
              event.stopPropagation();
              onSelect(CEO_ID);
            }}
            type="button"
          >
            <ExecutiveNameplate />
          </button>
        ) : null}
      </div>
    </article>
  );
}

function ExecutiveNameplate() {
  return (
    <span className={styles.nameplate}>
      <span className={styles.nameCopy}>
        <strong>CEO {CEO_PROFILE.displayName}</strong>
        <small>
          <i /> 空闲
        </small>
      </span>
    </span>
  );
}

function Workstation({
  employee,
  selected,
  statusUnknown,
  onSelect,
}: {
  employee: OfficeEmployee;
  selected: boolean;
  statusUnknown: boolean;
  onSelect: (employeeId: string) => void;
}) {
  const stateClass = statusUnknown ? styles.error : employee.state === "working" ? styles.running : styles.idle;
  const positionStyle = {
    left: `${employee.left}%`,
    top: `${employee.top}%`,
    width: `${employee.size}%`,
  };
  return (
    <>
      <span aria-hidden="true" className={styles.personBodyLayer} style={positionStyle}>
        <Image
          alt=""
          className={styles.personBodyImage}
          fill
          sizes="(max-width: 1200px) 6vw, 60px"
          src={personBodyAsset(employee)}
        />
      </span>
      <span aria-hidden="true" className={styles.personHandsLayer} style={positionStyle}>
        <Image
          alt=""
          className={styles.personHandsImage}
          fill
          sizes="(max-width: 1200px) 6vw, 60px"
          src={personHandsAsset(employee)}
        />
      </span>
      <button
        aria-label={`${employee.display_name}，${statusUnknown ? "状态未知" : stateLabel(employee.state)}`}
        className={[styles.workstation, stateClass, selected ? styles.selected : ""].join(" ")}
        data-variant={employee.workstation_variant}
        onClick={(event) => {
          event.stopPropagation();
          onSelect(employee.id);
        }}
        style={positionStyle}
        type="button"
      >
        <Nameplate employee={employee} statusUnknown={statusUnknown} />
      </button>
    </>
  );
}

function Nameplate({ employee, statusUnknown }: { employee: OfficeEmployee; statusUnknown: boolean }) {
  return (
    <span className={styles.nameplate}>
      <span className={styles.nameCopy}>
        <strong>{employee.display_name}</strong>
        <small>
          <i /> {statusUnknown ? "状态未知" : stateLabel(employee.state)}
        </small>
      </span>
    </span>
  );
}

function EmployeeDetailPanel({
  employee,
  loading,
  error,
  statusUnknown,
  onClose,
  onRefresh,
}: {
  employee: OfficeEmployeeViewModel | null;
  loading: boolean;
  error: string;
  statusUnknown: boolean;
  onClose: () => void;
  onRefresh: () => void;
}) {
  const router = useRouter();

  if (!employee) {
    return (
      <aside className={styles.detailPanel}>
        <header className={styles.detailHeader}>
          <h2>员工详情</h2>
        </header>
        <div className={styles.detailBody}>
          <div className={styles.taskDetail}>
            <strong>{loading ? "正在加载真实员工目录…" : "暂无可用智能体员工"}</strong>
            <p>{error || "请确认已登录并刷新页面。"}</p>
          </div>
        </div>
        <footer className={styles.detailActions}>
          <button onClick={onRefresh} type="button">
            <RefreshCw aria-hidden="true" />
            重新加载
          </button>
        </footer>
      </aside>
    );
  }

  const currentTask = employee.currentTask;
  const parallelTasks = employee.activeTasks.slice(1);
  const status = statusUnknown ? "状态未知" : stateLabel(employee.state);
  const avatar = personPortraitAsset(employee);

  return (
    <aside className={styles.detailPanel}>
      <header className={styles.detailHeader}>
        <h2>员工详情</h2>
        <button aria-label="关闭员工详情" onClick={onClose} type="button">
          <X aria-hidden="true" />
        </button>
      </header>

      <div className={styles.profile}>
        <div className={styles.profileAvatar}>
          <Image
            alt={`${employee.display_name}的头像`}
            className={styles.profileAvatarImage}
            fill
            sizes="72px"
            src={avatar}
          />
        </div>
        <div>
          <h3>
            {employee.display_name}
            <span
              className={styles.profileStatus}
              data-status={statusUnknown ? "error" : runtimeDataStatus(employee.state)}
            >
              <i /> {status}
            </span>
          </h3>
          <p className={styles.profileMeta}>
            <Building2 aria-hidden="true" />
            {employee.department_name} · {employee.role}
          </p>
          <p className={styles.profileMeta}>
            <MapPin aria-hidden="true" />
            工位：{employee.seat_code}
          </p>
          <p className={styles.profileMeta}>
            <Bot aria-hidden="true" />
            绑定能力：{employee.capability_name}
          </p>
        </div>
      </div>

      <section aria-label="员工实时状态摘要" className={styles.detailSnapshot}>
        <div>
          <span>当前状态</span>
          <strong>{status}</strong>
        </div>
        <div>
          <span>运行任务</span>
          <strong>{statusUnknown ? "-" : employee.activeTasks.length}</strong>
        </div>
        <div>
          <span>最近更新</span>
          <strong>{currentTask ? formatDateTime(currentTask.updated_at) : "-"}</strong>
        </div>
      </section>

      <nav aria-label="员工详情分类" className={styles.detailTabs}>
        <button className={styles.activeTab} type="button">
          当前工作
        </button>
        <button type="button">工作轨迹</button>
        <button type="button">历史记录</button>
      </nav>

      <div className={styles.detailBody}>
        {error ? (
          <div className={styles.taskDetail}>
            <span>状态同步异常</span>
            <strong>{error}</strong>
            <p>已保留最后一次成功快照，可手动重新加载。</p>
          </div>
        ) : null}

        <DetailSection title="能力说明">
          <div className={styles.taskDetail}>
            <strong>{employee.capability_name}</strong>
            <p>{employee.description}</p>
          </div>
        </DetailSection>

        <WorkloadSection currentTask={currentTask} parallelTasks={parallelTasks} statusUnknown={statusUnknown} />
      </div>

      <footer className={styles.detailActions}>
        <button
          disabled={!currentTask?.detail_url}
          onClick={() => currentTask?.detail_url && router.push(currentTask.detail_url)}
          type="button"
        >
          <ExternalLink aria-hidden="true" />
          打开任务详情
        </button>
        <button onClick={onRefresh} type="button">
          <RefreshCw aria-hidden="true" />
          刷新状态
        </button>
        <button onClick={() => router.push("/tasks")} type="button">
          <CircleAlert aria-hidden="true" />
          任务中心
        </button>
      </footer>
    </aside>
  );
}

function ExecutiveDetailPanel({ onClose }: { onClose: () => void }) {
  return (
    <aside className={styles.detailPanel}>
      <header className={styles.detailHeader}>
        <h2>负责人详情</h2>
        <button aria-label="关闭负责人详情" onClick={onClose} type="button">
          <X aria-hidden="true" />
        </button>
      </header>

      <div className={styles.profile}>
        <div className={styles.profileAvatar}>
          <Image
            alt={`${CEO_PROFILE.displayName}的头像`}
            className={styles.profileAvatarImage}
            fill
            sizes="72px"
            src={CEO_PROFILE.avatar}
          />
        </div>
        <div>
          <h3>{CEO_PROFILE.displayName}</h3>
          <p className={styles.profileMeta}>
            <Building2 aria-hidden="true" />
            {CEO_PROFILE.departmentName} · {CEO_PROFILE.role}
          </p>
          <p className={styles.profileMeta}>
            <MapPin aria-hidden="true" />
            办公室：{CEO_PROFILE.seatCode}
          </p>
        </div>
      </div>

      <div className={styles.detailBody}>
        <DetailSection title="管理职责">
          <div className={styles.skillList}>
            {CEO_PROFILE.responsibilities.map((responsibility) => (
              <span key={responsibility}>{responsibility}</span>
            ))}
          </div>
        </DetailSection>
        <DetailSection title="角色说明">
          <div className={styles.taskDetail}>
            <strong>AI 测试团队负责人</strong>
            <p>负责团队战略规划与整体协作管理。</p>
          </div>
        </DetailSection>
      </div>
    </aside>
  );
}

function TaskCard({ task }: { task: ApiTaskItem }) {
  return (
    <div className={styles.taskDetail}>
      <span>
        {task.project_name} · {task.module_label}
      </span>
      <strong>{task.title}</strong>
      <p>
        {task.status_label} · 更新于 {formatDateTime(task.updated_at)}
      </p>
    </div>
  );
}

function WorkloadSection({
  currentTask,
  parallelTasks,
  statusUnknown,
}: {
  currentTask: ApiTaskItem | null;
  parallelTasks: ApiTaskItem[];
  statusUnknown: boolean;
}) {
  return (
    <section className={styles.detailSection}>
      <div className={styles.workloadHeading}>
        <h4>工作安排</h4>
        <span data-status={statusUnknown ? "error" : currentTask ? "running" : "idle"}>
          <i />
          {statusUnknown ? "状态待同步" : currentTask ? "执行中" : "待命中"}
        </span>
      </div>

      <div className={styles.workloadPanel}>
        <div className={styles.workloadItem} data-active={currentTask ? "true" : "false"}>
          <span aria-hidden="true" className={styles.workloadMarker} />
          <div className={styles.workloadLabel}>
            <span>当前工作</span>
            <small>{currentTask ? "正在执行" : "空闲"}</small>
          </div>
          <div className={styles.workloadContent}>
            {currentTask ? (
              <TaskCard task={currentTask} />
            ) : (
              <div className={styles.workloadEmpty}>
                <strong>{statusUnknown ? "等待状态同步" : "等待任务分配"}</strong>
                <p>{statusUnknown ? "刷新后将恢复实时工作状态。" : "新任务到达后将在这里显示执行进度。"}</p>
              </div>
            )}
          </div>
        </div>

        <div className={styles.workloadItem} data-active={parallelTasks.length > 0 ? "true" : "false"}>
          <span aria-hidden="true" className={styles.workloadMarker} />
          <div className={styles.workloadLabel}>
            <span>并行任务</span>
            <small>{parallelTasks.length} 项</small>
          </div>
          <div className={styles.workloadContent}>
            {parallelTasks.length > 0 ? (
              <ol className={styles.timeline}>
                {parallelTasks.map((task) => (
                  <li key={task.id}>
                    <span className={styles.timelineDot} />
                    <time>{formatDateTime(task.updated_at)}</time>
                    <span className={styles.timelineTask}>{task.title}</span>
                    <em>{task.status_label}</em>
                  </li>
                ))}
              </ol>
            ) : (
              <p className={styles.workloadQueueEmpty}>暂无排队任务</p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function DetailSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={styles.detailSection}>
      <h4>{title}</h4>
      {children}
    </section>
  );
}

function buildOfficeRooms(employees: OfficeEmployeeViewModel[]): OfficeRoomData[] {
  const characterIds = assignCharacterIds(employees);
  return ROOM_CONFIGS.map((config) => {
    const seatLayout = ROOM_SEAT_LAYOUTS[config.id as keyof typeof ROOM_SEAT_LAYOUTS];
    const roomEmployees = employees
      .filter((employee) => employee.department_id === config.id)
      .slice(0, ROOM_CAPACITY)
      .map((employee) => ({
        ...employee,
        characterId: characterIds.get(employee.id) ?? BUILT_IN_CHARACTER_IDS[0],
        ...(seatLayout?.[employee.seat_index] ??
          seatLayout?.[seatLayout.length - 1] ??
          ROOM_SEAT_LAYOUTS.requirement[0]),
      }));
    return {
      ...config,
      employees: roomEmployees,
    };
  });
}

function roomConfig(id: string, name: string, capacity: number, roomAssetId: string, executive = false) {
  if (executive) {
    return { id, name, capacity, image: roomAssetId, executive };
  }
  return {
    id,
    name,
    capacity,
    image: `${ASSET_ROOT}/rooms/${roomAssetId}-room-furniture-clean.png`,
    deskForeground: `${ASSET_ROOT}/rooms/${roomAssetId}-room-desk-foreground.png`,
    monitorForeground: `${ASSET_ROOT}/rooms/${roomAssetId}-room-monitor-foreground.png`,
    executive,
  };
}

function assignCharacterIds(employees: OfficeEmployeeViewModel[]) {
  const availableCharacterIds = [...BUILT_IN_CHARACTER_IDS];
  const assignedCharacterIds = new Map<string, BuiltInCharacterId>();

  for (const employee of employees.slice(0, BUILT_IN_CHARACTER_IDS.length)) {
    const preferredCharacterId = isBuiltInCharacterId(employee.id) ? employee.id : null;
    const characterId = preferredCharacterId ?? availableCharacterIds[0];
    assignedCharacterIds.set(employee.id, characterId);
    availableCharacterIds.splice(availableCharacterIds.indexOf(characterId), 1);
  }

  return assignedCharacterIds;
}

function isBuiltInCharacterId(value: string): value is BuiltInCharacterId {
  return BUILT_IN_CHARACTER_IDS.includes(value as BuiltInCharacterId);
}

function personBodyAsset(employee: OfficeEmployee) {
  return PERSON_BODY_ASSETS[employee.characterId];
}

function personHandsAsset(employee: OfficeEmployee) {
  return PERSON_HANDS_ASSETS[employee.characterId];
}

function personPortraitAsset(employee: OfficeEmployeeViewModel) {
  const characterId = isBuiltInCharacterId(employee.id) ? employee.id : BUILT_IN_CHARACTER_IDS[0];
  return PERSON_PORTRAIT_ASSETS[characterId];
}

function stateLabel(state: EmployeeRuntimeState) {
  return state === "working" ? "工作中" : "空闲";
}

function runtimeDataStatus(state: EmployeeRuntimeState) {
  return state === "working" ? "running" : "idle";
}
