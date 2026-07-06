export type AgentPlanStatus =
  | "pending"
  | "queued"
  | "in-progress"
  | "running"
  | "stopping"
  | "completed"
  | "blocked"
  | "waiting_human"
  | "cancelled"
  | "failed";
