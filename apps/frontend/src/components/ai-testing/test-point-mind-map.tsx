"use client";

import type { ApiTestPoint } from "@/lib/api-client";
import { testPointPriorityVisual } from "@/lib/test-point-priority";

import { type MindMapItemConfig, MindMapTree, type MindMapTreeProps } from "./mind-map-tree";

type Props = Omit<MindMapTreeProps<ApiTestPoint>, "config" | "items" | "onEdit" | "onSelect" | "selectedId"> & {
  points: ApiTestPoint[];
  selectedPointId: string | null;
  onEditPoint?: (pointId: string, title: string) => Promise<void> | void;
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

export function TestPointMindMap({ points, selectedPointId, onEditPoint, onSelectPoint, ...rest }: Props) {
  return (
    <MindMapTree<ApiTestPoint>
      active={rest.active}
      config={testPointConfig}
      editable={rest.editable}
      items={points}
      onEdit={onEditPoint}
      onSelect={onSelectPoint}
      selectedId={selectedPointId}
    />
  );
}
