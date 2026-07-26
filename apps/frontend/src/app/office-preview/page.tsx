"use client";

import { SiliconOfficeCanvas } from "@/components/ai-testing/silicon-office/office-canvas";
import type { Agent, AgentState } from "@/types/agent";

const ROLES = [
  ["产品分析师", "需求分析", "working"],
  ["接口工程师", "接口用例生成", "thinking"],
  ["性能测试工程师", "压测执行", "working"],
  ["自动化测试工程师", "回归测试编排", "talking"],
  ["UI设计师", "界面设计", "idle"],
  ["前端开发工程师", "页面开发", "thinking"],
  ["数据分析师", "数据分析", "working"],
  ["测试用例工程师", "测试用例生成", "thinking"],
  ["运维工程师", "环境巡检", "working"],
  ["安全工程师", "安全分析", "talking"],
  ["文档工程师", "文档整理", "working"],
  ["项目经理", "项目管理", "idle"],
] as const;

const agents: Agent[] = ROLES.map(([name, currentTask, state], index) => ({
  id: `preview-${index}`,
  name,
  currentTask,
  state: state as AgentState,
  color: 0x3478ef,
  facing: 1,
  viewFacing: "front",
  x: 0,
  y: 0,
}));

export default function OfficePreviewPage() {
  return <SiliconOfficeCanvas agents={agents} onAgentSelect={() => undefined} />;
}
