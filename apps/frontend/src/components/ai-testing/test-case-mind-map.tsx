"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Loader2 } from "lucide-react";

import type { ApiTestCase, ApiTestCaseStep } from "@/lib/api-client";

type Props = {
  active: boolean;
  cases: ApiTestCase[];
  setName: string;
  selectedCaseId: string;
  onSelectCase: (caseId: string) => void;
};

type MindMapNode = {
  data: {
    text: string;
    uid?: string;
    testCaseId?: string;
    expand?: boolean;
    richText?: boolean;
  };
  children?: MindMapNode[];
};

function stepActionText(step: ApiTestCaseStep | string) {
  if (typeof step === "string") return step;
  return step.action || step.step || step.description || "";
}

function buildMindMapData(setName: string, cases: ApiTestCase[]): MindMapNode {
  const groupedCases = new Map<string, ApiTestCase[]>();
  for (const item of cases) {
    const moduleName = item.module.trim() || "未分模块";
    groupedCases.set(moduleName, [...(groupedCases.get(moduleName) ?? []), item]);
  }

  return {
    data: { text: setName, uid: "test-case-set-root", expand: true },
    children: Array.from(groupedCases, ([moduleName, moduleCases], moduleIndex) => ({
      data: { text: moduleName, uid: `module-${moduleIndex}`, expand: true },
      children: moduleCases.map((item) => ({
        data: {
          text: `${item.priority ? `${item.priority} ` : ""}${item.title}`,
          uid: `test-case-${item.id}`,
          testCaseId: item.id,
          expand: true,
        },
        children: [
          ...(item.preconditions
            ? [{ data: { text: `前置条件：${item.preconditions}`, uid: `precondition-${item.id}` } }]
            : []),
          ...item.steps.map((step, index) => ({
            data: {
              text: `步骤${index + 1}：${stepActionText(step)}`,
              uid: `step-${item.id}-${index}`,
              expand: true,
            },
            children: [
              {
                data: {
                  text: `预期结果${index + 1}：${
                    step.expected_result || (index === item.steps.length - 1 ? item.expected_result : "-")
                  }`,
                  uid: `result-${item.id}-${index}`,
                },
              },
            ],
          })),
          ...(item.steps.length === 0 && item.expected_result
            ? [
                {
                  data: {
                    text: `预期结果：${item.expected_result}`,
                    uid: `result-${item.id}-summary`,
                  },
                },
              ]
            : []),
        ],
      })),
    })),
  };
}

export function TestCaseMindMap({ active, cases, setName, selectedCaseId, onSelectCase }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<SimpleMindMapInstance | null>(null);
  const onSelectCaseRef = useRef(onSelectCase);
  const selectedCaseIdRef = useRef(selectedCaseId);
  const [rendering, setRendering] = useState(true);
  const data = useMemo(() => buildMindMapData(setName, cases), [cases, setName]);

  useEffect(() => {
    onSelectCaseRef.current = onSelectCase;
  }, [onSelectCase]);

  useEffect(() => {
    selectedCaseIdRef.current = selectedCaseId;
    if (!selectedCaseId || !instanceRef.current) return;
    instanceRef.current.renderer.findNodeByUid(`test-case-${selectedCaseId}`)?.active();
  }, [selectedCaseId]);

  useEffect(() => {
    if (!active || !instanceRef.current) return;
    const frameId = requestAnimationFrame(() => {
      instanceRef.current?.resize();
      instanceRef.current?.view.fit();
    });
    return () => cancelAnimationFrame(frameId);
  }, [active]);

  useEffect(() => {
    let disposed = false;

    async function renderMindMap() {
      const container = containerRef.current;
      if (!container) return;

      instanceRef.current?.destroy();
      instanceRef.current = null;
      container.replaceChildren();
      setRendering(true);

      const { default: MindMap } = await import("simple-mind-map");
      if (disposed || !containerRef.current) return;

      const mindMap = new MindMap({
        el: containerRef.current,
        data,
        layout: "logicalStructure",
        readonly: true,
        fit: true,
        mousewheelAction: "zoom",
        enableFreeDrag: true,
        nodeTextEditZIndex: 10,
        themeConfig: {
          backgroundColor: "#fbfcfe",
          lineColor: "#94a3b8",
          lineWidth: 2,
          lineStyle: "curve",
          root: {
            fillColor: "#172033",
            color: "#ffffff",
            borderColor: "#172033",
            borderWidth: 2,
            borderRadius: 12,
            paddingX: 18,
            paddingY: 12,
            fontSize: 18,
            fontWeight: "600",
          },
          second: {
            fillColor: "#ffffff",
            color: "#172033",
            borderColor: "#93c5fd",
            borderWidth: 1,
            borderRadius: 10,
            paddingX: 14,
            paddingY: 9,
            fontSize: 15,
            fontWeight: "600",
          },
          node: {
            fillColor: "#ffffff",
            color: "#334155",
            borderColor: "#dbe4f0",
            borderWidth: 1,
            borderRadius: 8,
            paddingX: 12,
            paddingY: 8,
            fontSize: 14,
          },
        },
      });
      mindMap.on("node_tree_render_end", () => {
        mindMap.view.fit();
        const currentCaseId = selectedCaseIdRef.current;
        if (currentCaseId) {
          mindMap.renderer.findNodeByUid(`test-case-${currentCaseId}`)?.active();
        }
        setRendering(false);
      });
      mindMap.on("node_click", (node) => {
        const caseId = node.getData("testCaseId");
        if (typeof caseId === "string" && caseId) onSelectCaseRef.current(caseId);
      });
      instanceRef.current = mindMap;
    }

    void renderMindMap();
    return () => {
      disposed = true;
      instanceRef.current?.destroy();
      instanceRef.current = null;
    };
  }, [data]);

  if (cases.length === 0) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center bg-[#fbfcfe] text-muted-foreground text-sm">
        当前筛选条件下没有可展示的测试用例。
      </div>
    );
  }

  return (
    <div className="relative min-h-0 flex-1 overflow-hidden bg-[#fbfcfe]">
      <div className="pointer-events-none absolute top-4 left-4 z-10 flex items-center gap-2 rounded-lg border bg-white/90 px-3 py-2 text-slate-500 text-xs shadow-sm backdrop-blur">
        {rendering ? <Loader2 className="size-3.5 animate-spin" /> : null}
        {rendering ? "正在绘制脑图" : "滚轮缩放 · 拖动画布 · 点击用例查看详情"}
      </div>
      <div className="h-full min-h-0 w-full" ref={containerRef} />
    </div>
  );
}
