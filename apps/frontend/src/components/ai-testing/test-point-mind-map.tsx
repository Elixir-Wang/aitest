"use client";

import type { ApiTestPoint } from "@/lib/api-client";
import { testPointPriorityVisual } from "@/lib/test-point-priority";
import { MindMapTree, type MindMapItemConfig, type MindMapTreeProps } from "./mind-map-tree";

type Props = Omit<MindMapTreeProps<ApiTestPoint>, "config" | "items" | "onSelect" | "selectedId"> & {
  points: ApiTestPoint[];
  selectedPointId: string | null;
  onSelectPoint: (pointId: string) => void;
};

const testPointConfig: MindMapItemConfig<ApiTestPoint> = {
  getText: (p) => p.title,
  getId: (p) => p.id,
  getGroupKey: (p) => p.module.trim() || "未分模块",
  getTag: (p) => {
    const priority = testPointPriorityVisual(p.priority);
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
  rootLabel: "测试要点",
  groupLabel: "未分模块",
};

export function TestPointMindMap({ points, selectedPointId, onSelectPoint, ...rest }: Props) {
  return (
    <MindMapTree<ApiTestPoint>
      active={rest.active}
      config={testPointConfig}
      items={points}
      onSelect={onSelectPoint}
      selectedId={selectedPointId}
    />
  );
}
