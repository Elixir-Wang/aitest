export type AgentPlanStatus =
  | "pending"
  | "queued"
  | "in-progress"
  | "running"
  | "stopping"
  | "completed"
  | "partial"
  | "blocked"
  | "waiting_human"
  | "cancelled"
  | "failed";
