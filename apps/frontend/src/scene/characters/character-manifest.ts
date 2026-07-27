import type { AgentState } from "@/types/agent";

export type CharacterAccessory =
  | "analysis-board"
  | "data-tablet"
  | "document-folder"
  | "explorer-compass"
  | "flow-board"
  | "glasses-round"
  | "glasses-square"
  | "headset-orange"
  | "headset-purple"
  | "performance-chart"
  | "report-folder"
  | "stylus"
  | "test-notes"
  | "ui-monitors";

export type CharacterProfile = {
  employeeId: string;
  skin: string;
  accentColor: number;
  accessorySlots: CharacterAccessory[];
  idleActions: string[];
  stateActions: Partial<Record<AgentState, string>>;
  fallbackPose: string;
  scale: number;
};

export const CEO_CHARACTER_PROFILE: CharacterProfile = {
  employeeId: "office-ceo",
  skin: "harri",
  accentColor: 0x183a61,
  accessorySlots: [],
  idleActions: ["emotes/dramatic-stare", "emotes/just-right"],
  stateActions: { idle: "movement/idle-front", thinking: "emotes/thinking", talking: "emotes/wave" },
  fallbackPose: "movement/idle-front",
  scale: 1.16,
};

const CHARACTER_PROFILES: Record<string, CharacterProfile> = {
  document_editor: profile("document_editor", "misaki", 0x4f7cff, ["stylus", "document-folder"], ["emotes/idea"]),
  requirement_standardization: profile(
    "requirement_standardization",
    "erikari",
    0x8b6fd8,
    ["glasses-square", "document-folder"],
    ["emotes/just-right"],
  ),
  requirement_analysis: profile(
    "requirement_analysis",
    "nate",
    0xe85d4a,
    ["analysis-board", "data-tablet"],
    ["emotes/thinking"],
  ),
  knowledge_query: profile("knowledge_query", "harri", 0x18a589, ["glasses-round", "document-folder"], ["emotes/idea"]),
  test_case_generation: profile(
    "test_case_generation",
    "luke",
    0xd5952f,
    ["test-notes", "stylus"],
    ["emotes/just-right"],
  ),
  test_point_generation: profile(
    "test_point_generation",
    "soeren",
    0x9b6dd7,
    ["headset-purple", "test-notes"],
    ["emotes/thinking"],
  ),
  api_test_generation: profile(
    "api_test_generation",
    "mario",
    0xf97316,
    ["headset-orange", "data-tablet"],
    ["emotes/determined"],
  ),
  api_scenario_orchestration: profile(
    "api_scenario_orchestration",
    "sinisa",
    0xdf574c,
    ["flow-board", "data-tablet"],
    ["emotes/idea"],
  ),
  ui_test_generation: profile(
    "ui_test_generation",
    "spineboy",
    0xe2ad2e,
    ["ui-monitors", "stylus"],
    ["emotes/excited"],
  ),
  page_exploration: profile(
    "page_exploration",
    "misaki",
    0x4a90d9,
    ["explorer-compass", "document-folder"],
    ["emotes/dramatic-stare"],
  ),
  performance_script_generation: profile(
    "performance_script_generation",
    "nate",
    0x3f8f75,
    ["performance-chart", "headset-orange"],
    ["emotes/determined"],
  ),
  performance_report_analysis: profile(
    "performance_report_analysis",
    "harri",
    0x4ecdc4,
    ["report-folder", "performance-chart"],
    ["emotes/just-right"],
  ),
};

const DEFAULT_CHARACTER_PROFILE = profile("default", "spineboy", 0x4a90d9, ["data-tablet"], ["emotes/wave"]);

export function getCharacterProfile(agentId: string): CharacterProfile {
  if (agentId === CEO_CHARACTER_PROFILE.employeeId) return CEO_CHARACTER_PROFILE;
  return CHARACTER_PROFILES[agentId] ?? { ...DEFAULT_CHARACTER_PROFILE, employeeId: agentId };
}

function profile(
  employeeId: string,
  skin: string,
  accentColor: number,
  accessorySlots: CharacterAccessory[],
  idleActions: string[],
): CharacterProfile {
  return {
    employeeId,
    skin,
    accentColor,
    accessorySlots,
    idleActions,
    stateActions: {
      idle: "movement/idle-front",
      walking: "movement/trot-front",
      working: "movement/idle-front",
      thinking: "emotes/thinking",
      talking: "emotes/wave",
    },
    fallbackPose: "movement/idle-front",
    scale: 1,
  };
}
