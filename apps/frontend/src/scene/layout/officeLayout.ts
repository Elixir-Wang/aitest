import type { Desk } from "@/types/agent";

export const SCENE_WIDTH = 960;
export const SCENE_HEIGHT = 640;
export const SEAT_OFFSET_Y = 10;

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
      seatX: x,
      seatY: y + SEAT_OFFSET_Y,
      visualScale,
    };
  });
}

function buildPerspectiveRowY(rows: number) {
  if (rows <= 1) return [350];
  if (rows === 2) return [270, 500];
  if (rows === 3) return [220, 385, 535];

  const top = 205;
  const bottom = 540;
  return Array.from({ length: rows }, (_, row) => top + ((bottom - top) * row) / (rows - 1));
}
