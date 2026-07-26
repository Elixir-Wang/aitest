import type { Desk } from "@/types/agent";

const NEAR_X = 78;
const NEAR_Y = 130;

export function isAgentNearDesk(desk: Desk, ax: number, ay: number): boolean {
  return Math.abs(ax - desk.x) < NEAR_X && Math.abs(ay - desk.y) < NEAR_Y;
}

type AgentPos = { x: number; y: number };

function occupantY(desk: Desk, agents: AgentPos[]): number {
  return agents.find((agent) => isAgentNearDesk(desk, agent.x, agent.y))?.y ?? desk.seatY;
}

export function computeDeskLayerZ(desk: Desk, agents: AgentPos[]): number {
  return occupantY(desk, agents) + 0.5;
}

export function computeChairLayerZ(desk: Desk, agents: AgentPos[], chairAhead = 0): number {
  return occupantY(desk, agents) - 0.5 + chairAhead;
}
