"use client";

import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";

import { Expand, Loader2, Maximize2, Minimize2, Minus, Plus } from "lucide-react";

import { IllustratedEmptyState } from "@/components/ai-testing/illustrated-empty-state";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { usePreferencesStore } from "@/stores/preferences/preferences-provider";

const LIGHT_BRANCH_COLORS = ["#e11d48", "#ea580c", "#ca8a04", "#16a34a", "#0891b2", "#2563eb", "#7c3aed"];
const DARK_BRANCH_COLORS = ["#fb7185", "#fb923c", "#facc15", "#4ade80", "#22d3ee", "#60a5fa", "#a78bfa"];

export type MindMapTag = {
  text: string;
  style: {
    fill: string;
    fontSize: number;
    height: number;
    paddingX: number;
    radius: number;
  };
};

export type MindMapNodeData = {
  text: string;
  uid?: string;
  nodeId?: string;
  expand?: boolean;
  richText?: boolean;
  tag?: MindMapTag[];
};

export type MindMapNode = {
  data: MindMapNodeData;
  children?: MindMapNode[];
};

export type MindMapItemConfig<T> = {
  getText: (item: T) => string;
  getId: (item: T) => string;
  getGroupKey: (item: T) => string;
  getTag?: (item: T) => MindMapTag | null;
  rootLabel: string;
  groupLabel?: string;
};

export type MindMapTreeProps<T> = {
  active: boolean;
  editable?: boolean;
  items: T[];
  config: MindMapItemConfig<T>;
  selectedId: string | null;
  onEdit?: (id: string, text: string) => Promise<void> | void;
  onSelect: (id: string) => void;
};

function buildMindMapData<T>(items: T[], config: MindMapItemConfig<T>): MindMapNode {
  const { getText, getId, getGroupKey, getTag, rootLabel, groupLabel = "未分模块" } = config;

  const groupedItems = new Map<string, T[]>();
  for (const item of items) {
    const key = getGroupKey(item).trim() || groupLabel;
    groupedItems.set(key, [...(groupedItems.get(key) ?? []), item]);
  }

  return {
    data: { text: rootLabel, uid: "mind-map-root", expand: true },
    children: Array.from(groupedItems, ([groupKey, groupItems], groupIndex) => ({
      data: { text: groupKey, uid: `group-${groupIndex}`, expand: true },
      children: groupItems.map((item) => {
        const tag = getTag ? getTag(item) : null;
        return {
          data: {
            text: getText(item),
            uid: `item-${getId(item)}`,
            nodeId: getId(item),
            expand: false,
            tag: tag
              ? [
                  {
                    text: tag.text,
                    style: {
                      fill: tag.style.fill,
                      fontSize: 11,
                      height: 20,
                      paddingX: 7,
                      radius: 10,
                    },
                  },
                ]
              : undefined,
          },
        };
      }),
    })),
  };
}

function placePriorityTagsBeforeTitles(container: HTMLElement) {
  for (const node of container.querySelectorAll<SVGGElement>(".smm-node")) {
    const priorityText = Array.from(node.querySelectorAll<SVGTextElement>("text")).find((element) =>
      /^P[0-3]$/.test(element.textContent ?? ""),
    );
    const tagItem = priorityText?.parentElement;
    const tagGroup = tagItem?.parentElement;
    const contentGroup = tagGroup?.parentElement;
    const textGroup = contentGroup?.querySelector<SVGGElement>(":scope > g[data-width]");
    const tagRect = tagItem?.querySelector<SVGRectElement>("rect");
    if (!tagGroup || !textGroup || !tagRect) continue;

    const tagX = Number(tagRect.getAttribute("x") ?? 0);
    const tagWidth = Number(tagRect.getAttribute("width") ?? 0);
    const textWidth = Number(textGroup.getAttribute("data-width") ?? 0);
    const gap = Math.max(0, tagX - textWidth);
    textGroup.setAttribute("transform", `translate(${tagWidth + gap} 0)`);
    tagGroup.setAttribute("transform", `translate(${-tagX} 0)`);
  }
}

export function MindMapTree<T>({
  active,
  editable = false,
  items,
  config,
  selectedId,
  onEdit,
  onSelect,
}: MindMapTreeProps<T>) {
  const isDark = usePreferencesStore((state) => state.themeMode === "dark");
  const containerRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<SimpleMindMapInstance | null>(null);
  const onSelectRef = useRef(onSelect);
  const onEditRef = useRef(onEdit);
  const selectedIdRef = useRef(selectedId);
  const [rendering, setRendering] = useState(true);
  const [scale, setScale] = useState(1);
  const [fullscreen, setFullscreen] = useState(false);
  const data = useMemo(() => buildMindMapData(items, config), [items, config]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setFullscreen(document.fullscreenElement === containerRef.current?.parentElement);
      requestAnimationFrame(() => {
        const container = containerRef.current;
        if (!container?.isConnected || container.clientWidth === 0 || container.clientHeight === 0) return;
        instanceRef.current?.resize();
        instanceRef.current?.view.fit();
      });
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    onEditRef.current = onEdit;
  }, [onEdit]);

  useEffect(() => {
    selectedIdRef.current = selectedId;
    if (!selectedId || !instanceRef.current) return;
    instanceRef.current.renderer.findNodeByUid(`item-${selectedId}`)?.active();
  }, [selectedId]);

  useEffect(() => {
    if (!active) return;

    let disposed = false;
    let mindMap: SimpleMindMapInstance | null = null;
    let removeListeners: (() => void) | null = null;
    let resizeObserver: ResizeObserver | null = null;
    const frameIds = new Set<number>();

    const scheduleFrame = (callback: () => void) => {
      const frameId = requestAnimationFrame(() => {
        frameIds.delete(frameId);
        callback();
      });
      frameIds.add(frameId);
    };

    async function renderMindMap() {
      const container = containerRef.current;
      if (!container || container.clientWidth === 0 || container.clientHeight === 0) {
        setRendering(false);
        return;
      }

      let initialRenderPending = true;

      instanceRef.current?.destroy();
      instanceRef.current = null;
      container.replaceChildren();
      setRendering(true);

      const [{ default: MindMap }, { default: RainbowLines }] = await Promise.all([
        import("simple-mind-map"),
        import("simple-mind-map/src/plugins/RainbowLines.js"),
      ]);
      if (disposed || !containerRef.current) return;

      const registerPlugin = MindMap.usePlugin;
      registerPlugin(RainbowLines);

      mindMap = new MindMap({
        el: containerRef.current,
        data,
        layout: "logicalStructure",
        readonly: !editable,
        beforeTextEdit: (node) => Boolean(node.getData("nodeId")),
        customCheckEnableShortcut: (event) =>
          event.target instanceof HTMLElement && event.target.classList.contains("smm-node-edit-wrap"),
        fit: false,
        mousewheelAction: "move",
        enableFreeDrag: true,
        textAutoWrapWidth: 300,
        expandBtnSize: 16,
        expandBtnStyle: {
          color: isDark ? "#d4d4d8" : "#475569",
          fill: isDark ? "#262626" : "#ffffff",
          fontSize: 11,
          strokeColor: isDark ? "#525252" : "#cbd5e1",
        },
        nodeTextEditZIndex: 10,
        rainbowLinesConfig: {
          open: true,
          colorsList: isDark ? DARK_BRANCH_COLORS : LIGHT_BRANCH_COLORS,
        },
        themeConfig: {
          backgroundColor: isDark ? "#171717" : "#fcfdfe",
          lineColor: isDark ? "#64748b" : "#94a3b8",
          lineWidth: 2,
          lineStyle: "curve",
          rootLineKeepSameInCurve: true,
          rootLineStartPositionKeepSameInCurve: true,
          nodeUseLineStyle: false,
          root: {
            fillColor: isDark ? "#e5e7eb" : "#1683ff",
            color: isDark ? "#171717" : "#ffffff",
            fontFamily: '"Noto Sans SC", "PingFang SC", sans-serif',
            borderColor: isDark ? "#e5e7eb" : "#1683ff",
            borderWidth: 0,
            borderRadius: 8,
            paddingX: 16,
            paddingY: 10,
            fontSize: 18,
            fontWeight: "600",
          },
          second: {
            fillColor: isDark ? "#172a46" : "#eaf2ff",
            color: isDark ? "#d9e8ff" : "#204a78",
            fontFamily: '"Noto Sans SC", "PingFang SC", sans-serif',
            borderColor: isDark ? "#315a86" : "#c8dcff",
            borderWidth: 1,
            borderRadius: 6,
            marginX: 72,
            marginY: 30,
            paddingX: 13,
            paddingY: 7,
            fontSize: 16,
            fontWeight: "500",
          },
          node: {
            fillColor: "transparent",
            color: isDark ? "#e5e7eb" : "#20252d",
            fontFamily: '"Noto Sans SC", "PingFang SC", sans-serif',
            borderColor: "transparent",
            borderWidth: 0,
            borderRadius: 4,
            marginX: 48,
            marginY: 8,
            paddingX: 8,
            paddingY: 5,
            fontSize: 14,
          },
        },
      });
      const isCurrentInstance = () =>
        !disposed &&
        instanceRef.current === mindMap &&
        container.isConnected &&
        container.clientWidth > 0 &&
        container.clientHeight > 0;
      const handleRenderEnd = () => {
        if (!isCurrentInstance()) return;
        const currentSelectedId = selectedIdRef.current;
        if (currentSelectedId) {
          mindMap?.renderer.findNodeByUid(`item-${currentSelectedId}`)?.active();
        }
        scheduleFrame(() => {
          if (!isCurrentInstance() || !mindMap) return;
          if (initialRenderPending) {
            initialRenderPending = false;
            mindMap.resize();
            mindMap.view.fit();
          }
          placePriorityTagsBeforeTitles(container);
          setRendering(false);
        });
      };
      const handleNodeClick = (node: { getData(key: string): unknown }) => {
        const nodeId = node.getData("nodeId");
        if (typeof nodeId === "string" && nodeId) onSelectRef.current(nodeId);
      };
      const handleScale = (nextScale: number) => setScale(nextScale);
      const handleTextEditEnd = (
        _editor: HTMLElement,
        _activeNodes: unknown[],
        node: { active(): void; getData(key: string): unknown },
      ) => {
        const nodeId = node.getData("nodeId");
        const nextText = node.getData("text");
        if (typeof nodeId !== "string" || !nodeId || typeof nextText !== "string") return;

        const previousText = items.find((item) => config.getId(item) === nodeId);
        if (!previousText || config.getText(previousText) === nextText.trim()) return;

        void Promise.resolve(onEditRef.current?.(nodeId, nextText.trim())).catch(() => {
          if (!mindMap) return;
          mindMap.execCommand("SET_NODE_TEXT", node, config.getText(previousText));
        });
      };

      mindMap.on("node_tree_render_end", handleRenderEnd);
      mindMap.on("node_click", handleNodeClick);
      mindMap.on("scale", handleScale);
      mindMap.on("hide_text_edit", handleTextEditEnd);
      removeListeners = () => {
        mindMap?.off("node_tree_render_end", handleRenderEnd);
        mindMap?.off("node_click", handleNodeClick);
        mindMap?.off("scale", handleScale);
        mindMap?.off("hide_text_edit", handleTextEditEnd);
      };
      instanceRef.current = mindMap;
    }

    const container = containerRef.current;
    if (!container) {
      setRendering(false);
      return;
    }

    if (container.clientWidth > 0 && container.clientHeight > 0) {
      void renderMindMap();
    } else {
      resizeObserver = new ResizeObserver(() => {
        if (container.clientWidth > 0 && container.clientHeight > 0) {
          if (resizeObserver) {
            resizeObserver.disconnect();
            resizeObserver = null;
          }
          void renderMindMap();
        }
      });
      resizeObserver.observe(container);
    }

    return () => {
      disposed = true;
      for (const frameId of frameIds) cancelAnimationFrame(frameId);
      frameIds.clear();
      if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = null;
      }
      if (mindMap) {
        removeListeners?.();
        mindMap.destroy();
      }
      if (instanceRef.current === mindMap) instanceRef.current = null;
    };
  }, [active, config, data, editable, isDark, items]);

  function fitMindMap() {
    instanceRef.current?.view.fit();
  }

  async function toggleFullscreen() {
    const wrapper = containerRef.current?.parentElement;
    if (!wrapper) return;
    if (document.fullscreenElement) {
      await document.exitFullscreen();
    } else {
      await wrapper.requestFullscreen();
    }
  }

  if (items.length === 0) {
    return (
      <IllustratedEmptyState
        className="min-h-0 flex-1 bg-[#fbfcfe] dark:bg-background"
        description="暂无数据可展示。"
        title="暂无可展示的内容"
      />
    );
  }

  return (
    <div className="relative min-h-0 flex-1 overflow-hidden bg-[#fbfcfe] dark:bg-background [&_.smm-quick-create-child-btn]:hidden">
      <div className="pointer-events-none absolute top-4 left-4 z-10 flex items-center gap-2 rounded-lg border bg-white/90 px-3 py-2 text-slate-500 text-xs shadow-sm backdrop-blur dark:bg-card/90 dark:text-muted-foreground dark:shadow-none">
        {rendering ? <Loader2 className="size-3.5 animate-spin" /> : null}
        {rendering
          ? "正在绘制脑图"
          : editable
            ? "双指移动 · 捏合缩放 · 拖动画布 · 双击测试要点编辑"
            : "双指移动 · 捏合缩放 · 拖动画布 · 点击节点查看详情"}
      </div>
      <div className="absolute top-4 right-4 z-10">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              aria-label={fullscreen ? "退出全屏" : "全屏查看"}
              className="border-slate-200 bg-white/90 text-slate-600 shadow-sm backdrop-blur hover:bg-white hover:text-slate-950 dark:border-border dark:bg-card/90 dark:text-muted-foreground dark:shadow-none dark:hover:bg-muted dark:hover:text-foreground"
              disabled={rendering}
              onClick={() => void toggleFullscreen()}
              size="icon"
              type="button"
              variant="outline"
            >
              {fullscreen ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="left">{fullscreen ? "退出全屏" : "全屏查看"}</TooltipContent>
        </Tooltip>
      </div>
      <div
        aria-label="脑图缩放工具"
        className="absolute right-4 bottom-4 z-10 flex items-center overflow-hidden rounded-lg border border-slate-200 bg-white/90 shadow-sm backdrop-blur dark:border-border dark:bg-card/90 dark:shadow-none"
        role="toolbar"
      >
        <MindMapToolButton disabled={rendering} label="缩小" onClick={() => instanceRef.current?.view.narrow()}>
          <Minus />
        </MindMapToolButton>
        <button
          aria-label="适应画布"
          className="h-8 min-w-14 border-slate-200 border-x px-2 font-mono text-slate-600 text-xs transition-colors hover:bg-slate-50 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-inset disabled:pointer-events-none disabled:opacity-50 dark:border-border dark:text-muted-foreground dark:hover:bg-muted dark:hover:text-foreground"
          disabled={rendering}
          onClick={fitMindMap}
          title="适应画布"
          type="button"
        >
          {Math.round(scale * 100)}%
        </button>
        <MindMapToolButton disabled={rendering} label="放大" onClick={() => instanceRef.current?.view.enlarge()}>
          <Plus />
        </MindMapToolButton>
        <div className="h-4 w-px bg-slate-200 dark:bg-border" />
        <MindMapToolButton disabled={rendering} label="适应画布" onClick={fitMindMap}>
          <Expand />
        </MindMapToolButton>
      </div>
      <div className="h-full min-h-0 w-full" ref={containerRef} />
    </div>
  );
}

function MindMapToolButton({
  children,
  disabled,
  label,
  onClick,
}: {
  children: ReactNode;
  disabled: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          aria-label={label}
          className="flex size-8 items-center justify-center text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-inset disabled:pointer-events-none disabled:opacity-50 dark:text-muted-foreground dark:hover:bg-muted dark:hover:text-foreground [&_svg]:size-4"
          disabled={disabled}
          onClick={onClick}
          type="button"
        >
          {children}
        </button>
      </TooltipTrigger>
      <TooltipContent side="top">{label}</TooltipContent>
    </Tooltip>
  );
}
