import type { ApiTaskItem } from "@/lib/api-client";

export type WorkstationVariant = "female-cream" | "male-gray" | "male-white";

export type SiliconEmployee = {
  id: string;
  name: string;
  display_name: string;
  role: string;
  capability_name: string;
  description: string;
  department: string;
  department_id: string;
  department_name: string;
  accent_color: string;
  avatar_asset: string;
  workstation_variant: WorkstationVariant;
  seat_code: string;
  task_source_types: string[];
  seat_index: number;
  registered: boolean;
};

export type EmployeeRuntimeState = "idle" | "working";

export type OfficeEmployeeViewModel = SiliconEmployee & {
  state: EmployeeRuntimeState;
  currentTask: ApiTaskItem | null;
  activeTasks: ApiTaskItem[];
};

export type OfficeMetrics = {
  total: number;
  working: number;
  idle: number;
};

export function tasksForEmployee(employee: SiliconEmployee, tasks: ApiTaskItem[]) {
  const acceptedSourceTypes = new Set(employee.task_source_types);
  return tasks
    .filter((task) => acceptedSourceTypes.has(task.source_type))
    .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at));
}

export function buildOfficeEmployeeViewModels(
  employees: SiliconEmployee[],
  tasks: ApiTaskItem[],
): OfficeEmployeeViewModel[] {
  return [...employees]
    .sort((left, right) => left.seat_index - right.seat_index)
    .map((employee) => {
      const activeTasks = tasksForEmployee(employee, tasks);
      return {
        ...employee,
        state: activeTasks.length > 0 ? "working" : "idle",
        currentTask: activeTasks[0] ?? null,
        activeTasks,
      };
    });
}

export function buildOfficeMetrics(employees: OfficeEmployeeViewModel[]): OfficeMetrics {
  const working = employees.filter((employee) => employee.state === "working").length;
  return {
    total: employees.length,
    working,
    idle: employees.length - working,
  };
}
