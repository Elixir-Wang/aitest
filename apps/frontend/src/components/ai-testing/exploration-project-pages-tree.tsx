import { type ReactNode, useEffect, useMemo, useState } from "react";

import { ChevronDown, ChevronRight, FileCode2, FileText, Folder, FolderOpen } from "lucide-react";

import { IllustratedEmptyState } from "@/components/ai-testing/illustrated-empty-state";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { Loader } from "@/components/ui/loader";
import { Table, TableBody } from "@/components/ui/table";
import { apiRequest } from "@/lib/api-client";

export type ExplorationPageRecord = {
  id: string;
  title: string;
  display_name?: string;
  parent_id?: string;
  url: string;
  entry_path: string;
};

type ExplorationPageYamlContent = {
  content: string;
};

type ExplorationPageTreeNode = {
  id: string;
  name: string;
  path: string;
  type: "folder" | "page";
  children: ExplorationPageTreeNode[];
  page?: ExplorationPageRecord;
};

function pageDisplayPath(page: ExplorationPageRecord) {
  return (
    page.entry_path ||
    (() => {
      try {
        return new URL(page.url).pathname || "/";
      } catch {
        return page.url || "/";
      }
    })()
  );
}

function pageDirectoryName(page: ExplorationPageRecord, fallbackSegment: string) {
  const displayName = page.display_name?.trim();
  if (displayName) return displayName;
  const pathSegment = fallbackSegment.trim();
  return pathSegment ? pathSegment : page.id;
}

function buildPageTree(pages: ExplorationPageRecord[]): ExplorationPageTreeNode {
  if (pages.some((page) => page.parent_id)) {
    return buildPageTreeFromParents(pages);
  }
  return buildPageTreeFromPaths(pages);
}

function buildPageTreeFromParents(pages: ExplorationPageRecord[]): ExplorationPageTreeNode {
  const root: ExplorationPageTreeNode = {
    id: "root",
    name: "页面",
    path: "/",
    type: "folder",
    children: [],
  };
  const nodes = new Map<string, ExplorationPageTreeNode>();
  for (const page of pages) {
    const path = pageDisplayPath(page);
    const fallbackSegment = path.split("/").filter(Boolean).at(-1) || "首页";
    nodes.set(page.id, {
      id: page.id,
      name: pageDirectoryName(page, fallbackSegment),
      path,
      type: "page",
      children: [],
      page,
    });
  }

  const attached = new Set<string>();
  for (const page of pages) {
    const node = nodes.get(page.id);
    const parentId = page.parent_id?.trim();
    const parent = parentId ? nodes.get(parentId) : null;
    if (!node || !parent || parent.id === node.id || isPageAncestor(node.id, parent, nodes)) {
      continue;
    }
    parent.children.push(node);
    attached.add(node.id);
  }

  for (const page of pages) {
    const node = nodes.get(page.id);
    if (node && !attached.has(page.id)) {
      root.children.push(node);
    }
  }
  return root;
}

function isPageAncestor(
  targetId: string,
  node: ExplorationPageTreeNode,
  nodes: Map<string, ExplorationPageTreeNode>,
): boolean {
  let current: ExplorationPageTreeNode | undefined = node;
  const seen = new Set<string>();
  while (current) {
    if (current.id === targetId) {
      return true;
    }
    if (seen.has(current.id)) {
      return false;
    }
    seen.add(current.id);
    const parentId: string | undefined = current.page?.parent_id;
    current = parentId ? nodes.get(parentId) : undefined;
  }
  return false;
}

function buildPageTreeFromPaths(pages: ExplorationPageRecord[]): ExplorationPageTreeNode {
  const root: ExplorationPageTreeNode = {
    id: "root",
    name: "页面",
    path: "/",
    type: "folder",
    children: [],
  };

  for (const page of pages) {
    const path = pageDisplayPath(page);
    const segments = path.split("/").filter(Boolean);
    const nodeSegments = segments.length > 0 ? segments : ["首页"];
    let current = root;
    let currentPath = "";

    nodeSegments.forEach((segment, index) => {
      currentPath = segment === "首页" && path === "/" ? "/" : `${currentPath}/${segment}`;
      const isPage = index === nodeSegments.length - 1;
      const nodeId = isPage ? page.id : `folder:${currentPath}`;
      let child = current.children.find((item) => item.id === nodeId);
      if (!child) {
        child = {
          id: nodeId,
          name: isPage ? pageDirectoryName(page, segment) : segment,
          path: isPage ? path : currentPath,
          type: isPage ? "page" : "folder",
          children: [],
          page: isPage ? page : undefined,
        };
        current.children.push(child);
      }
      if (isPage) {
        child.page = page;
        child.name = pageDirectoryName(page, segment);
      }
      current = child;
    });
  }

  return root;
}

function collectPageFolderIds(node: ExplorationPageTreeNode): string[] {
  return node.children.flatMap((child) => [
    ...(child.children.length > 0 ? [child.id] : []),
    ...collectPageFolderIds(child),
  ]);
}

function findPageNode(node: ExplorationPageTreeNode, pageId: string): ExplorationPageTreeNode | null {
  if (node.id === pageId) {
    return node;
  }
  for (const child of node.children) {
    const found = findPageNode(child, pageId);
    if (found) {
      return found;
    }
  }
  return null;
}

export function ExplorationProjectPagesTree({
  expandedNodeIds,
  loading,
  onPageSelect,
  onToggleNode,
  pages,
  projectId,
  selectedPageId,
}: {
  expandedNodeIds: string[];
  loading: boolean;
  onPageSelect: (pageId: string) => void;
  onToggleNode: (nodeId: string) => void;
  pages: ExplorationPageRecord[];
  projectId: string;
  selectedPageId: string;
}) {
  const tree = useMemo(() => buildPageTree(pages), [pages]);
  const selectedNode = selectedPageId ? findPageNode(tree, selectedPageId) : null;
  const selectedPage = selectedNode?.page ?? pages[0] ?? null;
  const effectiveExpandedIds = expandedNodeIds.length > 0 ? expandedNodeIds : collectPageFolderIds(tree);
  const [yamlContent, setYamlContent] = useState<ExplorationPageYamlContent | null>(null);
  const [yamlLoading, setYamlLoading] = useState(false);
  const [yamlError, setYamlError] = useState("");

  useEffect(() => {
    if (!selectedPageId && pages[0]) {
      onPageSelect(pages[0].id);
    }
  }, [onPageSelect, pages, selectedPageId]);

  useEffect(() => {
    if (!selectedPage?.id || !projectId) {
      setYamlContent(null);
      setYamlError("");
      return;
    }

    let ignore = false;
    setYamlLoading(true);
    setYamlError("");

    async function loadYamlContent() {
      try {
        const data = await apiRequest<ExplorationPageYamlContent>(
          `/page-exploration/projects/${projectId}/pages/${selectedPage.id}/yaml`,
        );
        if (!ignore) {
          setYamlContent(data);
        }
      } catch (requestError) {
        if (!ignore) {
          setYamlContent(null);
          setYamlError(requestError instanceof Error ? requestError.message : "YAML 文件加载失败");
        }
      } finally {
        if (!ignore) {
          setYamlLoading(false);
        }
      }
    }

    void loadYamlContent();

    return () => {
      ignore = true;
    };
  }, [projectId, selectedPage?.id]);

  return (
    <div className="overflow-hidden rounded-lg border bg-background">
      {loading ? (
        <div className="p-6">
          <Table>
            <TableBody>
              <TableLoadingRow colSpan={1} label="页面信息加载中" />
            </TableBody>
          </Table>
        </div>
      ) : pages.length === 0 ? (
        <IllustratedEmptyState description="执行页面探索后，已发现的页面会展示在这里。" title="暂无页面信息" />
      ) : (
        <div className="grid min-h-[30rem] lg:grid-cols-[18rem_minmax(0,1fr)]">
          <aside className="min-h-0 border-b bg-muted/20 lg:border-r lg:border-b-0">
            <div className="border-b px-3 py-2 font-medium text-sm">页面目录</div>
            <div className="max-h-[34rem] overflow-auto p-2">
              {tree.children.map((node) => (
                <ExplorationPageTreeItem
                  activePageId={selectedPage?.id ?? ""}
                  depth={0}
                  expandedNodeIds={effectiveExpandedIds}
                  key={node.id}
                  node={node}
                  onPageSelect={onPageSelect}
                  onToggleNode={onToggleNode}
                />
              ))}
            </div>
          </aside>
          <main className="min-w-0 p-4">
            {selectedPage ? (
              <YamlCodePreview content={yamlContent?.content ?? ""} error={yamlError} loading={yamlLoading} />
            ) : null}
          </main>
        </div>
      )}
    </div>
  );
}

function ExplorationPageTreeItem({
  activePageId,
  depth,
  expandedNodeIds,
  node,
  onPageSelect,
  onToggleNode,
}: {
  activePageId: string;
  depth: number;
  expandedNodeIds: string[];
  node: ExplorationPageTreeNode;
  onPageSelect: (pageId: string) => void;
  onToggleNode: (nodeId: string) => void;
}) {
  const isFolder = node.type === "folder";
  const hasChildren = node.children.length > 0;
  const expanded = hasChildren && expandedNodeIds.includes(node.id);
  const active = node.type === "page" && node.id === activePageId;

  return (
    <div>
      <div
        className={
          active
            ? "flex h-8 items-center gap-1 rounded-md bg-primary/10 px-1 text-primary"
            : "flex h-8 items-center gap-1 rounded-md px-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        }
        style={{ paddingLeft: `${depth * 14 + 4}px` }}
      >
        {hasChildren ? (
          <button
            aria-label={expanded ? "收起页面分组" : "展开页面分组"}
            className="flex size-5 items-center justify-center rounded-sm hover:bg-background"
            onClick={() => onToggleNode(node.id)}
            type="button"
          >
            {expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
          </button>
        ) : (
          <span className="size-5" />
        )}
        <button
          className="flex min-w-0 flex-1 items-center gap-1.5 text-left text-sm"
          onClick={() => {
            if (isFolder) {
              onToggleNode(node.id);
            } else {
              onPageSelect(node.id);
            }
          }}
          type="button"
        >
          {isFolder ? (
            expanded ? (
              <FolderOpen className="size-4 shrink-0" />
            ) : (
              <Folder className="size-4 shrink-0" />
            )
          ) : (
            <FileText className="size-4 shrink-0" />
          )}
          <span className="truncate">{node.name}</span>
        </button>
      </div>
      {hasChildren && expanded
        ? node.children.map((child) => (
            <ExplorationPageTreeItem
              activePageId={activePageId}
              depth={depth + 1}
              expandedNodeIds={expandedNodeIds}
              key={child.id}
              node={child}
              onPageSelect={onPageSelect}
              onToggleNode={onToggleNode}
            />
          ))
        : null}
    </div>
  );
}

function renderYamlValue(value: string): ReactNode {
  const trimmed = value.trim();
  if (!trimmed) return value;
  if (trimmed.startsWith("#")) return <span className="text-slate-400">{value}</span>;
  if (/^["'].*["']$/.test(trimmed)) {
    return <span className="text-emerald-700 dark:text-emerald-300">{value}</span>;
  }
  if (/^(true|false|null)$/i.test(trimmed)) {
    return <span className="font-medium text-violet-700 dark:text-violet-300">{value}</span>;
  }
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
    return <span className="font-medium text-blue-700 dark:text-blue-300">{value}</span>;
  }
  return <span className="text-slate-700 dark:text-slate-200">{value}</span>;
}

function renderYamlLine(line: string): ReactNode {
  if (!line.trim()) return <span>&nbsp;</span>;

  const commentIndex = line.indexOf("#");
  const content = commentIndex >= 0 ? line.slice(0, commentIndex) : line;
  const comment = commentIndex >= 0 ? line.slice(commentIndex) : "";
  const match = content.match(/^(\s*)(-\s*)?([^:#]+?)(\s*:\s*)(.*)$/);

  if (!match) {
    return (
      <>
        <span className="text-slate-700 dark:text-slate-200">{content}</span>
        {comment ? <span className="text-slate-400">{comment}</span> : null}
      </>
    );
  }

  const [, indent, dash = "", key, colon, value] = match;
  return (
    <>
      <span>{indent}</span>
      {dash ? <span className="text-amber-600 dark:text-amber-300">{dash}</span> : null}
      <span className="font-semibold text-cyan-800 dark:text-cyan-200">{key}</span>
      <span className="text-slate-400">{colon}</span>
      {renderYamlValue(value)}
      {comment ? <span className="text-slate-400">{comment}</span> : null}
    </>
  );
}

function YamlCodePreview({ content, error, loading }: { content: string; error: string; loading: boolean }) {
  if (loading) {
    return (
      <div className="grid min-h-72 place-items-center rounded-lg border border-dashed bg-slate-50 text-muted-foreground text-sm dark:bg-slate-950/40">
        <div className="flex items-center gap-2">
          <Loader className="size-4" />
          YAML 文件加载中
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/8 p-4 text-destructive text-sm">
        {error}
      </div>
    );
  }

  const lines = content
    ? content.split("\n").map((line, index) => ({
        id: `${index + 1}:${line}`,
        line,
        number: index + 1,
      }))
    : [];
  if (lines.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-6 text-center text-muted-foreground text-sm">
        暂无 YAML 内容。
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border bg-slate-50 shadow-sm dark:bg-slate-950/60">
      <div className="flex h-9 items-center justify-between border-b bg-white/80 px-3 dark:bg-slate-900/70">
        <div className="flex items-center gap-2 font-medium text-slate-700 text-xs dark:text-slate-200">
          <FileCode2 className="size-3.5 text-cyan-700 dark:text-cyan-300" />
          YAML
        </div>
        <div className="text-slate-400 text-xs">{lines.length} 行</div>
      </div>
      <pre className="max-h-[34rem] overflow-auto p-0 font-mono text-[12px] leading-6">
        {lines.map((line) => (
          <div
            className="grid grid-cols-[3.5rem_minmax(0,1fr)] border-slate-200/55 border-b last:border-b-0 dark:border-slate-800/70"
            key={line.id}
          >
            <span className="select-none border-r bg-slate-100/70 px-3 text-right text-slate-400 dark:border-slate-800 dark:bg-slate-900/70">
              {line.number}
            </span>
            <code className="min-w-0 whitespace-pre-wrap break-words px-3 text-slate-700 dark:text-slate-200">
              {renderYamlLine(line.line)}
            </code>
          </div>
        ))}
      </pre>
    </div>
  );
}
