import type { AgentState } from "@/types/agent";

export type ChibiFacing = "front" | "back" | "left" | "right";

export type ChibiAgentPreset = {
  facing: ChibiFacing;
  stateAnims: Partial<Record<AgentState, string>>;
};

/** 6 位 Agent 朝向与标志性动作 */
export const CHIBI_AGENT_PRESETS: Record<string, ChibiAgentPreset> = {
  "requirement-agent": {
    facing: "front",
    stateAnims: {
      idle: "emotes/determined",
      working: "emotes/determined",
      walking: "movement/trot-front",
      thinking: "emotes/thinking",
      talking: "emotes/wave",
    },
  },
  "test-design-agent": {
    facing: "back",
    stateAnims: {
      working: "movement/idle-back",
      idle: "movement/idle-back",
      walking: "movement/trot-back",
      thinking: "movement/idle-back",
      talking: "movement/idle-back",
    },
  },
  "ui-automation-agent": {
    facing: "left",
    stateAnims: {
      walking: "movement/trot-left",
      idle: "movement/idle-left",
      working: "movement/idle-left",
      thinking: "movement/idle-left",
      talking: "movement/idle-left",
    },
  },
  "performance-agent": {
    facing: "right",
    stateAnims: {
      thinking: "emotes/thinking",
      idle: "movement/idle-right",
      working: "movement/idle-right",
      walking: "movement/trot-right",
      talking: "emotes/wave",
    },
  },
  "exploration-agent": {
    facing: "front",
    stateAnims: {
      working: "emotes/idea",
      idle: "emotes/idea",
      thinking: "emotes/thinking",
      talking: "emotes/excited",
    },
  },
  "api-automation-agent": {
    facing: "front",
    stateAnims: {
      talking: "emotes/wave",
      working: "emotes/determined",
      idle: "movement/idle-front",
    },
  },
};

export function getChibiAgentPreset(agentId: string): ChibiAgentPreset | null {
  return CHIBI_AGENT_PRESETS[agentId] ?? null;
}

export function resolveChibiPresetAnim(agentId: string, state: AgentState): string | null {
  if (state === "walking") return null;
  const preset = getChibiAgentPreset(agentId);
  if (!preset) return null;
  return preset.stateAnims[state] ?? null;
}
