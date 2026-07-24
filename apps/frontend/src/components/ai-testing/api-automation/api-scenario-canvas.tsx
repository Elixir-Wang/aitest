"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import "@xyflow/react/dist/style.css";
import {
  Background,
  Controls,
  type Edge,
  Handle,
  MarkerType,
  MiniMap,
  type Node,
  type NodeProps,
  PanOnScrollMode,
  Position,
  ReactFlow,
  type ReactFlowInstance,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import {
  Braces,
  CheckCircle2,
  Clock3,
  GitBranch,
  PanelLeftClose,
  PanelLeftOpen,
  Play,
  Plus,
  RefreshCw,
  Variable,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ApiAutomationEndpoint, ApiAutomationScenarioStep } from "@/lib/api-client";
import { cn } from "@/lib/utils";

type ApiScenarioCanvasProps = {
  endpoints: ApiAutomationEndpoint[];
  steps: ApiAutomationScenarioStep[];
  activeStepId: string;
  onSelectStep: (stepId: string) => void;
  onClearSelection: () => void;
  onAddUtilityStep: (stepType: Exclude<ApiAutomationScenarioStep["step_type"], "api_request">) => void;
  onOpenAssetPicker: () => void;
};

type ScenarioNodeData = {
  kind: "start" | "end" | "step";
  step?: ApiAutomationScenarioStep;
  endpoint?: ApiAutomationEndpoint;
  index?: number;
  selected?: boolean;
  inputPosition?: Position;
  outputPosition?: Position;
};

type ScenarioNode = Node<ScenarioNodeData>;

const nodeTypes = { scenario: ScenarioNodeCard, terminal: TerminalNode };

const STEP_NODE_WIDTH = 258;
const STEP_NODE_HEIGHT = 112;
const TERMINAL_NODE_SIZE = 64;
const COLUMN_GAP = 48;
const ROW_GAP = 72;
const TERMINAL_GAP = 32;
const CANVAS_MARGIN = 24;
const MIN_READABLE_ZOOM = 0.7;
const DEFAULT_CANVAS_WIDTH = 1200;

export function ApiScenarioCanvas({
  endpoints,
  steps,
  activeStepId,
  onSelectStep,
  onClearSelection,
  onAddUtilityStep,
  onOpenAssetPicker,
}: ApiScenarioCanvasProps) {
  const initial = useMemo(
    () => buildCanvasGraph(steps, endpoints, activeStepId, new Map(), DEFAULT_CANVAS_WIDTH),
    [endpoints, steps, activeStepId],
  );
  const [nodes, setNodes, onNodesChange] = useNodesState<ScenarioNode>(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [paletteOpen, setPaletteOpen] = useState(true);
  const [canvasWidth, setCanvasWidth] = useState(DEFAULT_CANVAS_WIDTH);
  const [layoutMode, setLayoutMode] = useState<"auto" | "manual">("auto");
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const flowInstance = useRef<ReactFlowInstance<ScenarioNode> | null>(null);
  const stepIdsRef = useRef(steps.map((step) => step.id).join("|"));

  const fitCanvas = useCallback(() => {
    window.requestAnimationFrame(() =>
      window.requestAnimationFrame(() =>
        flowInstance.current?.fitView({ padding: 0.04, minZoom: MIN_READABLE_ZOOM, maxZoom: 1 }),
      ),
    );
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setCanvasWidth(Math.round(entry.contentRect.width));
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const stepIds = steps.map((step) => step.id).join("|");
    const structureChanged = stepIds !== stepIdsRef.current;
    setNodes((current) => {
      const positions = structureChanged ? new Map() : new Map(current.map((node) => [node.id, node.position]));
      return buildCanvasGraph(steps, endpoints, activeStepId, positions, canvasWidth).nodes;
    });
    setEdges(buildCanvasGraph(steps, endpoints, activeStepId, new Map(), canvasWidth).edges);
    if (structureChanged) {
      stepIdsRef.current = stepIds;
      setLayoutMode("auto");
      fitCanvas();
    }
  }, [activeStepId, canvasWidth, endpoints, fitCanvas, setEdges, setNodes, steps]);

  useEffect(() => {
    if (layoutMode !== "auto") return;
    setNodes((current) => layoutCanvasNodes(current, canvasWidth));
    fitCanvas();
  }, [canvasWidth, fitCanvas, layoutMode, setNodes]);

  const handleAutoLayout = useCallback(() => {
    const graph = buildCanvasGraph(steps, endpoints, activeStepId, new Map(), canvasWidth);
    setNodes(layoutCanvasNodes(graph.nodes, canvasWidth));
    setEdges(graph.edges);
    setLayoutMode("auto");
    fitCanvas();
  }, [activeStepId, canvasWidth, endpoints, fitCanvas, setEdges, setNodes, steps]);

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: ScenarioNode) => {
      if (node.data.kind === "step") onSelectStep(node.id);
    },
    [onSelectStep],
  );

  return (
    <div
      className={cn(
        "grid h-full min-h-0 min-w-0 flex-1 overflow-hidden",
        paletteOpen ? "grid-cols-[190px_minmax(0,1fr)]" : "grid-cols-1",
      )}
    >
      {paletteOpen ? (
        <CanvasPalette
          onAddUtilityStep={onAddUtilityStep}
          onClose={() => setPaletteOpen(false)}
          onOpenAssetPicker={onOpenAssetPicker}
        />
      ) : null}
      <div
        className="relative h-full min-h-0 min-w-0 bg-[radial-gradient(circle_at_15%_20%,color-mix(in_srgb,var(--primary),transparent_93%),transparent_34%),var(--background)] dark:bg-[radial-gradient(circle_at_15%_20%,color-mix(in_srgb,var(--primary),transparent_88%),transparent_34%),var(--background)]"
        ref={canvasRef}
      >
        <ReactFlow
          className="api-scenario-flow h-full w-full"
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.04, minZoom: MIN_READABLE_ZOOM, maxZoom: 1 }}
          nodeTypes={nodeTypes}
          nodes={nodes}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          onNodesChange={onNodesChange}
          onNodeDragStart={() => setLayoutMode("manual")}
          onNodeDragStop={() => setNodes((current) => orientCanvasNodes(current))}
          onPaneClick={onClearSelection}
          onInit={(instance) => {
            flowInstance.current = instance;
            fitCanvas();
          }}
          proOptions={{ hideAttribution: true }}
          panOnScroll
          panOnScrollMode={PanOnScrollMode.Free}
          panOnScrollSpeed={0.8}
          zoomOnScroll={false}
        >
          <Background color="color-mix(in srgb, var(--border), transparent 30%)" gap={22} size={1} />
          <Controls showInteractive={false} />
          {steps.length > 12 ? (
            <MiniMap
              className="!bottom-4 !right-4 !m-0 !h-[108px] !w-[180px] !overflow-hidden !rounded-lg !border !bg-card/90"
              nodeColor={(node) => (node.data?.kind === "step" ? "var(--primary)" : "#94a3b8")}
              pannable
              zoomable
              nodeStrokeColor="var(--border)"
            />
          ) : null}
        </ReactFlow>
        <div className="absolute top-4 left-4 flex items-center gap-2">
          <Button
            aria-label="展开节点库"
            className="shadow-sm"
            onClick={() => setPaletteOpen(true)}
            size="icon-sm"
            title="展开节点库"
            variant="outline"
          >
            <PanelLeftOpen />
          </Button>
          <div className="pointer-events-none flex items-center gap-2 rounded-lg border bg-card/90 px-3 py-2 text-[11px] shadow-sm backdrop-blur">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            <span className="font-medium">执行路径</span>
            <span className="text-muted-foreground">
              {steps.length} 个节点 · {layoutMode === "auto" ? "已按画布宽度排布" : "手动布局"}
            </span>
          </div>
        </div>
        <Button
          aria-label="自动布局"
          className="absolute top-4 right-4 shadow-sm"
          onClick={handleAutoLayout}
          size="sm"
          variant="outline"
        >
          <GitBranch />
          自动布局
        </Button>
      </div>
    </div>
  );
}

function CanvasPalette({
  onOpenAssetPicker,
  onAddUtilityStep,
  onClose,
}: {
  onOpenAssetPicker: () => void;
  onAddUtilityStep: (stepType: Exclude<ApiAutomationScenarioStep["step_type"], "api_request">) => void;
  onClose: () => void;
}) {
  return (
    <aside className="min-h-0 overflow-y-auto border-r bg-card/75 p-3">
      <div className="flex items-center justify-between gap-2 px-1 py-1">
        <div className="flex min-w-0 items-center gap-2">
          <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
            <Plus className="size-3.5" />
          </span>
          <div className="min-w-0">
            <div className="font-semibold text-xs">添加节点</div>
            <div className="truncate text-[10px] text-muted-foreground">点击添加到画布</div>
          </div>
        </div>
        <Button aria-label="收起节点库" onClick={onClose} size="icon-sm" title="收起节点库" variant="ghost">
          <PanelLeftClose />
        </Button>
      </div>
      <div className="mt-4 space-y-2">
        <PaletteAction icon={Plus} label="接口请求" onClick={onOpenAssetPicker} tone="primary" />
        <PaletteAction icon={Variable} label="数据赋值" onClick={() => onAddUtilityStep("assign")} />
        <PaletteAction icon={GitBranch} label="条件判断" onClick={() => onAddUtilityStep("condition")} />
        <PaletteAction icon={Clock3} label="固定等待" onClick={() => onAddUtilityStep("wait")} />
        <PaletteAction icon={RefreshCw} label="轮询等待" onClick={() => onAddUtilityStep("poll")} />
      </div>
      <div className="mt-6 border-t pt-4">
        <div className="px-2 font-semibold text-[10px] text-muted-foreground uppercase tracking-[0.08em]">画布提示</div>
        <div className="mt-2 space-y-2 text-[11px] text-muted-foreground leading-5">
          <p>选中节点后，在右侧配置请求、变量、响应提取和断言。</p>
          <p>当前画布沿用现有步骤顺序，节点布局不会改变运行语义。</p>
        </div>
      </div>
    </aside>
  );
}

function PaletteAction({
  icon: Icon,
  label,
  onClick,
  tone = "muted",
}: {
  icon: typeof Plus;
  label: string;
  onClick: () => void;
  tone?: "primary" | "muted";
}) {
  return (
    <Button
      className={cn(
        "h-10 w-full justify-start gap-3 px-3 text-xs",
        tone === "primary" && "border-primary/30 bg-primary/8 text-primary hover:bg-primary/12",
      )}
      onClick={onClick}
      variant="outline"
    >
      <Icon className="size-3.5" />
      {label}
    </Button>
  );
}

function ScenarioNodeCard({ data }: NodeProps<ScenarioNode>) {
  const step = data.step;
  const endpoint = data.endpoint;
  if (!step) return null;
  const method = endpoint?.method ?? step.step_type.toUpperCase();
  const isUtility = step.step_type !== "api_request";
  return (
    <div
      className={cn(
        "relative w-[258px] overflow-hidden rounded-xl border bg-card shadow-[0_10px_26px_color-mix(in_srgb,var(--primary),transparent_90%)] transition-shadow",
        data.selected ? "border-primary ring-2 ring-primary/15" : "border-border/90",
      )}
    >
      <Handle
        className="!size-2 !border-2 !border-card !bg-primary"
        position={data.inputPosition ?? Position.Left}
        type="target"
      />
      <Handle
        className="!size-2 !border-2 !border-card !bg-primary"
        position={data.outputPosition ?? Position.Right}
        type="source"
      />
      <div className="flex items-center justify-between border-b bg-muted/25 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <span
            className={cn(
              "grid size-6 place-items-center rounded-md",
              isUtility ? "bg-amber-500/12 text-amber-700 dark:text-amber-200" : "bg-primary/10 text-primary",
            )}
          >
            {step.step_type === "condition" ? <GitBranch className="size-3.5" /> : null}
            {step.step_type === "assign" ? <Variable className="size-3.5" /> : null}
            {step.step_type === "wait" ? <Clock3 className="size-3.5" /> : null}
            {step.step_type === "poll" ? <RefreshCw className="size-3.5" /> : null}
            {step.step_type === "api_request" ? <Play className="size-3.5" /> : null}
          </span>
          <span className="truncate font-medium text-xs">{step.name}</span>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <span className="font-mono font-semibold text-[9px] text-muted-foreground">
            {String((data.index ?? 0) + 1).padStart(2, "0")}
          </span>
          <Badge className="font-mono text-[9px]" variant="outline">
            {method}
          </Badge>
        </div>
      </div>
      <div className="space-y-2 px-3 py-3">
        <div className="truncate font-mono text-[10px] text-muted-foreground">{endpoint?.path ?? "辅助步骤"}</div>
        <div className="flex flex-wrap gap-1">
          {step.bindings.length ? <NodeTag icon={Variable} text={`${step.bindings.length} 个输入`} /> : null}
          {step.extractors.length ? <NodeTag icon={Braces} text={`${step.extractors.length} 个输出`} /> : null}
          {step.assertions.length ? (
            <NodeTag icon={CheckCircle2} text={`${step.assertions.length} 个断言`} success />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function TerminalNode({ data }: NodeProps<ScenarioNode>) {
  return (
    <div className="relative grid size-16 place-items-center rounded-full border border-primary/30 bg-primary/8 text-primary shadow-sm">
      {data.kind === "start" ? (
        <Handle
          className="!size-2 !border-2 !border-card !bg-primary"
          position={data.outputPosition ?? Position.Right}
          type="source"
        />
      ) : null}
      {data.kind === "end" ? (
        <Handle
          className="!size-2 !border-2 !border-card !bg-primary"
          position={data.inputPosition ?? Position.Left}
          type="target"
        />
      ) : null}
      <span className="font-semibold text-[10px]">{data.kind === "start" ? "开始" : "结束"}</span>
    </div>
  );
}

function NodeTag({ icon: Icon, text, success }: { icon: typeof Variable; text: string; success?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded bg-primary/8 px-1.5 py-0.5 text-[9px] text-primary",
        success && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-200",
      )}
    >
      <Icon className="size-2.5" />
      {text}
    </span>
  );
}

function buildCanvasGraph(
  steps: ApiAutomationScenarioStep[],
  endpoints: ApiAutomationEndpoint[],
  activeStepId: string,
  positions = new Map<string, { x: number; y: number }>(),
  canvasWidth = DEFAULT_CANVAS_WIDTH,
) {
  const nodes: ScenarioNode[] = [
    {
      id: "__start__",
      type: "terminal",
      data: { kind: "start" },
      position: positions.get("__start__") ?? { x: 30, y: 170 },
      draggable: false,
    },
    ...steps.map((step, index) => ({
      id: step.id,
      type: "scenario",
      data: {
        kind: "step" as const,
        step,
        endpoint: endpoints.find((endpoint) => endpoint.id === step.endpoint_id),
        index,
        selected: step.id === activeStepId,
      },
      position: positions.get(step.id) ?? { x: 240 + index * 300, y: 140 },
    })),
    {
      id: "__end__",
      type: "terminal",
      data: { kind: "end" },
      position: positions.get("__end__") ?? { x: 360 + steps.length * 300, y: 170 },
      draggable: false,
    },
  ];
  const chain = ["__start__", ...steps.map((step) => step.id), "__end__"];
  const edges: Edge[] = chain.slice(0, -1).map((source, index) => ({
    id: `${source}->${chain[index + 1]}`,
    source,
    target: chain[index + 1],
    type: "smoothstep",
    animated: source !== "__start__" && source === activeStepId,
    markerEnd: { type: MarkerType.ArrowClosed, color: "var(--primary)" },
    style: { stroke: "color-mix(in srgb, var(--primary), transparent 25%)", strokeWidth: 1.5 },
  }));
  const hasAllPositions = nodes.every((node) => positions.has(node.id));
  return { nodes: hasAllPositions ? orientCanvasNodes(nodes) : layoutCanvasNodes(nodes, canvasWidth), edges };
}

function layoutCanvasNodes(nodes: ScenarioNode[], canvasWidth: number) {
  const start = nodes.find((node) => node.data.kind === "start");
  const end = nodes.find((node) => node.data.kind === "end");
  const steps = nodes.filter((node) => node.data.kind === "step");
  if (!start || !end) return nodes;

  if (!steps.length) {
    const centerX = Math.max(CANVAS_MARGIN, canvasWidth / 2 - TERMINAL_NODE_SIZE - TERMINAL_GAP / 2);
    return orientCanvasNodes([
      { ...start, position: { x: centerX, y: CANVAS_MARGIN } },
      { ...end, position: { x: centerX + TERMINAL_NODE_SIZE + TERMINAL_GAP, y: CANVAS_MARGIN } },
    ]);
  }

  const columns = resolveColumnCount(canvasWidth, steps.length);
  if (columns === 1) {
    const stepX = Math.max(CANVAS_MARGIN, (canvasWidth - STEP_NODE_WIDTH) / 2);
    const firstStepY = CANVAS_MARGIN + TERMINAL_NODE_SIZE + TERMINAL_GAP;
    const positionedSteps = steps.map((node, index) => ({
      ...node,
      position: { x: stepX, y: firstStepY + index * (STEP_NODE_HEIGHT + ROW_GAP) },
    }));
    const lastStep = positionedSteps[positionedSteps.length - 1];
    return orientCanvasNodes([
      {
        ...start,
        position: { x: stepX + (STEP_NODE_WIDTH - TERMINAL_NODE_SIZE) / 2, y: CANVAS_MARGIN },
      },
      ...positionedSteps,
      {
        ...end,
        position: {
          x: stepX + (STEP_NODE_WIDTH - TERMINAL_NODE_SIZE) / 2,
          y: lastStep.position.y + STEP_NODE_HEIGHT + TERMINAL_GAP,
        },
      },
    ]);
  }

  const gridWidth = columns * STEP_NODE_WIDTH + (columns - 1) * COLUMN_GAP;
  const gridStartX = Math.max(CANVAS_MARGIN + TERMINAL_NODE_SIZE + TERMINAL_GAP, (canvasWidth - gridWidth) / 2);
  const positionedSteps = steps.map((node, index) => {
    const row = Math.floor(index / columns);
    const columnInRow = index % columns;
    const column = row % 2 === 0 ? columnInRow : columns - 1 - columnInRow;
    return {
      ...node,
      position: {
        x: gridStartX + column * (STEP_NODE_WIDTH + COLUMN_GAP),
        y: CANVAS_MARGIN + row * (STEP_NODE_HEIGHT + ROW_GAP),
      },
    };
  });
  const firstStep = positionedSteps[0];
  const lastStep = positionedSteps[positionedSteps.length - 1];
  const lastRow = Math.floor((positionedSteps.length - 1) / columns);
  const endOnRight = lastRow % 2 === 0;

  return orientCanvasNodes([
    {
      ...start,
      position: {
        x: firstStep.position.x - TERMINAL_GAP - TERMINAL_NODE_SIZE,
        y: firstStep.position.y + (STEP_NODE_HEIGHT - TERMINAL_NODE_SIZE) / 2,
      },
    },
    ...positionedSteps,
    {
      ...end,
      position: {
        x: endOnRight
          ? lastStep.position.x + STEP_NODE_WIDTH + TERMINAL_GAP
          : lastStep.position.x - TERMINAL_GAP - TERMINAL_NODE_SIZE,
        y: lastStep.position.y + (STEP_NODE_HEIGHT - TERMINAL_NODE_SIZE) / 2,
      },
    },
  ]);
}

function resolveColumnCount(canvasWidth: number, stepCount: number) {
  const logicalCanvasWidth = canvasWidth / MIN_READABLE_ZOOM;
  const widthForSteps = logicalCanvasWidth - CANVAS_MARGIN * 2;
  const columns = Math.floor((widthForSteps + COLUMN_GAP) / (STEP_NODE_WIDTH + COLUMN_GAP));
  return Math.max(1, Math.min(4, stepCount, columns));
}

function orientCanvasNodes(nodes: ScenarioNode[]) {
  return nodes.map((node, index) => ({
    ...node,
    data: {
      ...node.data,
      inputPosition: index > 0 ? positionToward(node, nodes[index - 1]) : undefined,
      outputPosition: index < nodes.length - 1 ? positionToward(node, nodes[index + 1]) : undefined,
    },
  }));
}

function positionToward(node: ScenarioNode, other: ScenarioNode) {
  const nodeCenter = getNodeCenter(node);
  const otherCenter = getNodeCenter(other);
  const horizontalDistance = Math.abs(otherCenter.x - nodeCenter.x);
  const verticalDistance = Math.abs(otherCenter.y - nodeCenter.y);
  if (verticalDistance > horizontalDistance) return otherCenter.y > nodeCenter.y ? Position.Bottom : Position.Top;
  return otherCenter.x > nodeCenter.x ? Position.Right : Position.Left;
}

function getNodeCenter(node: ScenarioNode) {
  const terminal = node.data.kind !== "step";
  const width = terminal ? TERMINAL_NODE_SIZE : STEP_NODE_WIDTH;
  const height = terminal ? TERMINAL_NODE_SIZE : STEP_NODE_HEIGHT;
  return { x: node.position.x + width / 2, y: node.position.y + height / 2 };
}
