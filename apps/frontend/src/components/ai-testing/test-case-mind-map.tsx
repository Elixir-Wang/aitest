"use client";

import type { ApiTestCase } from "@/lib/api-client";
import { testCasePriorityVisual } from "@/lib/test-case-priority";

import { type MindMapItemConfig, MindMapTree, type MindMapTreeProps } from "./mind-map-tree";

type Props = Omit<MindMapTreeProps<ApiTestCase>, "config" | "items" | "onSelect" | "selectedId"> & {
  cases: ApiTestCase[];
  setName: string;
  selectedCaseId: string;
  onSelectCase: (caseId: string) => void;
};

const testCaseConfig: MindMapItemConfig<ApiTestCase> = {
  getText: (c) => c.title,
  getId: (c) => c.id,
  getGroupKey: (c) => c.module.trim() || "未分模块",
  getTag: (c) => {
    if (!c.priority) return null;
    const priority = testCasePriorityVisual(c.priority);
    return {
      text: priority.label,
      style: {
        fill: priority.tagFill,
        fontSize: 11,
        height: 20,
        paddingX: 7,
        radius: 10,
      },
    };
  },
  rootLabel: "",
  groupLabel: "未分模块",
};

export function TestCaseMindMap({ cases, setName, selectedCaseId, onSelectCase, ...rest }: Props) {
  const config: MindMapItemConfig<ApiTestCase> = {
    ...testCaseConfig,
    rootLabel: setName,
  };

  return (
    <MindMapTree<ApiTestCase>
      active={rest.active}
      config={config}
      items={cases}
      onSelect={onSelectCase}
      selectedId={selectedCaseId}
    />
  );
}
