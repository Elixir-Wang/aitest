"use client";

import { useEffect, useId, useRef, useState } from "react";

import type { GraphLabel } from "@dagrejs/dagre";
import dagre from "@dagrejs/dagre";
import { Copy } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type MarkdownPreviewProps = {
  className?: string;
  content: string;
  emptyClassName?: string;
  emptyText?: string;
};

export function MarkdownPreview({
  className,
  content,
  emptyClassName,
  emptyText = "当前版本暂无可展示内容。",
}: MarkdownPreviewProps) {
  const markdown = content.trim();

  if (!markdown) {
    return <div className={cn("markdown-preview markdown-preview-empty", className, emptyClassName)}>{emptyText}</div>;
  }

  return (
    <article className={cn("markdown-preview", className)}>
      <ReactMarkdown
        components={{
          pre: ({ children }) => {
            const child = Array.isArray(children) ? children[0] : children;
            if (
              typeof child === "object" &&
              child !== null &&
              "props" in child &&
              typeof child.props === "object" &&
              child.props !== null &&
              "className" in child.props &&
              /language-mermaid/.test(String(child.props.className || ""))
            ) {
              const source = String(child.props.children || "").replace(/\n$/, "");
              return <MermaidDiagram source={source} />;
            }
            return <pre>{children}</pre>;
          },
          code: ({ children, className }) => {
            const language = /language-(\w+)/.exec(className || "")?.[1];
            const source = String(children).replace(/\n$/, "");
            if (language === "mermaid") {
              return <MermaidDiagram source={source} />;
            }
            return <code className={className}>{children}</code>;
          },
          table: ({ children }) => (
            <div className="markdown-table-scroll">
              <table>{children}</table>
            </div>
          ),
        }}
        remarkPlugins={[remarkGfm]}
      >
        {markdown}
      </ReactMarkdown>
    </article>
  );
}

type MermaidDiagramProps = {
  source: string;
};

function MermaidDiagram({ source }: MermaidDiagramProps) {
  const flowchart = parseSimpleFlowchart(source);
  if (flowchart) {
    return <SimpleFlowchartDiagram chart={flowchart} source={source} />;
  }

  return <MermaidSvgDiagram source={source} />;
}

function MermaidSvgDiagram({ source }: MermaidDiagramProps) {
  const reactId = useId();
  const isDarkMode = useDarkMode();
  const [svg, setSvg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function renderDiagram() {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "base",
          flowchart: {
            htmlLabels: true,
            nodeSpacing: 50,
            rankSpacing: 60,
            useMaxWidth: true,
          },
          themeVariables: getMermaidThemeVariables(isDarkMode),
        });
        const id = `mermaid-${reactId.replace(/[^a-zA-Z0-9_-]/g, "")}`;
        const result = await mermaid.render(id, source);
        if (!cancelled) {
          setSvg(result.svg);
          setError("");
        }
      } catch {
        if (!cancelled) {
          setSvg("");
          setError("流程图渲染失败");
        }
      }
    }

    void renderDiagram();

    return () => {
      cancelled = true;
    };
  }, [isDarkMode, reactId, source]);

  if (error) {
    return (
      <pre className="markdown-mermaid-fallback">
        <code>{source}</code>
      </pre>
    );
  }

  if (!svg) {
    return <div className="markdown-mermaid-loading">流程图生成中...</div>;
  }

  return (
    <div className="markdown-mermaid-card">
      <div className="markdown-mermaid-actions">
        <Button size="sm" type="button" variant="ghost" onClick={() => copyMermaidSource(source)}>
          <Copy />
          复制源码
        </Button>
      </div>
      <MermaidSvg className="markdown-mermaid" svg={svg} />
    </div>
  );
}

type SimpleFlowchart = {
  direction: "TD" | "LR";
  edges: Array<{ from: string; to: string }>;
  nodes: Array<{ id: string; label: string }>;
};

type PositionedNode = SimpleFlowchart["nodes"][number] & {
  height: number;
  width: number;
  x: number;
  y: number;
};

type PositionedEdge = {
  from: string;
  points: Array<{ x: number; y: number }>;
  to: string;
};

type FlowNodeMetrics = {
  height: number;
  width: number;
};

type FlowLayoutNode = FlowNodeMetrics & {
  x: number;
  y: number;
};

type FlowEdgeLabel = Record<string, unknown>;

type FlowLayoutEdge = FlowEdgeLabel & {
  points: Array<{ x: number; y: number }>;
};

const FLOW_NODE_HEIGHT = 58;
const FLOW_MIN_NODE_WIDTH = 190;
const FLOW_MAX_NODE_WIDTH = 520;
const FLOW_PADDING = 36;

function SimpleFlowchartDiagram({ chart, source }: { chart: SimpleFlowchart; source: string }) {
  const layout = layoutSimpleFlowchart(chart);
  const shellRef = useRef<HTMLDivElement | null>(null);
  const [availableWidth, setAvailableWidth] = useState(0);
  const scale = availableWidth > 0 && layout.width > availableWidth ? availableWidth / layout.width : 1;
  const scaledHeight = layout.height * scale;
  const scaledWidth = layout.width * scale;

  useEffect(() => {
    if (!shellRef.current) {
      return;
    }
    const observer = new ResizeObserver(([entry]) => {
      setAvailableWidth(entry.contentRect.width);
    });
    observer.observe(shellRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="markdown-mermaid-card">
      <div className="markdown-mermaid-actions">
        <Button size="sm" type="button" variant="ghost" onClick={() => copyMermaidSource(source)}>
          <Copy />
          复制源码
        </Button>
      </div>
      <div className="markdown-flowchart-shell" ref={shellRef}>
        <div className="markdown-flowchart-viewport" style={{ height: scaledHeight, width: scaledWidth }}>
          <div
            className="markdown-flowchart"
            style={{
              height: layout.height,
              transform: `scale(${scale})`,
              transformOrigin: "top left",
              width: layout.width,
            }}
          >
            <svg
              aria-hidden="true"
              className="markdown-flowchart-edges"
              height={layout.height}
              viewBox={`0 0 ${layout.width} ${layout.height}`}
              width={layout.width}
            >
              <defs>
                <marker id="markdown-flowchart-arrow" markerHeight="8" markerWidth="8" orient="auto" refX="7" refY="4">
                  <path d="M 0 0 L 8 4 L 0 8 z" />
                </marker>
              </defs>
              {layout.edges.map((edge) => (
                <path d={buildFlowEdgePath(edge.points)} key={`${edge.from}-${edge.to}`} />
              ))}
            </svg>
            {layout.nodes.map((node) => (
              <div
                className="markdown-flowchart-node"
                key={node.id}
                style={{ borderRadius: 6, height: node.height, left: node.x, top: node.y, width: node.width }}
              >
                {node.label}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function useDarkMode() {
  const [isDarkMode, setIsDarkMode] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    const syncTheme = () => {
      setIsDarkMode(root.classList.contains("dark"));
    };
    syncTheme();

    const observer = new MutationObserver(syncTheme);
    observer.observe(root, { attributeFilter: ["class"], attributes: true });

    return () => observer.disconnect();
  }, []);

  return isDarkMode;
}

function getMermaidThemeVariables(isDarkMode: boolean) {
  return {
    background: isDarkMode ? "#18181b" : "#ffffff",
    mainBkg: isDarkMode ? "#1f2937" : "#eef2ff",
    primaryColor: isDarkMode ? "#1f2937" : "#eef2ff",
    primaryTextColor: isDarkMode ? "#f8fafc" : "#172033",
    primaryBorderColor: isDarkMode ? "#64748b" : "#7c8db5",
    secondaryColor: isDarkMode ? "#172033" : "#f6f8fb",
    tertiaryColor: isDarkMode ? "#111827" : "#ffffff",
    lineColor: isDarkMode ? "#94a3b8" : "#667085",
    textColor: isDarkMode ? "#f8fafc" : "#172033",
    nodeTextColor: isDarkMode ? "#f8fafc" : "#172033",
    fontFamily: '"Noto Sans SC", Arial, sans-serif',
    fontSize: "14px",
  };
}

function MermaidSvg({ className, svg }: { className: string; svg: string }) {
  const containerRef = useMermaidSvg(svg);

  return (
    <div
      ref={containerRef}
      className={className}
      data-mermaid-mode={className === "markdown-mermaid" ? "inline" : "viewer"}
    />
  );
}

function useMermaidSvg(svg: string) {
  const [container, setContainer] = useState<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!container) {
      return;
    }
    container.replaceChildren();
    const template = document.createElement("template");
    template.innerHTML = svg.trim();
    const fragment = template.content.cloneNode(true);
    if (fragment instanceof DocumentFragment) {
      fixMermaidNodeLabels(fragment);
    }
    container.append(fragment);
    trimMermaidViewBox(container);
  }, [container, svg]);

  return setContainer;
}

function copyMermaidSource(source: string) {
  void navigator.clipboard?.writeText(source);
}

function parseSimpleFlowchart(source: string): SimpleFlowchart | null {
  const lines = source
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const header = lines[0]?.match(/^flowchart\s+(TD|LR)$/i);
  if (!header) {
    return null;
  }

  const nodes = new Map<string, string>();
  const edges: SimpleFlowchart["edges"] = [];

  for (const line of lines.slice(1)) {
    const edgeMatch = line.match(/^(\w+)(?:\["([^"]+)"\])?\s*-->\s*(\w+)(?:\["([^"]+)"\])?$/);
    const nodeMatch = line.match(/^(\w+)\["([^"]+)"\]$/);
    if (edgeMatch) {
      const [, from, fromLabel, to, toLabel] = edgeMatch;
      if (fromLabel) {
        nodes.set(from, stripHtmlBreaks(fromLabel));
      }
      if (toLabel) {
        nodes.set(to, stripHtmlBreaks(toLabel));
      }
      if (!nodes.has(from)) {
        nodes.set(from, from);
      }
      if (!nodes.has(to)) {
        nodes.set(to, to);
      }
      edges.push({ from, to });
    } else if (nodeMatch) {
      const [, id, label] = nodeMatch;
      nodes.set(id, stripHtmlBreaks(label));
    } else {
      return null;
    }
  }

  if (!nodes.size || !edges.length) {
    return null;
  }

  return {
    direction: header[1].toUpperCase() as "TD" | "LR",
    edges,
    nodes: Array.from(nodes, ([id, label]) => ({ id, label })),
  };
}

function stripHtmlBreaks(label: string) {
  return label.replace(/<br\s*\/?>/gi, " ");
}

function layoutSimpleFlowchart(chart: SimpleFlowchart) {
  const graph = new dagre.graphlib.Graph<GraphLabel, FlowNodeMetrics, FlowEdgeLabel>();
  graph.setGraph({
    edgesep: 24,
    marginx: FLOW_PADDING,
    marginy: FLOW_PADDING,
    nodesep: 72,
    rankdir: chart.direction === "TD" ? "TB" : "LR",
    ranksep: 60,
  });
  graph.setDefaultEdgeLabel(() => ({}));

  const nodeById = new Map(chart.nodes.map((node) => [node.id, node]));
  const nodeMetrics = new Map(chart.nodes.map((node) => [node.id, getFlowNodeMetrics(node.label)]));
  for (const node of chart.nodes) {
    graph.setNode(node.id, nodeMetrics.get(node.id) || { height: FLOW_NODE_HEIGHT, width: FLOW_MIN_NODE_WIDTH });
  }
  for (const edge of chart.edges) {
    graph.setEdge(edge.from, edge.to);
  }

  dagre.layout(graph);

  const nodes = chart.nodes.map((node) => {
    const graphNode = graph.node(node.id) as FlowLayoutNode;
    const metrics = nodeMetrics.get(node.id) || { height: FLOW_NODE_HEIGHT, width: FLOW_MIN_NODE_WIDTH };
    return {
      ...node,
      ...metrics,
      x: graphNode.x - metrics.width / 2,
      y: graphNode.y - metrics.height / 2,
    };
  });
  const edges = chart.edges
    .map((edge) => {
      const graphEdge = graph.edge(edge.from, edge.to) as FlowLayoutEdge | undefined;
      if (!graphEdge?.points?.length || !nodeById.has(edge.from) || !nodeById.has(edge.to)) {
        return null;
      }
      return { ...edge, points: graphEdge.points };
    })
    .filter((edge): edge is PositionedEdge => edge !== null);
  const bounds = getFlowBounds(nodes, edges);
  const offsetX = FLOW_PADDING - bounds.minX;
  const offsetY = FLOW_PADDING - bounds.minY;
  const positionedNodes = nodes.map((node) => ({ ...node, x: node.x + offsetX, y: node.y + offsetY }));
  const positionedEdges = edges.map((edge) => ({
    ...edge,
    points: edge.points.map((point) => ({ x: point.x + offsetX, y: point.y + offsetY })),
  }));

  return {
    direction: chart.direction,
    edges: positionedEdges,
    height: Math.ceil(bounds.maxY - bounds.minY + FLOW_PADDING * 2),
    nodeMap: new Map(positionedNodes.map((node) => [node.id, node])),
    nodes: positionedNodes,
    width: Math.ceil(bounds.maxX - bounds.minX + FLOW_PADDING * 2),
  };
}

function buildFlowEdgePath(points: PositionedEdge["points"]) {
  if (!points.length) {
    return "";
  }
  const [firstPoint, ...restPoints] = points;
  return `M ${firstPoint.x} ${firstPoint.y} ${restPoints.map((point) => `L ${point.x} ${point.y}`).join(" ")}`;
}

function getFlowNodeMetrics(label: string) {
  const weightedLength = Array.from(label).reduce((total, char) => total + (char.charCodeAt(0) > 127 ? 1.15 : 0.62), 0);
  return {
    height: FLOW_NODE_HEIGHT,
    width: Math.min(FLOW_MAX_NODE_WIDTH, Math.max(FLOW_MIN_NODE_WIDTH, Math.ceil(weightedLength * 18 + 56))),
  };
}

function getFlowBounds(nodes: PositionedNode[], edges: PositionedEdge[]) {
  const xs = nodes.flatMap((node) => [node.x, node.x + node.width]);
  const ys = nodes.flatMap((node) => [node.y, node.y + node.height]);
  for (const edge of edges) {
    xs.push(...edge.points.map((point) => point.x));
    ys.push(...edge.points.map((point) => point.y));
  }
  return {
    maxX: Math.max(...xs),
    maxY: Math.max(...ys),
    minX: Math.min(...xs),
    minY: Math.min(...ys),
  };
}

function fixMermaidNodeLabels(fragment: DocumentFragment) {
  fragment.querySelectorAll<SVGGElement>(".node").forEach((node) => {
    const rect = node.querySelector<SVGRectElement>("rect.label-container");
    const label = node.querySelector<SVGGElement>("g.label");
    const foreignObject = label?.querySelector<SVGForeignObjectElement>("foreignObject");
    const labelContent = foreignObject?.querySelector<HTMLElement>("div");
    const nodeLabel = foreignObject?.querySelector<HTMLElement>(".nodeLabel");
    const paragraph = foreignObject?.querySelector<HTMLElement>("p");
    if (!rect || !label || !foreignObject || !labelContent) {
      return;
    }

    const rectWidth = rect.width.baseVal.value;
    const rectHeight = rect.height.baseVal.value;
    const labelWidth = Math.max(rectWidth - 24, foreignObject.width.baseVal.value);
    const labelHeight = Math.max(rectHeight - 16, foreignObject.height.baseVal.value);
    const labelX = -labelWidth / 2;
    const labelY = -labelHeight / 2;

    label.setAttribute("transform", `translate(${labelX}, ${labelY})`);
    foreignObject.setAttribute("width", String(labelWidth));
    foreignObject.setAttribute("height", String(labelHeight));
    labelContent.style.display = "flex";
    labelContent.style.alignItems = "center";
    labelContent.style.justifyContent = "center";
    labelContent.style.width = `${labelWidth}px`;
    labelContent.style.height = `${labelHeight}px`;
    labelContent.style.maxWidth = `${labelWidth}px`;
    labelContent.style.whiteSpace = "normal";
    labelContent.style.overflowWrap = "normal";
    if (nodeLabel) {
      nodeLabel.style.display = "block";
      nodeLabel.style.width = "100%";
      nodeLabel.style.textAlign = "center";
    }
    if (paragraph) {
      paragraph.style.display = "block";
      paragraph.style.width = "100%";
      paragraph.style.margin = "0";
      paragraph.style.lineHeight = "1.35";
      paragraph.style.textAlign = "center";
    }
  });
}

function trimMermaidViewBox(container: ParentNode) {
  const svg = container.querySelector<SVGSVGElement>("svg.flowchart");
  const root = svg?.querySelector<SVGGElement>("g.root");
  if (!svg || !root) {
    return;
  }

  try {
    const box = root.getBBox();
    const padding = 16;
    const minX = Math.floor(box.x - padding);
    const minY = Math.floor(box.y - padding);
    const width = Math.ceil(box.width + padding * 2);
    const height = Math.ceil(box.height + padding * 2);
    svg.setAttribute("viewBox", `${minX} ${minY} ${width} ${height}`);
    svg.style.maxWidth = `${width}px`;
  } catch {
    // Some browsers may not expose getBBox before the SVG is attached; Mermaid's own viewBox remains usable.
  }
}
