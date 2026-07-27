import type { ApiTaskItem } from "@/lib/api-client";
import { buildDepartmentOfficeLayout } from "@/scene/layout/officeLayout";
import type { Agent } from "@/types/agent";

export type SiliconEmployee = {
  id: string;
  name: string;
  capability_name: string;
  description: string;
  department: string;
  accent_color: string;
  task_source_types: string[];
  seat_index: number;
  registered: boolean;
};

export function tasksForEmployee(employee: SiliconEmployee, tasks: ApiTaskItem[]) {
  const acceptedTypes = new Set(employee.task_source_types);
  return tasks
    .filter((task) => acceptedTypes.has(task.source_type))
    .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at));
}

export function buildOfficeAgents(employees: SiliconEmployee[], tasks: ApiTaskItem[]): Agent[] {
  const orderedEmployees = [...employees].sort((left, right) => left.seat_index - right.seat_index);
  const desks = buildDepartmentOfficeLayout(orderedEmployees);
  const deskByEmployeeId = new Map(desks.map((desk) => [desk.occupiedBy, desk]));

  return orderedEmployees.map((employee) => {
    const desk = deskByEmployeeId.get(employee.id);
    const assignedTasks = tasksForEmployee(employee, tasks);
    const currentTask = assignedTasks[0];
    const state = currentTask
      ? currentTask.status === "queued" || currentTask.status === "stopping"
        ? "thinking"
        : "working"
      : "idle";

    return {
      id: employee.id,
      name: employee.name,
      department: employee.department,
      characterProfileId: employee.id,
      color: parseAccentColor(employee.accent_color),
      x: desk?.seatX ?? 0,
      y: desk?.seatY ?? 0,
      visualScale: desk?.visualScale ?? 1,
      state,
      currentTask: currentTask ? compactTaskLabel(currentTask) : employee.capability_name,
      assignedDeskId: desk?.id,
      facing: 1,
      viewFacing: "front",
    };
  });
}

function compactTaskLabel(task: ApiTaskItem) {
  const label = `${task.status_label} · ${task.title}`;
  return label.length > 24 ? `${label.slice(0, 23)}…` : label;
}

function parseAccentColor(color: string) {
  const parsed = Number.parseInt(color.replace("#", ""), 16);
  return Number.isFinite(parsed) ? parsed : 0x4a90d9;
}
