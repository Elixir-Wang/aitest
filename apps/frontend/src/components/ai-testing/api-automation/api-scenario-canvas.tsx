"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import dagre from "@dagrejs/dagre";
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
};

type ScenarioNode = Node<ScenarioNodeData>;

const nodeTypes = { scenario: ScenarioNodeCard, terminal: TerminalNode };

export function ApiScenarioCanvas({
  endpoints,
  steps,
  activeStepId,
  onSelectStep,
  onClearSelection,
  onAddUtilityStep,
  onOpenAssetPicker,
}: ApiScenarioCanvasProps) {
  const initial = useMemo(() => buildCanvasGraph(steps, endpoints, activeStepId), [endpoints, steps, activeStepId]);
  const [nodes, setNodes, onNodesChange] = useNodesState<ScenarioNode>(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [paletteOpen, setPaletteOpen] = useState(true);
  const flowInstance = useRef<ReactFlowInstance<ScenarioNode> | null>(null);

  useEffect(() => {
    setNodes((current) => {
      const positions = new Map(current.map((node) => [node.id, node.position]));
      return buildCanvasGraph(steps, endpoints, activeStepId, positions).nodes;
    });
    setEdges(buildCanvasGraph(steps, endpoints, activeStepId).edges);
  }, [activeStepId, endpoints, setEdges, setNodes, steps]);

  useEffect(() => {
    if (!flowInstance.current) return;
    window.requestAnimationFrame(() =>
      flowInstance.current?.fitView({ padding: 0.24, minZoom: nodes.length > 2 ? 0.35 : 0.5, maxZoom: 1.2 }),
    );
  }, [nodes.length]);

  const handleAutoLayout = useCallback(() => {
    const graph = buildCanvasGraph(steps, endpoints, activeStepId);
    setNodes(layoutCanvasNodes(graph.nodes, graph.edges));
    setEdges(graph.edges);
  }, [activeStepId, endpoints, setEdges, setNodes, steps]);

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
      <div className="relative h-full min-h-0 min-w-0 bg-[radial-gradient(circle_at_15%_20%,color-mix(in_srgb,var(--primary),transparent_93%),transparent_34%),var(--background)] dark:bg-[radial-gradient(circle_at_15%_20%,color-mix(in_srgb,var(--primary),transparent_88%),transparent_34%),var(--background)]">
        <ReactFlow
          className="api-scenario-flow h-full w-full"
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.24, minZoom: 0.35, maxZoom: 1.2 }}
          nodeTypes={nodeTypes}
          nodes={nodes}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          onNodesChange={onNodesChange}
          onPaneClick={onClearSelection}
          onInit={(instance) => {
            flowInstance.current = instance;
            window.requestAnimationFrame(() => instance.fitView({ padding: 0.24, minZoom: 0.35, maxZoom: 1.2 }));
          }}
          proOptions={{ hideAttribution: true }}
          panOnScroll
          panOnScrollMode={PanOnScrollMode.Free}
          panOnScrollSpeed={0.8}
          zoomOnScroll={false}
        >
          <Background color="color-mix(in srgb, var(--border), transparent 30%)" gap={22} size={1} />
          <Controls showInteractive={false} />
          <MiniMap
            className="!bottom-4 !right-4 !m-0 !h-[108px] !w-[180px] !overflow-hidden !rounded-lg !border !bg-card/90"
            nodeColor={(node) => (node.data?.kind === "step" ? "var(--primary)" : "#94a3b8")}
            pannable
            zoomable
            nodeStrokeColor="var(--border)"
          />
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
            <span className="text-muted-foreground">{steps.length} 个节点 · 可拖拽调整布局</span>
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
      <Handle className="!size-2 !border-2 !border-card !bg-primary" position={Position.Left} type="target" />
      <Handle className="!size-2 !border-2 !border-card !bg-primary" position={Position.Right} type="source" />
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
        <Badge className="font-mono text-[9px]" variant="outline">
          {method}
        </Badge>
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
        <Handle className="!size-2 !border-2 !border-card !bg-primary" position={Position.Right} type="source" />
      ) : null}
      {data.kind === "end" ? (
        <Handle className="!size-2 !border-2 !border-card !bg-primary" position={Position.Left} type="target" />
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
  return { nodes: hasAllPositions ? nodes : layoutCanvasNodes(nodes, edges), edges };
}

function layoutCanvasNodes(nodes: ScenarioNode[], edges: Edge[]) {
  const graph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: "LR", ranksep: 76, nodesep: 44, marginx: 28, marginy: 28 });
  for (const node of nodes) {
    const terminal = node.data.kind !== "step";
    graph.setNode(node.id, { width: terminal ? 64 : 258, height: terminal ? 64 : 112 });
  }
  for (const edge of edges) graph.setEdge(edge.source, edge.target);
  dagre.layout(graph);
  return nodes.map((node) => {
    const position = graph.node(node.id);
    const terminal = node.data.kind !== "step";
    const width = terminal ? 64 : 258;
    const height = terminal ? 64 : 112;
    return { ...node, position: { x: position.x - width / 2, y: position.y - height / 2 } };
  });
}
