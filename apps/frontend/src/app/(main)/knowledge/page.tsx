"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import Image from "next/image";

import {
  Archive,
  ArrowLeft,
  BookOpen,
  Brain,
  Building2,
  ChevronDown,
  ChevronRight,
  Eye,
  FileText,
  Folder,
  FolderKanban,
  FolderOpen,
  Loader2,
  MapIcon,
  MessageSquare,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plus,
  Search,
  Trash2,
  TriangleAlert,
  Upload,
  User,
} from "lucide-react";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import FileUpload1 from "@/components/ui/file-upload-1";
import { Input } from "@/components/ui/input";
import { KnowledgeChatInput } from "@/components/ui/knowledge-chat-input";
import { Label } from "@/components/ui/label";
import PulsatingDots from "@/components/ui/pulsating-loader";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  API_BASE_URL,
  type ApiCompanyKnowledgeBase,
  type ApiCompanyKnowledgeBaseList,
  type ApiCompanyKnowledgeFile,
  type ApiCompanyKnowledgeFolder,
  type ApiCompanyKnowledgeTree,
  type ApiCompanyKnowledgeTreeNode,
  type ApiCompanyKnowledgeUploadResult,
  type ApiKnowledgeConversation,
  type ApiKnowledgeConversationDetail,
  type ApiKnowledgeConversationMessage,
  type ApiKnowledgeQueryResult,
  type ApiModelAssignment,
  type ApiModelProvider,
  type ApiProject,
  apiAuthHeaders,
  apiRequest,
  formatDateTime,
} from "@/lib/api-client";
import { useProjectContextStore } from "@/stores/project-context-store";

function ProjectKnowledgeIcon({ className }: { className?: string }) {
  return <Image src="/brand/a-orbit-logo.svg" alt="" width={16} height={16} className={className} />;
}

const knowledgeScopes = [
  { value: "project", label: "项目知识库", icon: FolderKanban },
  { value: "company", label: "公司知识库", icon: Building2 },
] as const;
const emptyCompanyForm = {
  name: "",
  description: "",
};
const KNOWLEDGE_QUERY_CAPABILITY_ID = "knowledge_query";
const COMPANY_KNOWLEDGE_PREVIEW_ID = "company-knowledge-preview";
const projectKnowledgeQuickPrompts = [
  { icon: Search, label: "查需求", prompt: "帮我查询当前项目最终需求文档中的核心业务规则。" },
  { icon: MapIcon, label: "看探索", prompt: "帮我总结当前项目探索记录覆盖了哪些页面和模块。" },
  { icon: Archive, label: "查来源", prompt: "帮我追踪当前项目关键结论的来源依据，包括需求版本、探索记录和对应位置。" },
  {
    icon: BookOpen,
    label: "看模块",
    prompt: "帮我按知识库模块梳理当前项目的业务域、页面事实、规则条目和模块之间的关系。",
  },
] as const;

type ProjectChatMessage = {
  id: string;
  role: "assistant" | "user";
  body: string;
  thinking?: string;
  thinkingCompletedAt?: number;
  thinkingStartedAt?: number;
};

type ProjectKnowledgeStreamEvent =
  | { type: "message_delta"; delta: string }
  | { type: "thinking_delta"; delta: string }
  | { type: "metadata"; result: ApiKnowledgeQueryResult }
  | { type: "done" }
  | { type: "error"; code?: string; message: string; result?: ApiKnowledgeQueryResult };

function companyTreeContainsNode(node: ApiCompanyKnowledgeTreeNode, nodeId: string): boolean {
  if (node.id === nodeId) {
    return true;
  }
  if (node.type === "file") {
    return false;
  }
  return node.children.some((child) => companyTreeContainsNode(child, nodeId));
}

type CompanyBreadcrumbItem = { id: string; name: string; type: "base" | "folder" | "file" };

function collectCompanyFolderIds(root: ApiCompanyKnowledgeFolder): string[] {
  const ids: string[] = [root.id];
  function walk(node: ApiCompanyKnowledgeFolder) {
    for (const child of node.children) {
      if (child.type === "folder") {
        ids.push(child.id);
        walk(child);
      }
    }
  }
  walk(root);
  return ids;
}

function collectAncestorFolderIds(root: ApiCompanyKnowledgeFolder, targetId: string): string[] {
  function walk(node: ApiCompanyKnowledgeFolder, ancestors: string[]): string[] | null {
    for (const child of node.children) {
      if (child.id === targetId) {
        return ancestors;
      }
      if (child.type === "folder") {
        const found = walk(child, [...ancestors, child.id]);
        if (found) {
          return found;
        }
      }
    }
    return null;
  }
  return walk(root, []) ?? [];
}

function findCompanyBreadcrumb(
  root: ApiCompanyKnowledgeFolder,
  baseName: string,
  targetId: string,
): CompanyBreadcrumbItem[] | null {
  function walk(node: ApiCompanyKnowledgeFolder, trail: CompanyBreadcrumbItem[]): CompanyBreadcrumbItem[] | null {
    for (const child of node.children) {
      const childItem: CompanyBreadcrumbItem =
        child.type === "file"
          ? { id: child.id, name: child.name, type: "file" }
          : { id: child.id, name: child.name, type: "folder" };
      if (child.id === targetId) {
        return [...trail, childItem];
      }
      if (child.type === "folder") {
        const found = walk(child, [...trail, childItem]);
        if (found) {
          return found;
        }
      }
    }
    return null;
  }
  return walk(root, [{ id: root.id, name: baseName, type: "base" }]);
}

function filterCompanyTreeNodes(nodes: ApiCompanyKnowledgeTreeNode[], query: string): ApiCompanyKnowledgeTreeNode[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return nodes;
  }
  const result: ApiCompanyKnowledgeTreeNode[] = [];
  for (const node of nodes) {
    if (node.type === "file") {
      if (node.name.toLowerCase().includes(normalized)) {
        result.push(node);
      }
      continue;
    }
    const filteredChildren = filterCompanyTreeNodes(node.children, query);
    if (node.name.toLowerCase().includes(normalized) || filteredChildren.length > 0) {
      result.push({ ...node, children: filteredChildren });
    }
  }
  return result;
}

function collectFolderIdsFromNodes(nodes: ApiCompanyKnowledgeTreeNode[]): string[] {
  const ids: string[] = [];
  for (const node of nodes) {
    if (node.type === "folder") {
      ids.push(node.id);
      ids.push(...collectFolderIdsFromNodes(node.children));
    }
  }
  return ids;
}

function companyUploadFileKey(file: File): string {
  return `${file.name}-${file.lastModified}-${file.size}`;
}

function resolveCompanyTargetFolderLabel(root: ApiCompanyKnowledgeFolder, baseName: string, folderId: string): string {
  if (!folderId || folderId === root.id) {
    return baseName;
  }
  const breadcrumb = findCompanyBreadcrumb(root, baseName, folderId);
  if (!breadcrumb) {
    return baseName;
  }
  return breadcrumb.map((item) => item.name).join(" / ");
}

function findCompanyFolderInTree(root: ApiCompanyKnowledgeFolder, folderId: string): ApiCompanyKnowledgeFolder | null {
  for (const child of root.children) {
    if (child.type === "folder") {
      if (child.id === folderId) {
        return child;
      }
      const found = findCompanyFolderInTree(child, folderId);
      if (found) {
        return found;
      }
    }
  }
  return null;
}

function resolveCompanyFolder(root: ApiCompanyKnowledgeFolder, folderId: string): ApiCompanyKnowledgeFolder {
  if (!folderId || folderId === root.id) {
    return root;
  }
  return findCompanyFolderInTree(root, folderId) ?? root;
}

function resolveCompanyBreadcrumb(
  root: ApiCompanyKnowledgeFolder,
  baseName: string,
  targetId: string,
): CompanyBreadcrumbItem[] {
  if (!targetId || targetId === root.id) {
    return [{ id: root.id, name: baseName, type: "base" }];
  }
  return findCompanyBreadcrumb(root, baseName, targetId) ?? [{ id: root.id, name: baseName, type: "base" }];
}

function countCompanyFolderChildren(folder: ApiCompanyKnowledgeFolder): { folders: number; files: number } {
  let folders = 0;
  let files = 0;
  for (const child of folder.children) {
    if (child.type === "folder") {
      folders += 1;
    } else {
      files += 1;
    }
  }
  return { folders, files };
}

export default function Page() {
  const [activeScope, setActiveScope] = useState<(typeof knowledgeScopes)[number]["value"]>("project");
  const [searchText, setSearchText] = useState("");
  const { currentProjectId, hydrate, scope: globalProjectScope } = useProjectContextStore();
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [companyView, setCompanyView] = useState<"list" | "detail">("list");
  const [selectedCompanyBase, setSelectedCompanyBase] = useState<ApiCompanyKnowledgeBase | null>(null);
  const [companyTree, setCompanyTree] = useState<ApiCompanyKnowledgeTree | null>(null);
  const [selectedTreeNodeId, setSelectedTreeNodeId] = useState("");
  const [selectedCompanyFile, setSelectedCompanyFile] = useState<ApiCompanyKnowledgeFile | null>(null);
  const [companyDialogOpen, setCompanyDialogOpen] = useState(false);
  const [companyDialogMode, setCompanyDialogMode] = useState<"create" | "edit">("create");
  const [editingCompanyBaseId, setEditingCompanyBaseId] = useState("");
  const [folderDialogOpen, setFolderDialogOpen] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [deleteBaseTarget, setDeleteBaseTarget] = useState<ApiCompanyKnowledgeBase | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ApiCompanyKnowledgeTreeNode | null>(null);
  const [companyForm, setCompanyForm] = useState(emptyCompanyForm);
  const [folderName, setFolderName] = useState("");
  const [activeFolderId, setActiveFolderId] = useState("");
  const [expandedFolderIds, setExpandedFolderIds] = useState<string[]>([]);
  const [companySidebarOpen, setCompanySidebarOpen] = useState(false);
  const [companyTreeSearch, setCompanyTreeSearch] = useState("");
  const [projectChatDraft, setProjectChatDraft] = useState("");
  const [showProjectThinking, setShowProjectThinking] = useState(false);
  const [knowledgeScope, setKnowledgeScope] = useState<"all" | "project">("all");
  const [knowledgeProjectId, setKnowledgeProjectId] = useState<string | null>(null);
  const [knowledgeModelProviders, setKnowledgeModelProviders] = useState<ApiModelProvider[]>([]);
  const [selectedKnowledgeModelProviderId, setSelectedKnowledgeModelProviderId] = useState("");
  const [knowledgeModelLoading, setKnowledgeModelLoading] = useState(true);
  const [knowledgeModelSaving, setKnowledgeModelSaving] = useState(false);
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [projectMessages, setProjectMessages] = useState<ProjectChatMessage[]>([]);
  const [projectConversations, setProjectConversations] = useState<ApiKnowledgeConversation[]>([]);
  const [activeProjectConversationId, setActiveProjectConversationId] = useState<string | null>(null);
  const projectQueryRunIdRef = useRef(0);
  const latestProjectQueryScopeRef = useRef("");
  const projectQueryAbortControllerRef = useRef<AbortController | null>(null);
  const projectConversationLoadRunIdRef = useRef(0);
  const projectConversationOpenRunIdRef = useRef(0);
  const [companyFiles, setCompanyFiles] = useState<File[]>([]);
  const [companyUploadStates, setCompanyUploadStates] = useState<
    Record<string, { progress: number; status: "idle" | "uploading" | "completed" | "error" }>
  >({});
  const {
    allSelected: allCompanySelected,
    partiallySelected: partiallyCompanySelected,
    rows: companyRows,
    selectedCount: selectedCompanyCount,
    selectedIds: selectedCompanyIds,
    setRows: setCompanyRows,
    toggleAll: toggleAllCompany,
    toggleOne: toggleOneCompany,
  } = useLocalTableSelection<ApiCompanyKnowledgeBase>([]);
  const filteredCompanyRows = companyRows.filter((item) =>
    [item.name, item.description].some((value) => value.toLowerCase().includes(searchText.trim().toLowerCase())),
  );
  const isCompanyKnowledge = activeScope === "company";
  const activeProjects = projects.filter((project) => project.status !== "archived");
  const activeProjectIdsKey = activeProjects.map((project) => project.id).join("|");
  const activeCurrentProject = activeProjects.find((project) => project.id === currentProjectId) ?? null;
  const effectiveKnowledgeScope = globalProjectScope === "project" && activeCurrentProject ? "project" : knowledgeScope;
  const effectiveProjectId =
    globalProjectScope === "project"
      ? (activeCurrentProject?.id ?? null)
      : effectiveKnowledgeScope === "project"
        ? knowledgeProjectId
        : null;
  const projectId = effectiveProjectId;
  const projectResetKey = `${effectiveKnowledgeScope}:${effectiveProjectId ?? ""}`;
  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (globalProjectScope === "project") {
      return;
    }
    const activeProjectIds = new Set(activeProjectIdsKey ? activeProjectIdsKey.split("|") : []);
    if (knowledgeScope === "project" && knowledgeProjectId && !activeProjectIds.has(knowledgeProjectId)) {
      setKnowledgeScope("all");
      setKnowledgeProjectId(null);
    }
  }, [activeProjectIdsKey, globalProjectScope, knowledgeProjectId, knowledgeScope]);

  useEffect(() => {
    let ignore = false;

    async function loadProjects() {
      try {
        const nextProjects = await apiRequest<ApiProject[]>("/projects");
        if (!ignore) {
          setProjects(nextProjects);
        }
      } catch {
        if (!ignore) {
          setProjects([]);
        }
      }
    }

    void loadProjects();

    return () => {
      ignore = true;
    };
  }, []);

  const loadKnowledgeQueryModelAssignment = useCallback(async () => {
    setKnowledgeModelLoading(true);
    try {
      const [assignmentRows, providerRows] = await Promise.all([
        apiRequest<ApiModelAssignment[]>("/model-assignments"),
        apiRequest<ApiModelProvider[]>("/models/providers"),
      ]);
      const enabledProviders = providerRows.filter((provider) => provider.status === "enabled");
      const assignment = assignmentRows.find((item) => item.capability_id === KNOWLEDGE_QUERY_CAPABILITY_ID);
      setKnowledgeModelProviders(enabledProviders);
      setSelectedKnowledgeModelProviderId(assignment?.model_provider_id ?? "");
    } catch (nextError) {
      setKnowledgeModelProviders([]);
      setSelectedKnowledgeModelProviderId("");
      setError(nextError instanceof Error ? nextError.message : "加载项目知识库模型配置失败。");
    } finally {
      setKnowledgeModelLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadKnowledgeQueryModelAssignment();
  }, [loadKnowledgeQueryModelAssignment]);

  async function updateKnowledgeQueryModelProvider(modelProviderId: string) {
    setSelectedKnowledgeModelProviderId(modelProviderId);
    setKnowledgeModelSaving(true);
    setError("");
    try {
      const assignment = await apiRequest<ApiModelAssignment>(`/model-assignments/${KNOWLEDGE_QUERY_CAPABILITY_ID}`, {
        body: JSON.stringify({ model_provider_id: modelProviderId }),
        method: "PUT",
      });
      setSelectedKnowledgeModelProviderId(assignment.model_provider_id ?? "");
      await loadKnowledgeQueryModelAssignment();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "保存项目知识库模型配置失败。");
      await loadKnowledgeQueryModelAssignment();
    } finally {
      setKnowledgeModelSaving(false);
    }
  }

  useEffect(() => {
    void projectResetKey;
    projectQueryAbortControllerRef.current?.abort();
    projectQueryAbortControllerRef.current = null;
    projectQueryRunIdRef.current += 1;
    projectConversationLoadRunIdRef.current += 1;
    projectConversationOpenRunIdRef.current += 1;
    latestProjectQueryScopeRef.current = projectResetKey;
    setProjectMessages([]);
    setProjectChatDraft("");
    setProjectConversations([]);
    setActiveProjectConversationId(null);
    setError("");
    setLoading(false);
    setRunning(false);
  }, [projectResetKey]);

  function stopProjectKnowledgeQuery() {
    projectQueryAbortControllerRef.current?.abort();
  }

  const openProjectConversation = useCallback(
    async (scope: "all" | "project", conversationId: string, targetProjectId?: string) => {
      const scopeKey = scope === "all" ? "all:" : `project:${targetProjectId ?? ""}`;
      const conversationOpenRunId = projectConversationOpenRunIdRef.current + 1;
      projectConversationOpenRunIdRef.current = conversationOpenRunId;
      const isCurrentConversationOpen = () =>
        projectConversationOpenRunIdRef.current === conversationOpenRunId &&
        latestProjectQueryScopeRef.current === scopeKey;
      setLoading(true);
      setError("");
      try {
        const conversationPath =
          scope === "all"
            ? `/knowledge/conversations/${conversationId}`
            : `/projects/${targetProjectId}/knowledge/conversations/${conversationId}`;
        const detail = await apiRequest<ApiKnowledgeConversationDetail>(conversationPath);
        if (isCurrentConversationOpen()) {
          setActiveProjectConversationId(detail.conversation.id);
          setProjectMessages(detail.messages.map(projectMessageFromApi));
          setProjectChatDraft("");
        }
      } catch (nextError) {
        if (isCurrentConversationOpen()) {
          setError(nextError instanceof Error ? nextError.message : "打开项目知识库对话失败。");
        }
      } finally {
        if (isCurrentConversationOpen()) {
          setLoading(false);
        }
      }
    },
    [],
  );

  const loadProjectConversations = useCallback(
    async (scope: "all" | "project", targetProjectId?: string) => {
      const scopeKey = scope === "all" ? "all:" : `project:${targetProjectId ?? ""}`;
      const conversationLoadRunId = projectConversationLoadRunIdRef.current + 1;
      projectConversationLoadRunIdRef.current = conversationLoadRunId;
      const isCurrentConversationLoad = () =>
        projectConversationLoadRunIdRef.current === conversationLoadRunId &&
        latestProjectQueryScopeRef.current === scopeKey;
      setLoading(true);
      setError("");
      try {
        const conversationsPath =
          scope === "all" ? "/knowledge/conversations" : `/projects/${targetProjectId}/knowledge/conversations`;
        const conversations = await apiRequest<ApiKnowledgeConversation[]>(conversationsPath);
        if (isCurrentConversationLoad()) {
          setProjectConversations(conversations);
        }
      } catch (nextError) {
        if (isCurrentConversationLoad()) {
          setError(nextError instanceof Error ? nextError.message : "加载项目知识库对话失败。");
          setProjectConversations([]);
        }
      } finally {
        if (isCurrentConversationLoad()) {
          setLoading(false);
        }
      }
    },
    [],
  );

  useEffect(() => {
    if (isCompanyKnowledge) {
      return;
    }
    if (effectiveKnowledgeScope === "all") {
      void loadProjectConversations("all");
      return;
    }
    if (!effectiveProjectId) {
      return;
    }
    void loadProjectConversations("project", effectiveProjectId);
  }, [effectiveKnowledgeScope, effectiveProjectId, isCompanyKnowledge, loadProjectConversations]);

  function createProjectConversation() {
    setActiveProjectConversationId(null);
    setProjectMessages([]);
    setProjectChatDraft("");
    setError("");
  }

  async function deleteProjectConversation(conversationId: string) {
    if (effectiveKnowledgeScope === "project" && !projectId) {
      return;
    }
    setRunning(true);
    setError("");
    try {
      const deletePath =
        effectiveKnowledgeScope === "all"
          ? `/knowledge/conversations/${conversationId}`
          : `/projects/${projectId}/knowledge/conversations/${conversationId}`;
      await apiRequest<{ deleted: boolean }>(deletePath, {
        method: "DELETE",
      });
      setProjectConversations((items) => items.filter((item) => item.id !== conversationId));
      if (activeProjectConversationId === conversationId) {
        createProjectConversation();
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "删除项目知识库对话失败。");
    } finally {
      setRunning(false);
    }
  }

  const openCompanyBase = useCallback(async (baseId: string) => {
    const tree = await apiRequest<ApiCompanyKnowledgeTree>(`/global-knowledge/bases/${baseId}/tree`);
    setSelectedCompanyBase(tree.base);
    setCompanyTree(tree);
    setCompanyView("detail");
    setExpandedFolderIds([]);
    setCompanyTreeSearch("");
    setCompanySidebarOpen(false);
    setSelectedTreeNodeId("");
    setActiveFolderId(tree.root.id);
    setSelectedCompanyFile(null);
  }, []);

  const refreshCompanyTree = useCallback(
    async (baseId = selectedCompanyBase?.id ?? "", focusFileId = selectedCompanyFile?.id ?? "") => {
      if (!baseId) {
        return;
      }
      const tree = await apiRequest<ApiCompanyKnowledgeTree>(`/global-knowledge/bases/${baseId}/tree`);
      setSelectedCompanyBase(tree.base);
      setCompanyTree(tree);
      setExpandedFolderIds((prev) => {
        const validIds = new Set(collectCompanyFolderIds(tree.root));
        let next = prev.filter((id) => validIds.has(id));
        if (focusFileId) {
          next = Array.from(new Set([...next, ...collectAncestorFolderIds(tree.root, focusFileId)]));
        }
        return next;
      });
    },
    [selectedCompanyBase?.id, selectedCompanyFile?.id],
  );

  const loadCompanyBases = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await apiRequest<ApiCompanyKnowledgeBaseList>("/global-knowledge/bases");
      setCompanyRows(result.items);
      if (!result.items[0]) {
        setSelectedCompanyBase(null);
        setCompanyTree(null);
        setSelectedCompanyFile(null);
        setSelectedTreeNodeId("");
        setActiveFolderId("");
        setCompanyView("list");
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "加载公司知识库失败。");
      setCompanyRows([]);
      setSelectedCompanyBase(null);
      setCompanyTree(null);
      setSelectedCompanyFile(null);
      setSelectedTreeNodeId("");
      setActiveFolderId("");
      setCompanyView("list");
    } finally {
      setLoading(false);
    }
  }, [setCompanyRows]);

  useEffect(() => {
    if (isCompanyKnowledge) {
      void loadCompanyBases();
    }
  }, [isCompanyKnowledge, loadCompanyBases]);

  async function queryProjectKnowledge(question: string) {
    if (effectiveKnowledgeScope === "project" && !effectiveProjectId) {
      setError("请先在顶部选择具体项目。");
      return;
    }
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      return;
    }
    const submittedKnowledgeScope = effectiveKnowledgeScope;
    const submittedProjectId = effectiveProjectId;
    const submittedConversationId = activeProjectConversationId;
    const submittedShowThinking = showProjectThinking;
    const submittedQueryScopeKey = `${submittedKnowledgeScope}:${submittedProjectId ?? ""}`;
    const queryRunId = projectQueryRunIdRef.current + 1;
    projectQueryRunIdRef.current = queryRunId;
    latestProjectQueryScopeRef.current = submittedQueryScopeKey;
    projectQueryAbortControllerRef.current?.abort();
    const abortController = new AbortController();
    projectQueryAbortControllerRef.current = abortController;
    const isCurrentProjectQueryScope = () =>
      projectQueryRunIdRef.current === queryRunId && latestProjectQueryScopeRef.current === submittedQueryScopeKey;
    const userMessage: ProjectChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      body: trimmedQuestion,
    };
    const assistantMessageId = crypto.randomUUID();
    const assistantMessage: ProjectChatMessage = {
      id: assistantMessageId,
      role: "assistant",
      body: "",
    };
    let errorResultPersisted = false;
    setProjectMessages((messages) => [...messages, userMessage, assistantMessage]);
    setProjectChatDraft("");
    setRunning(true);
    setError("");
    try {
      const headers = apiAuthHeaders();
      headers.set("Content-Type", "application/json");
      const streamPath =
        submittedKnowledgeScope === "all"
          ? "/knowledge/query/stream"
          : `/projects/${submittedProjectId}/knowledge/query/stream`;
      const response = await fetch(`${API_BASE_URL}${streamPath}`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          question: trimmedQuestion,
          include_requirements: true,
          show_thinking: submittedShowThinking,
          conversation_id: submittedConversationId,
        }),
        signal: abortController.signal,
      });
      if (!response.ok || !response.body) {
        throw new Error("项目知识库流式查询失败。");
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let finalResult: ApiKnowledgeQueryResult | null = null;

      for (;;) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() || "";
        for (const chunk of chunks) {
          const event = parseProjectKnowledgeStreamEvent(chunk);
          if (!event) {
            continue;
          }
          if (event.type === "message_delta") {
            if (isCurrentProjectQueryScope()) {
              setProjectMessages((messages) =>
                messages.map((message) =>
                  message.id === assistantMessageId ? { ...message, body: message.body + event.delta } : message,
                ),
              );
            }
          } else if (event.type === "thinking_delta") {
            const thinkingDelta = sanitizeThinkingText(event.delta);
            if (!thinkingDelta) {
              continue;
            }
            const thinkingReceivedAt = Date.now();
            if (isCurrentProjectQueryScope()) {
              setProjectMessages((messages) =>
                messages.map((message) =>
                  message.id === assistantMessageId
                    ? {
                        ...message,
                        thinking: `${message.thinking ?? ""}${thinkingDelta}\n`,
                        thinkingStartedAt: message.thinkingStartedAt ?? thinkingReceivedAt,
                      }
                    : message,
                ),
              );
            }
          } else if (event.type === "metadata") {
            finalResult = event.result;
            const conversation = event.result.conversation;
            if (isCurrentProjectQueryScope() && conversation) {
              setActiveProjectConversationId(conversation.id);
              setProjectConversations((items) => upsertConversation(items, conversation));
            }
            if (isCurrentProjectQueryScope()) {
              setProjectMessages((messages) =>
                messages.map((message) =>
                  message.id === assistantMessageId ? mergeAssistantStreamResult(message, event.result) : message,
                ),
              );
            }
          } else if (event.type === "error") {
            const errorResult = event.result;
            const errorConversation = errorResult?.conversation;
            if (errorResult && errorConversation && isCurrentProjectQueryScope()) {
              errorResultPersisted = true;
              setActiveProjectConversationId(errorConversation.id);
              setProjectConversations((items) => upsertConversation(items, errorConversation));
              setProjectMessages((messages) =>
                messages.map((message) =>
                  message.id === assistantMessageId ? mergeAssistantStreamResult(message, errorResult) : message,
                ),
              );
            }
            throw new Error(event.message || "查询项目知识库失败。");
          }
        }
      }
      if (!finalResult) {
        throw new Error("项目知识库流式查询未返回最终结果。");
      }
    } catch (nextError) {
      if (isCurrentProjectQueryScope()) {
        if (nextError instanceof DOMException && nextError.name === "AbortError") {
          setProjectMessages((messages) =>
            messages.flatMap((message) => {
              if (message.id !== assistantMessageId) {
                return [message];
              }
              return message.body.length > 0 || (message.thinking?.length ?? 0) > 0 ? [message] : [];
            }),
          );
        } else {
          setError(nextError instanceof Error ? nextError.message : "查询项目知识库失败。");
          if (!errorResultPersisted) {
            setProjectMessages((messages) => messages.filter((message) => message.id !== assistantMessageId));
          }
        }
      }
    } finally {
      if (isCurrentProjectQueryScope()) {
        if (projectQueryAbortControllerRef.current === abortController) {
          projectQueryAbortControllerRef.current = null;
        }
        setRunning(false);
      }
    }
  }

  async function createCompanyBase() {
    setRunning(true);
    setError("");
    try {
      const base = await apiRequest<ApiCompanyKnowledgeBase>("/global-knowledge/bases", {
        method: "POST",
        body: JSON.stringify({
          name: companyForm.name,
          description: companyForm.description,
        }),
      });
      setCompanyDialogOpen(false);
      setCompanyForm(emptyCompanyForm);
      setCompanyDialogMode("create");
      setEditingCompanyBaseId("");
      await loadCompanyBases();
      await openCompanyBase(base.id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "创建公司知识库失败。");
    } finally {
      setRunning(false);
    }
  }

  async function updateCompanyBase() {
    if (!editingCompanyBaseId) {
      return;
    }
    setRunning(true);
    setError("");
    try {
      const base = await apiRequest<ApiCompanyKnowledgeBase>(`/global-knowledge/bases/${editingCompanyBaseId}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: companyForm.name,
          description: companyForm.description,
        }),
      });
      setCompanyDialogOpen(false);
      setCompanyForm(emptyCompanyForm);
      setCompanyDialogMode("create");
      setEditingCompanyBaseId("");
      await loadCompanyBases();
      if (companyView === "detail" && selectedCompanyBase?.id === base.id) {
        setSelectedCompanyBase(base);
        await refreshCompanyTree(base.id);
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "编辑公司知识库失败。");
    } finally {
      setRunning(false);
    }
  }

  function openCreateCompanyDialog() {
    setCompanyForm(emptyCompanyForm);
    setCompanyDialogMode("create");
    setEditingCompanyBaseId("");
    setCompanyDialogOpen(true);
  }

  function openEditCompanyDialog(base: ApiCompanyKnowledgeBase) {
    setCompanyForm({ name: base.name, description: base.description ?? "" });
    setCompanyDialogMode("edit");
    setEditingCompanyBaseId(base.id);
    setCompanyDialogOpen(true);
  }

  function returnToCompanyList() {
    setCompanyView("list");
    setSelectedCompanyBase(null);
    setCompanyTree(null);
    setSelectedCompanyFile(null);
    setSelectedTreeNodeId("");
    setActiveFolderId("");
    setExpandedFolderIds([]);
    setCompanyTreeSearch("");
    setCompanySidebarOpen(false);
    setDeleteBaseTarget(null);
    setDeleteTarget(null);
  }

  function handleKnowledgeScopeChange(value: string) {
    const nextScope = value as (typeof knowledgeScopes)[number]["value"];
    if (nextScope === "company" && activeScope === "company" && companyView === "detail") {
      returnToCompanyList();
      return;
    }
    setActiveScope(nextScope);
  }

  async function createCompanyFolder() {
    if (!selectedCompanyBase || !activeFolderId) {
      return;
    }
    setRunning(true);
    setError("");
    try {
      const folder = await apiRequest<ApiCompanyKnowledgeFolder>(
        `/global-knowledge/bases/${selectedCompanyBase.id}/folders`,
        {
          method: "POST",
          body: JSON.stringify({ parent_id: activeFolderId, name: folderName }),
        },
      );
      setFolderDialogOpen(false);
      setFolderName("");
      setSelectedTreeNodeId(folder.id);
      setActiveFolderId(folder.id);
      setExpandedFolderIds((ids) => Array.from(new Set([...ids, activeFolderId, folder.id])));
      await refreshCompanyTree(selectedCompanyBase.id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "新建文件夹失败。");
    } finally {
      setRunning(false);
    }
  }

  async function uploadCompanyFiles() {
    if (!selectedCompanyBase || !activeFolderId || companyFiles.length === 0) {
      setError("请先选择要上传的文件。");
      return;
    }
    const unsupported = companyFiles.find((file) => !/\.(md|markdown)$/i.test(file.name));
    if (unsupported) {
      setError(`仅支持 Markdown（.md）文件：${unsupported.name}`);
      return;
    }
    setRunning(true);
    setError("");
    setCompanyUploadStates(
      Object.fromEntries(
        companyFiles.map((file) => [companyUploadFileKey(file), { progress: 1, status: "uploading" as const }]),
      ),
    );
    try {
      const result = await new Promise<ApiCompanyKnowledgeUploadResult>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open(
          "POST",
          `${API_BASE_URL}/global-knowledge/bases/${selectedCompanyBase.id}/folders/${activeFolderId}/files`,
        );
        const headers = apiAuthHeaders();
        headers.forEach((value, key) => {
          xhr.setRequestHeader(key, value);
        });
        xhr.upload.onprogress = (event) => {
          if (!event.lengthComputable) {
            return;
          }
          const progress = Math.min(99, Math.round((event.loaded / event.total) * 100));
          setCompanyUploadStates(
            Object.fromEntries(
              companyFiles.map((file) => [companyUploadFileKey(file), { progress, status: "uploading" as const }]),
            ),
          );
        };
        xhr.onload = () => {
          let payload: unknown = null;
          if (xhr.responseText) {
            try {
              payload = JSON.parse(xhr.responseText);
            } catch {
              payload = null;
            }
          }
          if (xhr.status >= 200 && xhr.status < 300 && payload) {
            resolve(payload as ApiCompanyKnowledgeUploadResult);
            return;
          }
          reject(new Error((payload as { detail?: { message?: string } })?.detail?.message || "上传文件失败。"));
        };
        xhr.onerror = () => reject(new Error("网络异常，文件上传失败。"));
        const formData = new FormData();
        companyFiles.forEach((file) => {
          formData.append("files", file);
        });
        xhr.send(formData);
      });
      setCompanyUploadStates(
        Object.fromEntries(
          companyFiles.map((file) => [companyUploadFileKey(file), { progress: 100, status: "completed" as const }]),
        ),
      );
      setUploadDialogOpen(false);
      setCompanyFiles([]);
      await refreshCompanyTree(selectedCompanyBase.id);
      if (result.files[0]) {
        await selectCompanyFile(result.files[0].id);
      }
      await loadCompanyBases();
    } catch (nextError) {
      setCompanyUploadStates(
        Object.fromEntries(
          companyFiles.map((file) => [companyUploadFileKey(file), { progress: 0, status: "error" as const }]),
        ),
      );
      setError(nextError instanceof Error ? nextError.message : "上传文件失败。");
    } finally {
      setRunning(false);
    }
  }

  async function selectCompanyFile(fileId: string) {
    if (!selectedCompanyBase) {
      return;
    }
    setRunning(true);
    setError("");
    try {
      const file = await apiRequest<ApiCompanyKnowledgeFile>(
        `/global-knowledge/bases/${selectedCompanyBase.id}/files/${fileId}`,
      );
      setSelectedCompanyFile(file);
      setSelectedTreeNodeId(file.id);
      setActiveFolderId(file.folder_id);
      if (companyTree) {
        setExpandedFolderIds((ids) =>
          Array.from(new Set([...ids, ...collectAncestorFolderIds(companyTree.root, file.id)])),
        );
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "加载文件内容失败。");
    } finally {
      setRunning(false);
    }
  }

  async function deleteCompanyTreeNode() {
    if (!selectedCompanyBase || !deleteTarget) {
      return;
    }
    setRunning(true);
    setError("");
    try {
      if (deleteTarget.type === "file") {
        await apiRequest<{ deleted: boolean }>(
          `/global-knowledge/bases/${selectedCompanyBase.id}/files/${deleteTarget.id}`,
          {
            method: "DELETE",
          },
        );
        if (selectedCompanyFile?.id === deleteTarget.id) {
          setSelectedCompanyFile(null);
          setSelectedTreeNodeId(activeFolderId || companyTree?.root.id || "");
        }
      } else {
        await apiRequest<{ deleted: boolean }>(
          `/global-knowledge/bases/${selectedCompanyBase.id}/folders/${deleteTarget.id}`,
          {
            method: "DELETE",
          },
        );
        const deletedActiveNode = selectedTreeNodeId
          ? companyTreeContainsNode(deleteTarget, selectedTreeNodeId)
          : false;
        const deletedPreviewFile = selectedCompanyFile
          ? companyTreeContainsNode(deleteTarget, selectedCompanyFile.id)
          : false;
        if (deletedActiveNode || deletedPreviewFile) {
          setSelectedCompanyFile(null);
          setSelectedTreeNodeId(companyTree?.root.id || "");
          setActiveFolderId(companyTree?.root.id || "");
        }
      }
      setDeleteTarget(null);
      await refreshCompanyTree(selectedCompanyBase.id);
      await loadCompanyBases();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "删除失败。");
    } finally {
      setRunning(false);
    }
  }

  async function deleteCompanyBase() {
    if (!deleteBaseTarget) {
      return;
    }
    setRunning(true);
    setError("");
    try {
      await apiRequest<{ deleted: boolean }>(`/global-knowledge/bases/${deleteBaseTarget.id}`, {
        method: "DELETE",
      });
      if (selectedCompanyBase?.id === deleteBaseTarget.id) {
        setSelectedCompanyBase(null);
        setCompanyTree(null);
        setSelectedCompanyFile(null);
        setSelectedTreeNodeId("");
        setActiveFolderId("");
      }
      setDeleteBaseTarget(null);
      await loadCompanyBases();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "删除知识库失败。");
    } finally {
      setRunning(false);
    }
  }

  function selectCompanyKnowledgeHome() {
    if (!companyTree) {
      return;
    }
    setSelectedCompanyFile(null);
    setSelectedTreeNodeId("");
    setActiveFolderId(companyTree.root.id);
  }

  function selectCompanyFolder(folder: ApiCompanyKnowledgeFolder) {
    setSelectedTreeNodeId(folder.id);
    setActiveFolderId(folder.id);
    setSelectedCompanyFile(null);
    if (companyTree) {
      setExpandedFolderIds((ids) =>
        Array.from(new Set([...ids, ...collectAncestorFolderIds(companyTree.root, folder.id), folder.id])),
      );
    }
  }

  function toggleCompanyFolder(folderId: string) {
    setExpandedFolderIds((ids) => (ids.includes(folderId) ? ids.filter((id) => id !== folderId) : [...ids, folderId]));
  }

  function expandAllCompanyFolders() {
    if (!companyTree) {
      return;
    }
    setExpandedFolderIds(collectCompanyFolderIds(companyTree.root).filter((id) => id !== companyTree.root.id));
  }

  function collapseAllCompanyFolders() {
    setExpandedFolderIds([]);
  }

  function openFolderCreate(folderId: string) {
    setActiveFolderId(folderId);
    setFolderName("");
    setFolderDialogOpen(true);
  }

  function openFolderUpload(folderId: string) {
    setActiveFolderId(folderId);
    setCompanyFiles([]);
    setCompanyUploadStates({});
    setUploadDialogOpen(true);
  }

  return (
    <PageShell
      breadcrumbs={[{ label: "项目工作区" }, { label: "知识库" }]}
      description="查看项目知识库与公司知识库的知识块、来源材料和版本记录。"
      fillViewport
      projectScope="all"
      title="知识库"
    >
      <Tabs onValueChange={handleKnowledgeScopeChange} value={activeScope}>
        <TabsList className="h-auto flex-wrap justify-start">
          {knowledgeScopes.map(({ icon: Icon, label, value }) => (
            <TabsTrigger
              className="h-8 gap-1.5 px-3"
              key={value}
              onClick={() => {
                if (value === "company" && activeScope === "company" && companyView === "detail") {
                  returnToCompanyList();
                }
              }}
              value={value}
            >
              <Icon className="size-4" />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {isCompanyKnowledge && companyView === "list" ? (
        <ShellSection>
          <ListToolbar
            createDisabled={running}
            createLabel={running ? "处理中" : "创建知识库"}
            onCreate={openCreateCompanyDialog}
            onSearch={setSearchText}
            placeholder="搜索公司知识库"
            selectedCount={selectedCompanyCount}
            title="公司知识库列表"
          />
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <Checkbox
                      aria-label="选择全部知识库"
                      checked={allCompanySelected || (partiallyCompanySelected ? "indeterminate" : false)}
                      onCheckedChange={(checked) => toggleAllCompany(Boolean(checked))}
                    />
                  </TableHead>
                  <TableHead>知识库名称</TableHead>
                  <TableHead>描述</TableHead>
                  <TableHead>文件数量</TableHead>
                  <TableHead>更新时间</TableHead>
                  <TableHead className="w-16">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCompanyRows.map((item) => (
                  <TableRow data-state={selectedCompanyIds.includes(item.id) ? "selected" : undefined} key={item.id}>
                    <TableCell>
                      <Checkbox
                        aria-label={`选择 ${item.id}`}
                        checked={selectedCompanyIds.includes(item.id)}
                        onCheckedChange={(checked) => toggleOneCompany(item.id, Boolean(checked))}
                      />
                    </TableCell>
                    <TableCell>
                      <button
                        className="text-left font-medium hover:underline"
                        onClick={() => void openCompanyBase(item.id)}
                        type="button"
                      >
                        {item.name}
                      </button>
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-muted-foreground">{item.description || "—"}</TableCell>
                    <TableCell>{item.file_count}</TableCell>
                    <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                    <TableCell>
                      <RowActions
                        actions={[
                          { label: "查看", icon: Eye, onSelect: () => void openCompanyBase(item.id) },
                          { label: "编辑", icon: Pencil, onSelect: () => openEditCompanyDialog(item) },
                          { label: "删除", icon: Trash2, destructive: true, onSelect: () => setDeleteBaseTarget(item) },
                        ]}
                        label="打开操作菜单"
                      />
                    </TableCell>
                  </TableRow>
                ))}
                {filteredCompanyRows.length === 0 ? (
                  <TableRow>
                    <TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
                      {loading ? "正在加载公司知识库。" : "暂无公司知识库。"}
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>
          {error ? <p className="mt-3 text-destructive text-sm">{error}</p> : null}
        </ShellSection>
      ) : null}
      {isCompanyKnowledge && companyView === "detail" ? (
        <>
          {error ? <p className="mb-3 text-destructive text-sm">{error}</p> : null}
          {companyTree && selectedCompanyBase ? (
            <CompanyKnowledgeVault
              activeFolderId={activeFolderId || companyTree.root.id}
              activeNodeId={selectedTreeNodeId}
              base={selectedCompanyBase}
              expandedFolderIds={expandedFolderIds}
              file={selectedCompanyFile}
              onCollapseAll={collapseAllCompanyFolders}
              onDelete={setDeleteTarget}
              onExpandAll={expandAllCompanyFolders}
              onFileSelect={(fileId) => void selectCompanyFile(fileId)}
              onFolderCreate={openFolderCreate}
              onFolderSelect={selectCompanyFolder}
              onFolderToggle={toggleCompanyFolder}
              onFolderUpload={openFolderUpload}
              onHomeSelect={selectCompanyKnowledgeHome}
              onBackToList={returnToCompanyList}
              onSidebarOpenChange={setCompanySidebarOpen}
              onTreeSearchChange={setCompanyTreeSearch}
              root={companyTree.root}
              running={running}
              sidebarOpen={companySidebarOpen}
              treeSearch={companyTreeSearch}
            />
          ) : (
            <div className="rounded-lg border p-6 text-muted-foreground text-sm">正在加载知识库目录。</div>
          )}
        </>
      ) : null}
      {!isCompanyKnowledge ? (
        <ProjectKnowledgeWorkspace
          activeConversationId={activeProjectConversationId}
          conversations={projectConversations}
          error={error}
          loading={loading}
          messages={projectMessages}
          modelLoading={knowledgeModelLoading}
          modelProviders={knowledgeModelProviders}
          modelSaving={knowledgeModelSaving}
          onConversationOpen={(conversationId) => {
            if (effectiveKnowledgeScope === "all") {
              void openProjectConversation("all", conversationId);
              return;
            }
            if (projectId) {
              void openProjectConversation("project", conversationId, projectId);
            }
          }}
          onConversationCreate={createProjectConversation}
          onConversationDelete={(conversationId) => void deleteProjectConversation(conversationId)}
          onModelProviderChange={(modelProviderId) => void updateKnowledgeQueryModelProvider(modelProviderId)}
          onShowThinkingChange={setShowProjectThinking}
          onStop={stopProjectKnowledgeQuery}
          onSubmit={(question) => void queryProjectKnowledge(question)}
          projectSelected={effectiveKnowledgeScope === "all" || Boolean(projectId)}
          projectConversationEnabled={effectiveKnowledgeScope === "all" || Boolean(projectId)}
          running={running}
          selectedModelProviderId={selectedKnowledgeModelProviderId}
          showThinking={showProjectThinking}
          value={projectChatDraft}
          onValueChange={setProjectChatDraft}
        />
      ) : null}
      <CompanyKnowledgeDialog
        form={companyForm}
        mode={companyDialogMode}
        onFormChange={setCompanyForm}
        onOpenChange={(open) => {
          setCompanyDialogOpen(open);
          if (!open) {
            setCompanyForm(emptyCompanyForm);
            setCompanyDialogMode("create");
            setEditingCompanyBaseId("");
          }
        }}
        onSubmit={() => void (companyDialogMode === "edit" ? updateCompanyBase() : createCompanyBase())}
        open={companyDialogOpen}
        running={running}
      />
      <CompanyFolderDialog
        name={folderName}
        onNameChange={setFolderName}
        onOpenChange={setFolderDialogOpen}
        onSubmit={() => void createCompanyFolder()}
        open={folderDialogOpen}
        running={running}
      />
      <CompanyUploadDialog
        files={companyFiles}
        uploadStates={companyUploadStates}
        onFilesChange={setCompanyFiles}
        onOpenChange={(open) => {
          setUploadDialogOpen(open);
          if (!open && !running) {
            setCompanyUploadStates({});
          }
        }}
        onSubmit={() => void uploadCompanyFiles()}
        open={uploadDialogOpen}
        running={running}
        targetFolderLabel={
          companyTree && selectedCompanyBase
            ? resolveCompanyTargetFolderLabel(
                companyTree.root,
                selectedCompanyBase.name,
                activeFolderId || companyTree.root.id,
              )
            : undefined
        }
      />
      <DeleteCompanyNodeDialog
        base={deleteBaseTarget}
        onBaseSubmit={() => void deleteCompanyBase()}
        onBaseOpenChange={(open) => {
          if (!open) {
            setDeleteBaseTarget(null);
          }
        }}
        node={deleteTarget}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
          }
        }}
        onSubmit={() => void deleteCompanyTreeNode()}
        running={running}
      />
    </PageShell>
  );
}

function projectMessageFromApi(message: ApiKnowledgeConversationMessage): ProjectChatMessage {
  return {
    id: message.id,
    role: message.role,
    body: message.content,
  };
}

function mergeAssistantStreamResult(message: ProjectChatMessage, result: ApiKnowledgeQueryResult): ProjectChatMessage {
  const assistant = result.messages.find((item) => item.role === "assistant");
  const thinkingCompletedAt =
    message.thinking && !message.thinkingCompletedAt ? Date.now() : message.thinkingCompletedAt;
  return {
    ...message,
    body: assistant?.content || result.answer || message.body,
    thinkingCompletedAt,
  };
}

function parseProjectKnowledgeStreamEvent(chunk: string): ProjectKnowledgeStreamEvent | null {
  const dataLine = chunk
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line.startsWith("data:"));
  if (!dataLine) {
    return null;
  }
  try {
    const payload = JSON.parse(dataLine.slice(5).trim()) as ProjectKnowledgeStreamEvent;
    if (!payload || typeof payload !== "object" || !("type" in payload)) {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

function sanitizeThinkingText(value: string): string {
  return value
    .replace(/<!--\s*source_metadata:[\s\S]*?-->/gi, "")
    .split(/\r?\n/)
    .map((line) =>
      line
        .replace(/^\s*\d+\s+(?=\S)/, "")
        .replace(/^\s*(read_file|grep|glob|ls)\b.*$/i, "")
        .trim(),
    )
    .filter(Boolean)
    .join("\n");
}

function formatThinkingItems(value: string): string[] {
  const seen = new Set<string>();
  return sanitizeThinkingText(value)
    .split(/\r?\n+/)
    .map((line) => line.replace(/^[-*]\s+/, "").trim())
    .filter((line) => {
      if (!line || seen.has(line)) {
        return false;
      }
      seen.add(line);
      return true;
    })
    .slice(0, 8);
}

function formatThinkingElapsedSeconds(startedAt?: number, completedAt?: number): string {
  if (!startedAt) {
    return "";
  }
  const elapsedMs = Math.max(0, (completedAt ?? Date.now()) - startedAt);
  const seconds = Math.max(1, Math.round(elapsedMs / 1000));
  return `用时 ${seconds} 秒`;
}

function upsertConversation(
  conversations: ApiKnowledgeConversation[],
  conversation: ApiKnowledgeConversation,
): ApiKnowledgeConversation[] {
  return [conversation, ...conversations.filter((item) => item.id !== conversation.id)];
}

function ProjectKnowledgeWorkspace({
  activeConversationId,
  conversations,
  error,
  loading,
  messages,
  modelLoading,
  modelProviders,
  modelSaving,
  onConversationCreate,
  onConversationDelete,
  onConversationOpen,
  onModelProviderChange,
  onShowThinkingChange,
  onStop,
  onSubmit,
  projectConversationEnabled,
  projectSelected,
  running,
  selectedModelProviderId,
  showThinking,
  value,
  onValueChange,
}: {
  activeConversationId: string | null;
  conversations: ApiKnowledgeConversation[];
  error: string;
  loading: boolean;
  messages: ProjectChatMessage[];
  modelLoading: boolean;
  modelProviders: ApiModelProvider[];
  modelSaving: boolean;
  onConversationCreate: () => void;
  onConversationDelete: (conversationId: string) => void;
  onConversationOpen: (conversationId: string) => void;
  onModelProviderChange: (modelProviderId: string) => void;
  onShowThinkingChange: (value: boolean) => void;
  onStop: () => void;
  onSubmit: (instruction: string) => void;
  projectConversationEnabled: boolean;
  projectSelected: boolean;
  running: boolean;
  selectedModelProviderId: string;
  showThinking: boolean;
  value: string;
  onValueChange: (value: string) => void;
}) {
  const hasConversation = messages.length > 0 || running;
  const [historyOpen, setHistoryOpen] = useState(false);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const lastScrollTopRef = useRef(0);
  const latestMessage = messages[messages.length - 1];
  const projectHistoryOpen = historyOpen;
  const latestMessageScrollKey = [
    messages.length,
    latestMessage?.id,
    latestMessage?.body,
    error,
    projectHistoryOpen,
    running,
  ].join("|");
  const chatControl = (
    <KnowledgeChatTopControls
      historyOpen={projectHistoryOpen}
      onConversationCreate={onConversationCreate}
      onHistoryOpen={() => {
        if (!projectSelected || running) {
          return;
        }
        setHistoryOpen(true);
      }}
      onHistoryClose={() => {
        if (!projectSelected || running) {
          return;
        }
        setHistoryOpen(false);
      }}
      onShowThinkingChange={onShowThinkingChange}
      projectSelected={projectSelected}
      running={running}
      showThinking={showThinking}
    />
  );

  const handleMessageListScroll = useCallback(() => {
    const list = messageListRef.current;
    if (!list) {
      return;
    }

    const distanceToBottom = list.scrollHeight - list.scrollTop - list.clientHeight;
    const scrollingUp = list.scrollTop < lastScrollTopRef.current;
    lastScrollTopRef.current = list.scrollTop;

    if (scrollingUp && distanceToBottom > 24) {
      setAutoScrollEnabled(false);
      return;
    }

    if (distanceToBottom <= 24) {
      setAutoScrollEnabled(true);
    }
  }, []);

  const handleSubmit = useCallback(
    (instruction: string) => {
      setAutoScrollEnabled(true);
      onSubmit(instruction);
    },
    [onSubmit],
  );

  useLayoutEffect(() => {
    if (!hasConversation || !autoScrollEnabled || latestMessageScrollKey.length === 0) {
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      const list = messageListRef.current;
      if (!list) {
        return;
      }
      list.scrollTo({ top: list.scrollHeight, behavior: "auto" });
      lastScrollTopRef.current = list.scrollTop;
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [autoScrollEnabled, hasConversation, latestMessageScrollKey]);

  useEffect(() => {
    void activeConversationId;
    setAutoScrollEnabled(true);
    lastScrollTopRef.current = 0;
  }, [activeConversationId]);

  useEffect(() => {
    if (!projectSelected) {
      setHistoryOpen(false);
    }
  }, [projectSelected]);

  return (
    <ShellSection className="min-h-[28rem] flex-1 overflow-hidden p-0">
      <div
        className={
          projectHistoryOpen
            ? "grid h-full min-h-0 rounded-lg border bg-background lg:grid-cols-[18rem_minmax(0,1fr)]"
            : "relative grid h-full min-h-0 rounded-lg border bg-background"
        }
      >
        {projectHistoryOpen ? (
          <aside className="flex min-h-[16rem] flex-col border-b bg-muted/20 lg:border-r lg:border-b-0">
            <div className="flex items-center justify-between gap-2 border-b bg-muted/30 p-3">
              <div className="flex items-center gap-2 font-medium text-sm">
                <MessageSquare className="size-4 text-primary" />
                对话
              </div>
              <div className="flex items-center gap-1">
                <Button onClick={() => setHistoryOpen(false)} size="icon" title="收起对话历史" variant="ghost">
                  <PanelLeftClose className="size-4" />
                </Button>
                <Button
                  disabled={!projectSelected || running}
                  onClick={onConversationCreate}
                  size="icon"
                  title="新建对话"
                  variant="outline"
                >
                  <Plus className="size-4" />
                </Button>
              </div>
            </div>
            <div className="max-h-[calc(100dvh-20rem)] min-h-0 flex-1 space-y-1 overflow-auto p-2 lg:sticky lg:top-4 lg:max-h-[calc(100dvh-18rem)]">
              {loading ? (
                <div className="px-2 py-3 text-muted-foreground text-sm">正在加载对话。</div>
              ) : conversations.length === 0 ? (
                <div className="px-2 py-3 text-muted-foreground text-sm">暂无历史对话。</div>
              ) : null}
              {conversations.map((conversation) => {
                const active = conversation.id === activeConversationId;
                return (
                  <div className="group flex items-center gap-1" key={conversation.id}>
                    <button
                      className={
                        active
                          ? "min-w-0 flex-1 rounded-md bg-primary px-2.5 py-2 text-left text-primary-foreground text-sm shadow-sm"
                          : "min-w-0 flex-1 rounded-md px-2.5 py-2 text-left text-muted-foreground text-sm transition-colors hover:bg-muted hover:text-foreground"
                      }
                      disabled={!projectConversationEnabled || running}
                      onClick={() => onConversationOpen(conversation.id)}
                      type="button"
                    >
                      <div className="truncate font-medium">{conversation.title}</div>
                      <div className="mt-0.5 truncate text-[11px] opacity-70">
                        {formatDateTime(conversation.updated_at)}
                      </div>
                    </button>
                    <button
                      className="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-70 transition-colors hover:bg-destructive/10 hover:text-destructive disabled:cursor-not-allowed disabled:opacity-40 lg:opacity-0 lg:group-hover:opacity-100"
                      disabled={!projectConversationEnabled || running}
                      onClick={() => onConversationDelete(conversation.id)}
                      title="删除对话"
                      type="button"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          </aside>
        ) : null}

        {!hasConversation ? (
          <div className="relative flex h-full min-h-0 flex-col items-center justify-center px-4 py-6 min-[900px]:py-10">
            <div className="relative mb-5 text-center min-[900px]:mb-8">
              <div className="mx-auto mb-1 flex size-[72px] items-center justify-center min-[900px]:size-24">
                <ProjectKnowledgeIcon className="size-[72px] object-contain min-[900px]:size-24" />
              </div>
              <div className="mb-2 flex items-center justify-center gap-2 font-semibold text-[11px] text-muted-foreground uppercase tracking-[0.18em] min-[900px]:mb-3 min-[900px]:text-xs">
                <span className="h-px w-8 bg-border" />
                Source-backed QA
                <span className="h-px w-8 bg-border" />
              </div>
              <h2 className="font-heading text-3xl text-foreground tracking-normal min-[900px]:text-5xl">项目知识库</h2>
              <p className="mx-auto mt-2 max-w-xl text-muted-foreground text-sm leading-6 min-[900px]:mt-3">
                查询最终需求文档和探索记录，把业务规则、页面事实和测试风险串成可追溯答案。
              </p>
            </div>
            <KnowledgeChatInput
              compact
              disabled={!projectSelected}
              leadingControl={chatControl}
              loading={running}
              modelLoading={modelLoading}
              modelProviders={modelProviders}
              modelSaving={modelSaving}
              onModelProviderChange={onModelProviderChange}
              onStop={onStop}
              onSubmit={handleSubmit}
              onValueChange={onValueChange}
              selectedModelProviderId={selectedModelProviderId}
              value={value}
            />
            <div className="relative mt-4 flex max-w-2xl flex-wrap justify-center gap-2 px-4 min-[900px]:mt-5">
              {projectKnowledgeQuickPrompts.map(({ icon: Icon, label, prompt }) => (
                <button
                  className="inline-flex items-center gap-1.5 rounded-md border bg-background px-2.5 py-1.5 text-muted-foreground text-xs shadow-sm transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50 min-[900px]:px-3 min-[900px]:text-sm"
                  disabled={!projectSelected || running}
                  key={label}
                  onClick={() => onValueChange(prompt)}
                  type="button"
                >
                  <Icon className="size-4" />
                  {label}
                </button>
              ))}
            </div>
            {error ? (
              <div className="relative mt-4 max-w-2xl rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-destructive text-sm">
                {error}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="relative flex h-full min-h-0 min-w-0 flex-col">
            <div
              className="min-h-0 flex-1 space-y-4 overflow-y-auto bg-muted/20 px-4 pt-4 pb-44 min-[900px]:px-10"
              onScroll={handleMessageListScroll}
              ref={messageListRef}
            >
              {messages.map((message) => (
                <ChatMessage
                  body={message.body}
                  icon={message.role === "user" ? User : ProjectKnowledgeIcon}
                  key={message.id}
                  loading={running && message.role === "assistant" && message.body.length === 0}
                  thinking={message.thinking}
                  thinkingCompletedAt={message.thinkingCompletedAt}
                  thinkingStartedAt={message.thinkingStartedAt}
                  title={message.role === "user" ? "你" : "项目知识库 AI"}
                  tone={message.role === "user" ? "user" : "assistant"}
                />
              ))}
              {error ? <ChatMessage body={error} icon={TriangleAlert} title="查询失败" tone="warning" /> : null}
            </div>
            <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 bg-gradient-to-t from-muted/80 via-muted/45 to-transparent px-4 pt-8 pb-4 min-[900px]:px-10">
              <KnowledgeChatInput
                compact
                disabled={!projectSelected}
                leadingControl={chatControl}
                loading={running}
                modelLoading={modelLoading}
                modelProviders={modelProviders}
                modelSaving={modelSaving}
                onModelProviderChange={onModelProviderChange}
                onStop={onStop}
                onSubmit={handleSubmit}
                onValueChange={onValueChange}
                selectedModelProviderId={selectedModelProviderId}
                value={value}
                wrapperClassName="pointer-events-auto"
              />
            </div>
          </div>
        )}
      </div>
    </ShellSection>
  );
}

function KnowledgeChatTopControls({
  historyOpen,
  onConversationCreate,
  onHistoryClose,
  onHistoryOpen,
  projectSelected,
  running,
  showThinking,
  onShowThinkingChange,
}: {
  historyOpen: boolean;
  onConversationCreate: () => void;
  onHistoryClose: () => void;
  onHistoryOpen: () => void;
  projectSelected: boolean;
  running: boolean;
  showThinking: boolean;
  onShowThinkingChange: (value: boolean) => void;
}) {
  const controlDisabledReason = !projectSelected ? "请选择知识库后使用对话" : "查询中";
  const createTitle = projectSelected && !running ? "新增会话" : controlDisabledReason;
  const historyTitle = projectSelected && !running ? (historyOpen ? "关闭历史" : "展开历史") : controlDisabledReason;
  const thinkingTitle = showThinking ? "关闭深度思考显示" : "显示深度思考内容";

  return (
    <div className="flex shrink-0 items-center gap-1">
      <button
        aria-label="新建对话"
        className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-45"
        disabled={!projectSelected || running}
        onClick={onConversationCreate}
        title={createTitle}
        type="button"
      >
        <Plus className="size-4" />
      </button>
      <button
        aria-label="深度思考"
        aria-pressed={showThinking}
        className={
          showThinking
            ? "inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-45"
            : "inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-45"
        }
        disabled={!projectSelected || running}
        onClick={() => onShowThinkingChange(!showThinking)}
        title={thinkingTitle}
        type="button"
      >
        <Brain className="size-4" />
      </button>
      <button
        aria-label="展开对话历史"
        className={
          historyOpen
            ? "inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted text-foreground transition-colors hover:bg-muted/80 disabled:cursor-not-allowed disabled:opacity-45"
            : "inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-45"
        }
        disabled={!projectSelected || running}
        onClick={historyOpen ? onHistoryClose : onHistoryOpen}
        title={historyTitle}
        type="button"
      >
        {historyOpen ? <PanelLeftClose className="size-4" /> : <PanelLeftOpen className="size-4" />}
      </button>
    </div>
  );
}

function ChatMessage({
  body,
  children,
  icon: Icon,
  loading = false,
  thinking = "",
  thinkingCompletedAt,
  thinkingStartedAt,
  title,
  tone,
}: {
  body: string;
  children?: React.ReactNode;
  icon: React.ComponentType<{ className?: string }>;
  loading?: boolean;
  thinking?: string;
  thinkingCompletedAt?: number;
  thinkingStartedAt?: number;
  title: string;
  tone: "assistant" | "user" | "warning";
}) {
  const isUser = tone === "user";
  const thinkingItems = formatThinkingItems(thinking);
  const showThinking = tone === "assistant" && thinkingItems.length > 0;
  const thinkingElapsed = formatThinkingElapsedSeconds(thinkingStartedAt, thinkingCompletedAt);
  const thinkingStatus = loading ? "思考中" : "已思考";
  return (
    <div className={isUser ? "flex justify-end" : "flex justify-start"}>
      <div className={isUser ? "max-w-[82%]" : "max-w-[88%]"}>
        <div className={isUser ? "flex flex-row-reverse items-center gap-2" : "flex items-center gap-2"}>
          <div className="flex size-7 items-center justify-center rounded-md border bg-background">
            <Icon className="size-4" />
          </div>
          <div className="font-medium text-muted-foreground text-xs">{title}</div>
        </div>
        <div
          className={
            isUser
              ? "mt-2 rounded-lg bg-primary p-3 text-primary-foreground text-sm shadow-sm"
              : loading && body.length === 0
                ? "mt-2 px-1 py-2 text-foreground text-sm"
                : tone === "warning"
                  ? "mt-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-destructive text-sm"
                  : "mt-2 rounded-lg border bg-background p-3 text-foreground text-sm shadow-sm"
          }
        >
          {showThinking ? (
            <details className="group mb-3 text-sm" open={loading}>
              <summary className="flex cursor-pointer list-none items-center gap-2 text-muted-foreground transition-colors hover:text-foreground">
                <Brain className="size-4 shrink-0 text-primary" />
                <span className="font-medium">
                  {thinkingStatus}
                  {thinkingElapsed ? `（${thinkingElapsed}）` : ""}
                </span>
                <ChevronDown className="size-4 shrink-0 transition-transform group-open:rotate-180" />
              </summary>
              <ol className="mt-3 max-h-56 space-y-3 overflow-auto border-muted-foreground/20 border-l pl-5 text-muted-foreground">
                {thinkingItems.map((item, index) => (
                  <li className="relative leading-6" key={item}>
                    <span className="absolute -left-[1.45rem] mt-2 size-1.5 rounded-full bg-muted-foreground/60" />
                    <span className="min-w-0 break-words">
                      {thinkingItems.length > 1 ? `${index + 1}. ` : ""}
                      {item}
                    </span>
                  </li>
                ))}
              </ol>
            </details>
          ) : null}
          {loading && body.length === 0 ? (
            <PulsatingDots className="min-h-6 justify-start px-0.5" />
          ) : tone === "assistant" ? (
            <MarkdownPreview className="knowledge-chat-markdown" content={body} emptyText="" />
          ) : (
            <p className="whitespace-pre-wrap leading-6">{body}</p>
          )}
          {children}
        </div>
      </div>
    </div>
  );
}

function CompanyDirectoryAddMenu({
  onFolderCreate,
  onFolderUpload,
  running,
  targetLabel,
}: {
  onFolderCreate: () => void;
  onFolderUpload: () => void;
  running: boolean;
  targetLabel: string;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button disabled={running} size="icon" title={`添加到：${targetLabel}`} variant="ghost">
          <Plus className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onSelect={onFolderCreate}>
          <Folder className="size-4" />
          新建文件夹
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={onFolderUpload}>
          <Upload className="size-4" />
          上传 Markdown
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function CompanyKnowledgeHub({
  base,
  folder,
  onFileSelect,
  onFolderSelect,
  root,
  sidebarOpen,
}: {
  base: ApiCompanyKnowledgeBase;
  folder: ApiCompanyKnowledgeFolder;
  onFileSelect: (fileId: string) => void;
  onFolderSelect: (folder: ApiCompanyKnowledgeFolder) => void;
  root: ApiCompanyKnowledgeFolder;
  sidebarOpen: boolean;
}) {
  const isRoot = folder.id === root.id;
  const { folders: folderCount, files: fileCount } = countCompanyFolderChildren(folder);
  const subfolders = folder.children.filter((node): node is ApiCompanyKnowledgeFolder => node.type === "folder");
  const files = folder.children.filter((node): node is ApiCompanyKnowledgeFile => node.type === "file");
  const gridClass = sidebarOpen ? "grid gap-2 sm:grid-cols-2" : "grid gap-2 sm:grid-cols-2 lg:grid-cols-3";

  function renderNodeCard(node: ApiCompanyKnowledgeTreeNode) {
    return (
      <button
        className="flex items-center gap-2 rounded-lg border bg-background px-4 py-3 text-left text-sm transition-colors hover:bg-muted/60"
        key={node.id}
        onClick={() => {
          if (node.type === "file") {
            onFileSelect(node.id);
            return;
          }
          onFolderSelect(node);
        }}
        type="button"
      >
        {node.type === "folder" ? (
          <Folder className="size-4 shrink-0 text-muted-foreground" />
        ) : (
          <FileText className="size-4 shrink-0 text-muted-foreground" />
        )}
        <span className="truncate">{node.name}</span>
      </button>
    );
  }

  return (
    <div
      className={
        sidebarOpen
          ? "flex h-full min-h-[32rem] flex-col items-center justify-center px-6 py-10"
          : "flex h-full min-h-[32rem] flex-col justify-center px-8 py-10 lg:px-12"
      }
    >
      <div className={sidebarOpen ? "w-full max-w-2xl space-y-6" : "w-full space-y-6"}>
        <div className="space-y-1 text-center">
          <h2 className="font-semibold text-2xl tracking-tight">{isRoot ? base.name : folder.name}</h2>
          <p className="text-muted-foreground text-sm">
            {isRoot
              ? `${base.description || "公司知识库"} · ${base.file_count} 篇文档`
              : `${folderCount} 个子目录 · ${fileCount} 篇文档`}
          </p>
        </div>
        {folder.children.length === 0 ? (
          <p className="text-center text-muted-foreground text-sm">此目录暂无内容，可从左侧上传或新建。</p>
        ) : (
          <div className="space-y-4">
            {subfolders.length > 0 ? (
              <div className="space-y-2">
                <p className="font-medium text-muted-foreground text-xs uppercase tracking-wide">子目录</p>
                <div className={gridClass}>{subfolders.map((node) => renderNodeCard(node))}</div>
              </div>
            ) : null}
            {files.length > 0 ? (
              <div className="space-y-2">
                <p className="font-medium text-muted-foreground text-xs uppercase tracking-wide">文档</p>
                <div className={gridClass}>{files.map((node) => renderNodeCard(node))}</div>
              </div>
            ) : null}
          </div>
        )}
        {isRoot ? (
          <p className="text-center text-muted-foreground text-sm">
            {sidebarOpen ? "或从左侧目录展开浏览文档" : "展开左侧目录可浏览全部文档"}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function CompanyReadingTrail({
  items,
  onSelect,
  className,
}: {
  items: CompanyBreadcrumbItem[];
  onSelect: (item: CompanyBreadcrumbItem) => void;
  className?: string;
}) {
  return (
    <nav
      aria-label="阅读路径"
      className={`flex min-w-0 flex-1 flex-wrap items-center gap-1 text-sm ${className ?? ""}`}
    >
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        return (
          <span className="flex min-w-0 items-center gap-1" key={item.id}>
            {index > 0 ? <ChevronRight className="size-3.5 shrink-0 text-muted-foreground/70" /> : null}
            {isLast ? (
              <span className="truncate font-medium text-foreground">{item.name}</span>
            ) : (
              <button
                className="truncate font-medium text-muted-foreground hover:text-foreground"
                onClick={() => onSelect(item)}
                type="button"
              >
                {item.name}
              </button>
            )}
          </span>
        );
      })}
    </nav>
  );
}

function CompanyKnowledgeVault({
  activeFolderId,
  activeNodeId,
  base,
  expandedFolderIds,
  file,
  onCollapseAll,
  onDelete,
  onExpandAll,
  onFileSelect,
  onFolderCreate,
  onFolderSelect,
  onFolderToggle,
  onFolderUpload,
  onHomeSelect,
  onBackToList,
  onSidebarOpenChange,
  onTreeSearchChange,
  root,
  running,
  sidebarOpen,
  treeSearch,
}: {
  activeFolderId: string;
  activeNodeId: string;
  base: ApiCompanyKnowledgeBase;
  expandedFolderIds: string[];
  file: ApiCompanyKnowledgeFile | null;
  onCollapseAll: () => void;
  onDelete: (node: ApiCompanyKnowledgeTreeNode) => void;
  onExpandAll: () => void;
  onFileSelect: (fileId: string) => void;
  onFolderCreate: (folderId: string) => void;
  onFolderSelect: (folder: ApiCompanyKnowledgeFolder) => void;
  onFolderToggle: (folderId: string) => void;
  onFolderUpload: (folderId: string) => void;
  onHomeSelect: () => void;
  onBackToList: () => void;
  onSidebarOpenChange: (open: boolean) => void;
  onTreeSearchChange: (value: string) => void;
  root: ApiCompanyKnowledgeFolder;
  running: boolean;
  sidebarOpen: boolean;
  treeSearch: string;
}) {
  const [previewScrollEl, setPreviewScrollEl] = useState<HTMLDivElement | null>(null);
  const filteredNodes = filterCompanyTreeNodes(root.children, treeSearch);
  const targetFolderLabel = resolveCompanyTargetFolderLabel(root, base.name, activeFolderId);
  const effectiveExpandedIds =
    treeSearch.trim().length > 0
      ? Array.from(new Set([...expandedFolderIds, ...collectFolderIdsFromNodes(filteredNodes)]))
      : expandedFolderIds;

  useEffect(() => {
    const currentFileId = file?.id;
    void currentFileId;
    previewScrollEl?.scrollTo({ top: 0, behavior: "auto" });
  }, [file?.id, previewScrollEl]);

  const currentFolder = resolveCompanyFolder(root, activeFolderId);
  const navigationTargetId = file?.id ?? (activeFolderId || root.id);
  const breadcrumb = resolveCompanyBreadcrumb(root, base.name, navigationTargetId);

  function renderMarkdownPreview(content: string) {
    return (
      <div data-toc-ignore id={COMPANY_KNOWLEDGE_PREVIEW_ID}>
        <MarkdownPreview
          className="requirement-document-preview"
          content={content}
          emptyText="暂无 Markdown 内容。"
          onVaultFileClick={(fileId) => {
            previewScrollEl?.scrollTo({ top: 0, behavior: "auto" });
            onFileSelect(fileId);
          }}
        />
      </div>
    );
  }

  function handleBreadcrumbSelect(item: CompanyBreadcrumbItem) {
    if (item.type === "base") {
      onHomeSelect();
      return;
    }
    if (item.type === "file") {
      onFileSelect(item.id);
      return;
    }
    if (item.type === "folder") {
      const folder = findCompanyFolderInTree(root, item.id);
      if (folder) {
        onFolderSelect(folder);
      }
    }
  }

  return (
    <div
      className={
        sidebarOpen
          ? "grid min-h-[32rem] overflow-hidden rounded-lg border bg-background lg:grid-cols-[18rem_minmax(0,1fr)]"
          : "min-h-[32rem] overflow-hidden rounded-lg border bg-background"
      }
    >
      {sidebarOpen ? (
        <aside className="flex min-h-0 flex-col border-b bg-muted/20 lg:border-r lg:border-b-0">
          <div className="flex h-11 shrink-0 items-center justify-between gap-2 border-b px-3">
            <span className="font-medium text-sm">目录</span>
            <div className="flex items-center gap-0.5">
              <CompanyDirectoryAddMenu
                onFolderCreate={() => onFolderCreate(activeFolderId)}
                onFolderUpload={() => onFolderUpload(activeFolderId)}
                running={running}
                targetLabel={targetFolderLabel}
              />
              <Button disabled={running} onClick={onExpandAll} size="icon" title="全部展开" variant="ghost">
                <ChevronDown className="size-4" />
              </Button>
              <Button disabled={running} onClick={onCollapseAll} size="icon" title="全部折叠" variant="ghost">
                <ChevronRight className="size-4" />
              </Button>
              <Button onClick={() => onSidebarOpenChange(false)} size="icon" title="收起目录" variant="ghost">
                <PanelLeftClose className="size-4" />
              </Button>
            </div>
          </div>
          <div className="border-b px-2 py-2">
            <div className="relative">
              <Search className="pointer-events-none absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
              <Input
                className="h-9 pl-8"
                onChange={(event) => onTreeSearchChange(event.target.value)}
                placeholder="搜索目录"
                value={treeSearch}
              />
            </div>
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-2">
            {filteredNodes.length > 0 ? (
              filteredNodes.map((node) => (
                <CompanyTreeNode
                  activeNodeId={activeNodeId}
                  depth={0}
                  expandedFolderIds={effectiveExpandedIds}
                  key={node.id}
                  node={node}
                  onDelete={onDelete}
                  onFileSelect={onFileSelect}
                  onFolderCreate={onFolderCreate}
                  onFolderSelect={onFolderSelect}
                  onFolderToggle={onFolderToggle}
                  onFolderUpload={onFolderUpload}
                  running={running}
                />
              ))
            ) : (
              <p className="px-2 py-3 text-muted-foreground text-sm">没有匹配的目录项。</p>
            )}
          </div>
        </aside>
      ) : null}
      <main className="min-w-0 overflow-hidden">
        {file ? (
          <div className="flex h-full min-h-0 flex-col">
            <div className="flex h-11 shrink-0 items-center gap-2 border-b px-3">
              {!sidebarOpen ? (
                <Button
                  className="shrink-0"
                  onClick={() => onSidebarOpenChange(true)}
                  size="icon"
                  title="展开目录"
                  variant="outline"
                >
                  <PanelLeftOpen className="size-4" />
                </Button>
              ) : null}
              <CompanyReadingTrail items={breadcrumb} onSelect={handleBreadcrumbSelect} />
              <Button className="ml-auto shrink-0" onClick={onBackToList} size="sm" type="button" variant="default">
                <ArrowLeft className="size-3.5" />
                返回
              </Button>
            </div>
            <div className="min-h-0 flex-1 overflow-auto p-4" ref={setPreviewScrollEl}>
              {file.conversion_status === "failed" ? (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-destructive text-sm">
                  {file.conversion_summary || "文件转换失败。"}
                </div>
              ) : (
                renderMarkdownPreview(file.markdown_content ?? "")
              )}
            </div>
          </div>
        ) : (
          <div className="flex h-full min-h-0 flex-col">
            <div className="flex h-11 shrink-0 items-center gap-2 border-b px-3">
              {!sidebarOpen ? (
                <Button
                  className="shrink-0"
                  onClick={() => onSidebarOpenChange(true)}
                  size="icon"
                  title="展开目录"
                  variant="outline"
                >
                  <PanelLeftOpen className="size-4" />
                </Button>
              ) : null}
              <CompanyReadingTrail items={breadcrumb} onSelect={handleBreadcrumbSelect} />
              <Button className="ml-auto shrink-0" onClick={onBackToList} size="sm" type="button" variant="default">
                <ArrowLeft className="size-3.5" />
                返回
              </Button>
            </div>
            <CompanyKnowledgeHub
              base={base}
              folder={currentFolder}
              onFileSelect={onFileSelect}
              onFolderSelect={onFolderSelect}
              root={root}
              sidebarOpen={sidebarOpen}
            />
          </div>
        )}
      </main>
    </div>
  );
}

function CompanyTreeNode({
  activeNodeId,
  depth,
  expandedFolderIds,
  node,
  onDelete,
  onFileSelect,
  onFolderCreate,
  onFolderSelect,
  onFolderToggle,
  onFolderUpload,
  running,
}: {
  activeNodeId: string;
  depth: number;
  expandedFolderIds: string[];
  node: ApiCompanyKnowledgeTreeNode;
  onDelete: (node: ApiCompanyKnowledgeTreeNode) => void;
  onFileSelect: (fileId: string) => void;
  onFolderCreate: (folderId: string) => void;
  onFolderSelect: (folder: ApiCompanyKnowledgeFolder) => void;
  onFolderToggle: (folderId: string) => void;
  onFolderUpload: (folderId: string) => void;
  running: boolean;
}) {
  const active = activeNodeId === node.id;
  const isFolder = node.type === "folder";
  const expanded = isFolder && expandedFolderIds.includes(node.id);
  return (
    <div>
      <div
        className={
          active
            ? "group flex h-8 items-center gap-1 rounded-md bg-primary/10 px-1 text-primary"
            : "group flex h-8 items-center gap-1 rounded-md px-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        }
        style={{ paddingLeft: `${depth * 14 + 4}px` }}
      >
        {isFolder ? (
          <button
            aria-label={expanded ? "收起文件夹" : "展开文件夹"}
            className="flex size-5 items-center justify-center rounded-sm hover:bg-background"
            onClick={() => onFolderToggle(node.id)}
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
              onFolderSelect(node);
            } else {
              onFileSelect(node.id);
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
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              aria-label={`打开${node.name}操作菜单`}
              className="size-7 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 data-[state=open]:opacity-100"
              disabled={running}
              size="icon"
              variant="ghost"
            >
              <MoreHorizontal className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="center">
            {isFolder ? (
              <>
                <DropdownMenuItem onSelect={() => onFolderCreate(node.id)}>
                  <Folder className="size-4" />
                  新建文件夹
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => onFolderUpload(node.id)}>
                  <Upload className="size-4" />
                  上传 Markdown
                </DropdownMenuItem>
                <DropdownMenuItem disabled={node.is_root} onSelect={() => onDelete(node)} variant="destructive">
                  <Trash2 className="size-4" />
                  删除本文件夹
                </DropdownMenuItem>
              </>
            ) : (
              <DropdownMenuItem onSelect={() => onDelete(node)} variant="destructive">
                <Trash2 className="size-4" />
                删除文件
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {isFolder && expanded
        ? node.children.map((child) => (
            <CompanyTreeNode
              activeNodeId={activeNodeId}
              depth={depth + 1}
              expandedFolderIds={expandedFolderIds}
              key={child.id}
              node={child}
              onDelete={onDelete}
              onFileSelect={onFileSelect}
              onFolderCreate={onFolderCreate}
              onFolderSelect={onFolderSelect}
              onFolderToggle={onFolderToggle}
              onFolderUpload={onFolderUpload}
              running={running}
            />
          ))
        : null}
    </div>
  );
}

function CompanyKnowledgeDialog({
  form,
  mode,
  onFormChange,
  onOpenChange,
  onSubmit,
  open,
  running,
}: {
  form: typeof emptyCompanyForm;
  mode: "create" | "edit";
  onFormChange: (form: typeof emptyCompanyForm) => void;
  onOpenChange: (open: boolean) => void;
  onSubmit: () => void;
  open: boolean;
  running: boolean;
}) {
  const isEdit = mode === "edit";
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? "编辑知识库" : "创建知识库"}</DialogTitle>
        </DialogHeader>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="company-knowledge-name">知识库名称</FieldLabel>
            <Input
              id="company-knowledge-name"
              onChange={(event) => onFormChange({ ...form, name: event.target.value })}
              placeholder="请输入知识库名称"
              value={form.name}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="company-knowledge-description">描述</FieldLabel>
            <Textarea
              id="company-knowledge-description"
              onChange={(event) => onFormChange({ ...form, description: event.target.value })}
              placeholder="请输入描述"
              value={form.description}
            />
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button disabled={running} onClick={() => onOpenChange(false)} type="button" variant="outline">
            取消
          </Button>
          <Button disabled={running || !form.name.trim()} onClick={onSubmit} type="button">
            {running ? "处理中" : isEdit ? "保存" : "创建"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CompanyFolderDialog({
  name,
  onNameChange,
  onOpenChange,
  onSubmit,
  open,
  running,
}: {
  name: string;
  onNameChange: (value: string) => void;
  onOpenChange: (open: boolean) => void;
  onSubmit: () => void;
  open: boolean;
  running: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建文件夹</DialogTitle>
        </DialogHeader>
        <div className="space-y-1">
          <Label htmlFor="company-folder-name">文件夹名称</Label>
          <Input id="company-folder-name" value={name} onChange={(event) => onNameChange(event.target.value)} />
        </div>
        <DialogFooter>
          <Button disabled={running} onClick={onSubmit}>
            <Folder className="size-4" />
            新建
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CompanyUploadDialog({
  files,
  onFilesChange,
  onOpenChange,
  onSubmit,
  open,
  running,
  targetFolderLabel,
  uploadStates,
}: {
  files: File[];
  onFilesChange: (files: File[]) => void;
  onOpenChange: (open: boolean) => void;
  onSubmit: () => void;
  open: boolean;
  running: boolean;
  targetFolderLabel?: string;
  uploadStates: Record<string, { progress: number; status: "idle" | "uploading" | "completed" | "error" }>;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>上传 Markdown</DialogTitle>
          <DialogDescription>
            {targetFolderLabel
              ? `文件将上传到「${targetFolderLabel}」，仅支持 .md / .markdown 格式。`
              : "文件会上传到当前文件夹，仅支持 .md / .markdown 格式。"}
          </DialogDescription>
        </DialogHeader>
        <FileUpload1
          accept={{
            "text/markdown": [".md", ".markdown"],
          }}
          files={files}
          hint="仅支持 Markdown（.md）文件，最多 10 个"
          maxFiles={10}
          title="上传 Markdown 文档"
          uploadStates={uploadStates}
          onFilesChange={onFilesChange}
        />
        <DialogFooter>
          <Button disabled={running} onClick={() => onOpenChange(false)} type="button" variant="outline">
            取消
          </Button>
          <Button disabled={running || files.length === 0} onClick={onSubmit} type="button">
            {running ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
            {running ? "上传中" : "上传"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DeleteCompanyNodeDialog({
  base,
  onBaseOpenChange,
  onBaseSubmit,
  node,
  onOpenChange,
  onSubmit,
  running,
}: {
  base: ApiCompanyKnowledgeBase | null;
  onBaseOpenChange: (open: boolean) => void;
  onBaseSubmit: () => void;
  node: ApiCompanyKnowledgeTreeNode | null;
  onOpenChange: (open: boolean) => void;
  onSubmit: () => void;
  running: boolean;
}) {
  const isFolder = node?.type === "folder";
  return (
    <Dialog open={Boolean(node ?? base)} onOpenChange={base ? onBaseOpenChange : onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{base ? "删除知识库" : isFolder ? "删除文件夹" : "删除文件"}</DialogTitle>
          <DialogDescription>
            {base
              ? `确认删除知识库“${base.name}”吗？该知识库下的文件夹、文件和对应记录都会从后端删除。`
              : node
                ? isFolder
                  ? `确认删除文件夹“${node.name}”吗？该文件夹下的子文件夹和文件也会一并删除，并从后端移除对应记录。`
                  : `确认删除文件“${node.name}”吗？删除后将从后端移除文件和对应记录。`
                : ""}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            disabled={running}
            onClick={() => (base ? onBaseOpenChange(false) : onOpenChange(false))}
            variant="outline"
          >
            取消
          </Button>
          <Button disabled={running} onClick={base ? onBaseSubmit : onSubmit} variant="destructive">
            <Trash2 className="size-4" />
            删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
