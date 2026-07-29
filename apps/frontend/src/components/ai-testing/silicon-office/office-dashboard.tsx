"use client";

import { type ReactNode, useMemo, useState } from "react";

import Image from "next/image";

import {
  Building2,
  CalendarDays,
  CircleAlert,
  Ellipsis,
  Mail,
  MapPin,
  MessageSquare,
  PlayCircle,
  UsersRound,
  X,
} from "lucide-react";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { usePreferencesStore } from "@/stores/preferences/preferences-provider";

import styles from "./office-dashboard.module.css";

type EmployeeStatus = "idle" | "running" | "error";
type WorkstationVariant = "male-gray" | "male-white" | "female-cream";

type OfficeEmployee = {
  id: string;
  name: string;
  role: string;
  room: string;
  seat: string;
  status: EmployeeStatus;
  workstation: WorkstationVariant;
  left: number;
  top: number;
  skills: string[];
  email: string;
};

type OfficeRoomData = {
  id: string;
  name: string;
  occupied: number;
  capacity: number;
  image: string;
  employees: OfficeEmployee[];
  executive?: boolean;
};

const ASSET_ROOT = "/assets/silicon-office-v2";
const EMPLOYEE_PORTRAITS: Record<WorkstationVariant, string> = {
  "male-gray": `${ASSET_ROOT}/workstations/workstation-male-gray-front-clean.png`,
  "male-white": `${ASSET_ROOT}/workstations/workstation-male-white-front-clean.png`,
  "female-cream": `${ASSET_ROOT}/workstations/workstation-female-cream-front-clean.png`,
};

const DETAIL_PORTRAITS: Partial<Record<string, string>> = {
  "li-ming": `${ASSET_ROOT}/portraits/male-handsome-charcoal.png`,
  "wang-fang": `${ASSET_ROOT}/portraits/female-yujie-red.png`,
  "liu-yang": `${ASSET_ROOT}/portraits/male-handsome-camel.png`,
  "zhang-wei": `${ASSET_ROOT}/portraits/male-handsome-charcoal.png`,
  "zhou-yan": `${ASSET_ROOT}/portraits/female-yujie-emerald.png`,
  "zhou-jie": `${ASSET_ROOT}/portraits/male-handsome-green.png`,
  "chen-yan": `${ASSET_ROOT}/portraits/female-yujie-plum.png`,
  "sun-na": `${ASSET_ROOT}/portraits/female-yujie-red.png`,
  "zheng-kai": `${ASSET_ROOT}/portraits/male-handsome-camel.png`,
  "tang-yu": `${ASSET_ROOT}/portraits/male-handsome-charcoal.png`,
  "lin-yue": `${ASSET_ROOT}/portraits/female-yujie-plum.png`,
  "peng-yu": `${ASSET_ROOT}/portraits/male-handsome-camel.png`,
  "xu-jing": `${ASSET_ROOT}/portraits/female-yujie-emerald.png`,
  "yang-fan": `${ASSET_ROOT}/portraits/male-handsome-green.png`,
  "he-li": `${ASSET_ROOT}/portraits/male-handsome-green.png`,
  ceo: `${ASSET_ROOT}/portraits/ceo-wang-avatar.png`,
};

const STATUS_META: Record<EmployeeStatus, { label: string; detail: string }> = {
  idle: { label: "空闲", detail: "等待任务" },
  running: { label: "运行中", detail: "专注工作" },
  error: { label: "异常", detail: "任务执行异常" },
};

const EMPLOYEES: OfficeEmployee[] = [
  employee("li-ming", "李明", "需求分析师", "requirement", "01-01", "running", "male-gray", 31, 35, [
    "需求分析",
    "业务建模",
  ]),
  employee("wang-fang", "王芳", "产品分析师", "requirement", "01-02", "running", "female-cream", 69, 35, [
    "需求澄清",
    "文档分析",
  ]),
  employee("liu-yang", "刘洋", "需求工程师", "requirement", "01-03", "idle", "male-white", 31, 69, [
    "原型审查",
    "规则提取",
  ]),
  employee("zhang-wei", "张伟", "测试设计师", "test-design", "02-03", "running", "male-gray", 31, 35, [
    "测试设计",
    "接口测试",
    "性能测试",
    "自动化测试",
  ]),
  employee("zhou-yan", "周燕", "测试分析师", "test-design", "02-04", "running", "female-cream", 69, 35, [
    "用例评审",
    "覆盖分析",
  ]),
  employee("zhou-jie", "周杰", "测试工程师", "test-design", "02-05", "running", "male-white", 31, 69, [
    "边界分析",
    "缺陷预测",
  ]),
  employee("chen-yan", "陈燕", "自动化工程师", "automation", "03-01", "running", "female-cream", 31, 35, [
    "UI 自动化",
    "脚本生成",
  ]),
  employee("sun-na", "孙娜", "接口自动化工程师", "automation", "03-02", "error", "female-cream", 69, 35, [
    "接口测试",
    "场景编排",
  ]),
  employee("zheng-kai", "郑凯", "自动化架构师", "automation", "03-03", "running", "male-gray", 31, 69, [
    "框架设计",
    "任务编排",
  ]),
  employee("tang-yu", "唐宇", "运行分析师", "operations", "04-01", "running", "male-white", 31, 35, [
    "运行监控",
    "日志分析",
  ]),
  employee("lin-yue", "林悦", "数据分析师", "operations", "04-02", "running", "female-cream", 69, 35, [
    "数据分析",
    "质量洞察",
  ]),
  employee("peng-yu", "彭宇", "质量分析师", "operations", "04-03", "running", "male-gray", 31, 69, [
    "质量分析",
    "趋势预测",
  ]),
  employee("xu-jing", "徐静", "AI 能力工程师", "ai-center", "05-01", "running", "female-cream", 31, 35, [
    "模型评测",
    "提示词工程",
  ]),
  employee("yang-fan", "杨帆", "知识工程师", "ai-center", "05-02", "running", "male-white", 69, 35, [
    "知识检索",
    "RAG",
  ]),
  employee("he-li", "何立", "算法工程师", "ai-center", "05-03", "idle", "male-white", 31, 69, ["模型路由", "智能分析"]),
  employee("ceo", "王总", "AI 测试负责人", "ceo", "CEO-01", "running", "male-gray", 50, 72, ["战略规划", "团队管理"]),
];

const ROOMS: OfficeRoomData[] = [
  room("requirement", "需求工程组", 6, 7, `${ASSET_ROOT}/rooms/requirement-room-unified.png`),
  room("test-design", "测试设计组", 8, 8, `${ASSET_ROOT}/rooms/test-design-room-unified.png`),
  room("automation", "自动化工程组", 7, 7, `${ASSET_ROOT}/rooms/automation-room-unified.png`),
  room("operations", "运行与分析组", 5, 6, `${ASSET_ROOT}/rooms/operations-room-unified.png`),
  room("ai-center", "AI能力中枢", 4, 4, `${ASSET_ROOT}/rooms/ai-center-room-unified.png`),
  room("ceo", "CEO办公室", 1, 1, `${ASSET_ROOT}/rooms/ceo-office-unified.png`, true),
];

const METRICS = [
  { label: "员工总数", value: 32, suffix: "人", hint: "较昨日 +2", tone: "blue", icon: UsersRound },
  { label: "工作中", value: 24, suffix: "人", hint: "75.0%", tone: "green", icon: PlayCircle },
  { label: "异常", value: 1, suffix: "人", hint: "3.1%", tone: "red", icon: CircleAlert },
] as const;

export function SiliconOfficeDashboard({ embedded = false }: { embedded?: boolean }) {
  const [selectedId, setSelectedId] = useState("zhang-wei");
  const [expandedRoomId, setExpandedRoomId] = useState<string | null>(null);
  const isDarkMode = usePreferencesStore((state) => state.themeMode === "dark");
  const selectedEmployee = useMemo(
    () => EMPLOYEES.find((employeeItem) => employeeItem.id === selectedId) ?? EMPLOYEES[3],
    [selectedId],
  );
  const expandedRoom = useMemo(
    () => ROOMS.find((roomItem) => roomItem.id === expandedRoomId) ?? null,
    [expandedRoomId],
  );

  return (
    <main className={[styles.dashboard, embedded ? styles.embedded : "", isDarkMode ? styles.darkTheme : ""].join(" ")}>
      <section className={styles.workspace}>
        <div className={styles.leftColumn}>
          <section aria-label="硅基员工状态概览" className={styles.metricsSection}>
            <div className={styles.metrics}>
              {METRICS.map((metric) => (
                <MetricCard key={metric.label} metric={metric} />
              ))}
            </div>
          </section>
          <div className={styles.officeFloor}>
            <div className={styles.roomGrid}>
              {ROOMS.map((roomItem) => (
                <OfficeRoom
                  key={roomItem.id}
                  onSelect={setSelectedId}
                  onOpenRoom={setExpandedRoomId}
                  room={roomItem}
                  selectedId={selectedEmployee.id}
                />
              ))}
            </div>
            <StatusLegend />
          </div>
        </div>
        <EmployeeDetailPanel employee={selectedEmployee} onClose={() => setSelectedId("")} />
      </section>
      <Dialog open={expandedRoom !== null} onOpenChange={(open) => !open && setExpandedRoomId(null)}>
        <DialogContent className={styles.roomDialog} showCloseButton>
          {expandedRoom ? (
            <>
              <DialogHeader className={styles.roomDialogHeader}>
                <DialogTitle>{expandedRoom.name}</DialogTitle>
                <DialogDescription>
                  {expandedRoom.occupied}/{expandedRoom.capacity} 个工位已占用 · 点击工位查看员工详情
                </DialogDescription>
              </DialogHeader>
              <div className={styles.roomPreviewScene}>
                <Image
                  alt={`${expandedRoom.name}工位实景`}
                  className={styles.roomBackground}
                  fill
                  sizes="(max-width: 760px) calc(100vw - 40px), 900px"
                  src={expandedRoom.image}
                />
                {!expandedRoom.executive
                  ? expandedRoom.employees.map((employeeItem) => (
                      <Workstation
                        employee={employeeItem}
                        key={employeeItem.id}
                        onSelect={(employeeId) => {
                          setSelectedId(employeeId);
                          setExpandedRoomId(null);
                        }}
                        selected={employeeItem.id === selectedEmployee.id}
                      />
                    ))
                  : null}
                {expandedRoom.executive ? (
                  <button
                    aria-label="查看王总"
                    className={[styles.executiveHotspot, selectedEmployee.id === "ceo" ? styles.selected : ""].join(
                      " ",
                    )}
                    onClick={(event) => {
                      event.stopPropagation();
                      setSelectedId("ceo");
                      setExpandedRoomId(null);
                    }}
                    type="button"
                  >
                    <Nameplate employee={expandedRoom.employees[0]} />
                  </button>
                ) : null}
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </main>
  );
}

function StatusLegend() {
  return (
    <section aria-label="员工状态图例" className={styles.statusLegend}>
      <span data-status="running">
        <i />
        运行中
      </span>
      <span data-status="idle">
        <i />
        空闲
      </span>
      <span data-status="error">
        <i />
        异常
      </span>
    </section>
  );
}

function MetricCard({ metric }: { metric: (typeof METRICS)[number] }) {
  const Icon = metric.icon;
  return (
    <article className={styles.metricCard} data-tone={metric.tone}>
      <span className={styles.metricIcon}>
        <Icon aria-hidden="true" />
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
  onSelect,
  onOpenRoom,
}: {
  room: OfficeRoomData;
  selectedId: string;
  onSelect: (employeeId: string) => void;
  onOpenRoom: (roomId: string) => void;
}) {
  return (
    <article className={styles.room} data-executive={room.executive ? "true" : "false"}>
      <header className={styles.roomHeader}>
        <h2>{room.name}</h2>
        <span>
          <UsersRound aria-hidden="true" /> {room.occupied}/{room.capacity}
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
        <button
          aria-label={`放大查看${room.name}`}
          className={styles.roomExpandHotspot}
          onClick={() => onOpenRoom(room.id)}
          title="点击空白区域放大查看"
          type="button"
        />
        {!room.executive
          ? room.employees.map((employeeItem) => (
              <Workstation
                employee={employeeItem}
                key={employeeItem.id}
                onSelect={onSelect}
                selected={employeeItem.id === selectedId}
              />
            ))
          : null}
        {room.executive ? (
          <button
            aria-label="查看王总"
            className={[styles.executiveHotspot, selectedId === "ceo" ? styles.selected : ""].join(" ")}
            onClick={(event) => {
              event.stopPropagation();
              onSelect("ceo");
            }}
            type="button"
          >
            <Nameplate employee={room.employees[0]} />
          </button>
        ) : null}
      </div>
    </article>
  );
}

function Workstation({
  employee,
  selected,
  onSelect,
}: {
  employee: OfficeEmployee;
  selected: boolean;
  onSelect: (employeeId: string) => void;
}) {
  return (
    <button
      aria-label={`${employee.name}，${STATUS_META[employee.status].label}`}
      className={[styles.workstation, styles[employee.status], selected ? styles.selected : ""].join(" ")}
      data-variant={employee.workstation}
      onClick={(event) => {
        event.stopPropagation();
        onSelect(employee.id);
      }}
      style={{ left: `${employee.left}%`, top: `${employee.top}%` }}
      type="button"
    >
      {employee.status !== "idle" ? <Nameplate employee={employee} /> : null}
    </button>
  );
}

function Nameplate({ employee }: { employee: OfficeEmployee }) {
  const status = STATUS_META[employee.status];
  return (
    <span className={styles.nameplate}>
      <span className={styles.nameCopy}>
        <strong>{employee.name}</strong>
        <small>
          <i /> {status.label}
        </small>
      </span>
    </span>
  );
}

function EmployeeDetailPanel({ employee, onClose }: { employee: OfficeEmployee; onClose: () => void }) {
  const status = STATUS_META[employee.status];
  const [selectedTask, setSelectedTask] = useState("接口测试用例设计");
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
            alt={`${employee.name}的头像`}
            className={styles.profileAvatarImage}
            fill
            sizes="56px"
            src={DETAIL_PORTRAITS[employee.id] ?? EMPLOYEE_PORTRAITS[employee.workstation]}
          />
        </div>
        <div>
          <h3>
            {employee.name}
            <span className={styles.profileStatus} data-status={employee.status}>
              <i /> {status.detail}
            </span>
          </h3>
          <p className={styles.profileMeta}>
            <Building2 aria-hidden="true" />
            {employee.room === "ceo" ? "管理中心" : roomName(employee.room)} · {employee.role}
          </p>
          <p className={styles.profileMeta}>
            <MapPin aria-hidden="true" />
            工位：{employee.seat}
          </p>
          <p className={styles.profileMeta}>
            <Mail aria-hidden="true" />
            {employee.email}
          </p>
        </div>
      </div>

      <section aria-label="员工今日状态摘要" className={styles.detailSnapshot}>
        <div>
          <span>今日专注</span>
          <strong>3h 42m</strong>
        </div>
        <div>
          <span>完成任务</span>
          <strong>3 / 4</strong>
        </div>
        <div>
          <span>今日会议</span>
          <strong>1 场</strong>
        </div>
      </section>

      <nav aria-label="员工详情分类" className={styles.detailTabs}>
        <button className={styles.activeTab} type="button">
          概览
        </button>
        <button type="button">状态</button>
        <button type="button">统计</button>
        <button type="button">项目</button>
      </nav>

      <div className={styles.detailBody}>
        <DetailSection title="技能标签">
          <div className={styles.skillList}>
            {employee.skills.map((skill) => (
              <span key={skill}>{skill}</span>
            ))}
          </div>
        </DetailSection>
        <DetailSection title="今日工作安排">
          <ol className={styles.timeline}>
            <TimelineItem
              active={selectedTask === "接口测试用例设计"}
              label="接口测试用例设计"
              onSelect={setSelectedTask}
              status="进行中"
              time="09:00-10:30"
            />
            <TimelineItem
              active={selectedTask === "项目需求评审"}
              label="项目需求评审"
              onSelect={setSelectedTask}
              status="已完成"
              time="10:45-12:00"
            />
            <TimelineItem
              active={selectedTask === "自动化测试脚本开发"}
              label="自动化测试脚本开发"
              onSelect={setSelectedTask}
              status="待开始"
              time="14:00-16:00"
            />
            <TimelineItem
              active={selectedTask === "测试报告编写"}
              label="测试报告编写"
              onSelect={setSelectedTask}
              status="待开始"
              time="16:15-17:30"
            />
          </ol>
        </DetailSection>
        <div className={styles.taskDetail}>
          <span>当前任务</span>
          <strong>{selectedTask}</strong>
          <p>点击任务或对应工位，可快速切换员工详情。</p>
        </div>
      </div>

      <footer className={styles.detailActions}>
        <button type="button">
          <MessageSquare aria-hidden="true" />
          发送消息
        </button>
        <button type="button">
          <CalendarDays aria-hidden="true" />
          查看日程
        </button>
        <button type="button">
          <Ellipsis aria-hidden="true" />
          更多操作
        </button>
      </footer>
    </aside>
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

function TimelineItem({
  time,
  label,
  status,
  active = false,
  onSelect,
}: {
  time: string;
  label: string;
  status: string;
  active?: boolean;
  onSelect: (label: string) => void;
}) {
  return (
    <li className={active ? styles.timelineActive : ""}>
      <span className={styles.timelineDot} />
      <time>{time}</time>
      <button className={styles.timelineTask} onClick={() => onSelect(label)} type="button">
        {label}
      </button>
      <em>{status}</em>
    </li>
  );
}

function room(
  id: string,
  name: string,
  occupied: number,
  capacity: number,
  image: string,
  executive = false,
): OfficeRoomData {
  return {
    id,
    name,
    occupied,
    capacity,
    image,
    executive,
    employees: EMPLOYEES.filter((employeeItem) => employeeItem.room === id),
  };
}

function employee(
  id: string,
  name: string,
  role: string,
  roomId: string,
  seat: string,
  status: EmployeeStatus,
  workstation: WorkstationVariant,
  left: number,
  top: number,
  skills: string[],
): OfficeEmployee {
  return {
    id,
    name,
    role,
    room: roomId,
    seat,
    status,
    workstation,
    left,
    top,
    skills,
    email: `${id.replaceAll("-", "")}@siliconflow.ai`,
  };
}

function roomName(roomId: string) {
  return ROOMS.find((roomItem) => roomItem.id === roomId)?.name ?? "硅基员工中心";
}
