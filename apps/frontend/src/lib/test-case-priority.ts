export type TestCasePriorityVisual = {
  label: string;
  tagFill: string;
  tone: string;
};

const DEFAULT_PRIORITY_VISUAL: TestCasePriorityVisual = {
  label: "P3",
  tagFill: "#64748B",
  tone: "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-500/40 dark:bg-slate-500/15 dark:text-slate-300",
};

const PRIORITY_VISUALS: Record<string, TestCasePriorityVisual> = {
  P0: {
    label: "P0",
    tagFill: "#DC2626",
    tone: "border-red-200 bg-red-50 text-red-700 dark:border-red-500/40 dark:bg-red-500/15 dark:text-red-300",
  },
  P1: {
    label: "P1",
    tagFill: "#D97706",
    tone: "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/15 dark:text-amber-300",
  },
  P2: {
    label: "P2",
    tagFill: "#2563EB",
    tone: "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-500/40 dark:bg-blue-500/15 dark:text-blue-300",
  },
  P3: DEFAULT_PRIORITY_VISUAL,
};

export function testCasePriorityVisual(priority: string): TestCasePriorityVisual {
  const normalized = priority.trim().toUpperCase();
  return PRIORITY_VISUALS[normalized] ?? { ...DEFAULT_PRIORITY_VISUAL, label: normalized || "P3" };
}
