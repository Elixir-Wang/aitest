import type { Desk } from "@/types/agent";

export const SCENE_WIDTH = 960;
export const SCENE_HEIGHT = 780;
export const SEAT_OFFSET_Y = 26;

export const OFFICE_DEPARTMENT_ORDER = ["需求工程", "测试设计", "自动化工程", "运行与分析"] as const;
export const OTHER_DEPARTMENT = "其他";

export type OfficeLayoutEmployee = {
  id: string;
  department: string;
  seat_index: number;
};

export const COLORS = {
  floor: 0xeef1ef,
  wall: 0xdfe6e1,
  desk: 0xfafbf9,
  deskShadow: 0x00000014,
  monitor: 0x2a2a2a,
  chair: 0xd4d2cc,
  agentBody: 0x1a1a1a,
} as const;

export function buildOfficeDesks(employeeCount: number): Desk[] {
  if (employeeCount <= 0) return [];

  const columns = employeeCount <= 9 ? 3 : 4;
  const rows = Math.ceil(employeeCount / columns);
  const rowY = buildPerspectiveRowY(rows);

  return Array.from({ length: employeeCount }, (_, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    const depth = rows <= 1 ? 1 : row / (rows - 1);
    const visualScale = 0.74 + depth * 0.22;
    const baseGap = columns === 4 ? 185 : 220;
    const columnGap = baseGap + depth * (columns === 4 ? 40 : 45);
    const itemsInRow = Math.min(columns, employeeCount - row * columns);
    const rowWidth = (itemsInRow - 1) * columnGap;
    const x = (SCENE_WIDTH - rowWidth) / 2 + column * columnGap;
    const y = rowY[row];
    return {
      id: `desk-${index}`,
      x,
      y,
      seatX: x - 32,
      seatY: y + SEAT_OFFSET_Y,
      visualScale,
    };
  });
}

export function buildDepartmentOfficeLayout(employees: OfficeLayoutEmployee[]): Desk[] {
  const departmentX = new Map<string, number>([
    ["需求工程", 118],
    ["测试设计", 358],
    ["自动化工程", 602],
    ["运行与分析", 842],
  ]);
  const rowY = [342, 440, 530];
  const rowScale = [0.78, 0.88, 0.98];
  const desks: Desk[] = [];

  for (const department of OFFICE_DEPARTMENT_ORDER) {
    const members = employees
      .filter((employee) => employee.department === department)
      .sort((left, right) => left.seat_index - right.seat_index);
    const centerX = departmentX.get(department) ?? SCENE_WIDTH / 2;

    members.forEach((employee, index) => {
      const row = Math.min(index, rowY.length - 1);
      desks.push({
        id: `department-${OFFICE_DEPARTMENT_ORDER.indexOf(department)}-${index}`,
        x: centerX,
        y: rowY[row],
        seatX: centerX - 32,
        seatY: rowY[row] + SEAT_OFFSET_Y,
        visualScale: rowScale[row],
        occupiedBy: employee.id,
      });
    });
  }

  const knownDepartments = new Set<string>(OFFICE_DEPARTMENT_ORDER);
  const otherEmployees = employees
    .filter((employee) => !knownDepartments.has(employee.department))
    .sort((left, right) => left.seat_index - right.seat_index);
  const otherDesks = buildOfficeDesks(otherEmployees.length);
  otherDesks.forEach((desk, index) => {
    const employee = otherEmployees[index];
    if (!employee) return;
    desks.push({
      ...desk,
      id: `${OTHER_DEPARTMENT}-${index}`,
      y: Math.min(desk.y + 30, SCENE_HEIGHT - 60),
      seatY: Math.min(desk.seatY + 30, SCENE_HEIGHT - 50),
      occupiedBy: employee.id,
    });
  });

  return desks;
}

function buildPerspectiveRowY(rows: number) {
  if (rows <= 1) return [350];
  if (rows === 2) return [270, 500];
  if (rows === 3) return [220, 385, 535];

  const top = 205;
  const bottom = 540;
  return Array.from({ length: rows }, (_, row) => top + ((bottom - top) * row) / (rows - 1));
}
