"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import {
  Archive,
  BookOpen,
  Bot,
  Brain,
  Building2,
  ChevronDown,
  ChevronRight,
  Command,
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
import { Badge } from "@/components/ui/badge-2";
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
import { fileConversionTone, StatusBadge } from "@/components/ui/status-badge";
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

const knowledgeScopes = [
  { value: "project", label: "项目知识库", icon: FolderKanban },
  { value: "company", label: "公司知识库", icon: Building2 },
] as const;
const emptyCompanyForm = {
  name: "",
  description: "",
};
const KNOWLEDGE_QUERY_CAPABILITY_ID = "knowledge_query";
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
  sourceRefs?: ApiKnowledgeQueryResult["source_refs"];
  usedRequirementVersions?: string[];
  usedExplorationRuns?: string[];
};

type ProjectKnowledgeStreamEvent =
  | { type: "message_delta"; delta: string }
  | { type: "thinking_delta"; delta: string }
  | { type: "metadata"; result: ApiKnowledgeQueryResult }
  | { type: "done" }
  | { type: "error"; message: string };

function companyTreeContainsNode(node: ApiCompanyKnowledgeTreeNode, nodeId: string): boolean {
  if (node.id === nodeId) {
    return true;
  }
  if (node.type === "file") {
    return false;
  }
  return node.children.some((child) => companyTreeContainsNode(child, nodeId));
}

function companyUploadFileKey(file: File): string {
  return `${file.name}-${file.lastModified}-${file.size}`;
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
  const [folderDialogOpen, setFolderDialogOpen] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [deleteBaseTarget, setDeleteBaseTarget] = useState<ApiCompanyKnowledgeBase | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ApiCompanyKnowledgeTreeNode | null>(null);
  const [companyForm, setCompanyForm] = useState(emptyCompanyForm);
  const [folderName, setFolderName] = useState("");
  const [activeFolderId, setActiveFolderId] = useState("");
  const [expandedFolderIds, setExpandedFolderIds] = useState<string[]>([]);
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
  const knowledgeProjectScopeOptions = [
    { value: "all", label: "全部项目知识库" },
    ...activeProjects.map((project) => ({
      value: project.id,
      label: project.name,
      locked: globalProjectScope === "project" && project.id === activeCurrentProject?.id,
    })),
  ];
  const selectedProjectScope = effectiveKnowledgeScope === "project" ? (effectiveProjectId ?? "") : "all";

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

  const loadProjectConversations = useCallback(async (targetProjectId: string) => {
    const conversationLoadRunId = projectConversationLoadRunIdRef.current + 1;
    projectConversationLoadRunIdRef.current = conversationLoadRunId;
    const isCurrentConversationLoad = () =>
      projectConversationLoadRunIdRef.current === conversationLoadRunId &&
      latestProjectQueryScopeRef.current === `project:${targetProjectId}`;
    setLoading(true);
    setError("");
    try {
      const conversations = await apiRequest<ApiKnowledgeConversation[]>(
        `/projects/${targetProjectId}/knowledge/conversations`,
      );
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
  }, []);

  const openProjectConversation = useCallback(async (targetProjectId: string, conversationId: string) => {
    const conversationOpenRunId = projectConversationOpenRunIdRef.current + 1;
    projectConversationOpenRunIdRef.current = conversationOpenRunId;
    const isCurrentConversationOpen = () =>
      projectConversationOpenRunIdRef.current === conversationOpenRunId &&
      latestProjectQueryScopeRef.current === `project:${targetProjectId}`;
    setLoading(true);
    setError("");
    try {
      const detail = await apiRequest<ApiKnowledgeConversationDetail>(
        `/projects/${targetProjectId}/knowledge/conversations/${conversationId}`,
      );
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
  }, []);

  useEffect(() => {
    if (isCompanyKnowledge || effectiveKnowledgeScope !== "project" || !effectiveProjectId) {
      return;
    }
    void loadProjectConversations(effectiveProjectId);
  }, [effectiveKnowledgeScope, effectiveProjectId, isCompanyKnowledge, loadProjectConversations]);

  function createProjectConversation() {
    setActiveProjectConversationId(null);
    setProjectMessages([]);
    setProjectChatDraft("");
    setError("");
  }

  function changeKnowledgeProjectScope(value: string) {
    if (value === "all") {
      setKnowledgeScope("all");
      setKnowledgeProjectId(null);
      return;
    }
    setKnowledgeScope("project");
    setKnowledgeProjectId(value);
  }

  async function deleteProjectConversation(conversationId: string) {
    if (effectiveKnowledgeScope !== "project" || !projectId) {
      return;
    }
    setRunning(true);
    setError("");
    try {
      await apiRequest<{ deleted: boolean }>(`/projects/${projectId}/knowledge/conversations/${conversationId}`, {
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
    setExpandedFolderIds((ids) => Array.from(new Set([...ids, tree.root.id])));
    setSelectedTreeNodeId(tree.root.id);
    setActiveFolderId(tree.root.id);
    setSelectedCompanyFile(null);
  }, []);

  const refreshCompanyTree = useCallback(
    async (baseId = selectedCompanyBase?.id ?? "") => {
      if (!baseId) {
        return;
      }
      const tree = await apiRequest<ApiCompanyKnowledgeTree>(`/global-knowledge/bases/${baseId}/tree`);
      setSelectedCompanyBase(tree.base);
      setCompanyTree(tree);
      setExpandedFolderIds((ids) => Array.from(new Set([...ids, tree.root.id])));
    },
    [selectedCompanyBase?.id],
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
          include_explorations: true,
          show_thinking: submittedShowThinking,
          conversation_id: submittedKnowledgeScope === "project" ? submittedConversationId : null,
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
            if (isCurrentProjectQueryScope()) {
              setProjectMessages((messages) =>
                messages.map((message) =>
                  message.id === assistantMessageId
                    ? { ...message, thinking: `${message.thinking ?? ""}${event.delta}` }
                    : message,
                ),
              );
            }
          } else if (event.type === "metadata") {
            finalResult = event.result;
            const conversation = event.result.conversation;
            if (isCurrentProjectQueryScope() && submittedKnowledgeScope === "project" && conversation) {
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
          setProjectMessages((messages) => messages.filter((message) => message.id !== assistantMessageId));
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
      await loadCompanyBases();
      await openCompanyBase(base.id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "创建公司知识库失败。");
    } finally {
      setRunning(false);
    }
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
    const unsupported = companyFiles.find((file) => !/\.(pdf|doc|docx|txt|md|markdown)$/i.test(file.name));
    if (unsupported) {
      setError(`仅支持 PDF、Word、TXT、MD 文件：${unsupported.name}`);
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

  function selectCompanyFolder(folder: ApiCompanyKnowledgeFolder) {
    setSelectedTreeNodeId(folder.id);
    setActiveFolderId(folder.id);
    setExpandedFolderIds((ids) => Array.from(new Set([...ids, folder.id])));
  }

  function toggleCompanyFolder(folderId: string) {
    setExpandedFolderIds((ids) => (ids.includes(folderId) ? ids.filter((id) => id !== folderId) : [...ids, folderId]));
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
      breadcrumbs={["项目工作区", "知识库"]}
      description="查看项目知识库与公司知识库的知识块、来源材料和版本记录。"
      projectScope="all"
      title="知识库"
    >
      <Tabs onValueChange={(value) => setActiveScope(value as typeof activeScope)} value={activeScope}>
        <TabsList className="h-auto flex-wrap justify-start">
          {knowledgeScopes.map(({ icon: Icon, label, value }) => (
            <TabsTrigger className="h-8 gap-1.5 px-3" key={value} value={value}>
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
            onCreate={() => {
              setCompanyForm(emptyCompanyForm);
              setCompanyDialogOpen(true);
            }}
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
        <ShellSection>
          {error ? <p className="mb-3 text-destructive text-sm">{error}</p> : null}
          {companyTree ? (
            <CompanyKnowledgeVault
              activeNodeId={selectedTreeNodeId}
              expandedFolderIds={expandedFolderIds}
              file={selectedCompanyFile}
              onDelete={setDeleteTarget}
              onFileSelect={(fileId) => void selectCompanyFile(fileId)}
              onFolderCreate={openFolderCreate}
              onFolderSelect={selectCompanyFolder}
              onFolderToggle={toggleCompanyFolder}
              onFolderUpload={openFolderUpload}
              root={companyTree.root}
              running={running}
            />
          ) : (
            <div className="rounded-lg border p-6 text-muted-foreground text-sm">正在加载知识库目录。</div>
          )}
        </ShellSection>
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
          onConversationOpen={(conversationId) =>
            effectiveKnowledgeScope === "project" &&
            projectId &&
            void openProjectConversation(projectId, conversationId)
          }
          onConversationCreate={createProjectConversation}
          onConversationDelete={(conversationId) => void deleteProjectConversation(conversationId)}
          onModelProviderChange={(modelProviderId) => void updateKnowledgeQueryModelProvider(modelProviderId)}
          onProjectScopeChange={changeKnowledgeProjectScope}
          onShowThinkingChange={setShowProjectThinking}
          onStop={stopProjectKnowledgeQuery}
          onSubmit={(question) => void queryProjectKnowledge(question)}
          projectScopeOptions={knowledgeProjectScopeOptions}
          projectSelected={effectiveKnowledgeScope === "all" || Boolean(projectId)}
          projectConversationEnabled={effectiveKnowledgeScope === "project" && Boolean(projectId)}
          running={running}
          selectedModelProviderId={selectedKnowledgeModelProviderId}
          selectedProjectScope={selectedProjectScope}
          showThinking={showProjectThinking}
          value={projectChatDraft}
          onValueChange={setProjectChatDraft}
        />
      ) : null}
      <CompanyKnowledgeDialog
        form={companyForm}
        onFormChange={setCompanyForm}
        onOpenChange={setCompanyDialogOpen}
        onSubmit={() => void createCompanyBase()}
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
    sourceRefs: message.source_refs,
    usedRequirementVersions: message.used_requirement_versions,
    usedExplorationRuns: message.used_exploration_runs,
  };
}

function mergeAssistantStreamResult(message: ProjectChatMessage, result: ApiKnowledgeQueryResult): ProjectChatMessage {
  const assistant = result.messages.find((item) => item.role === "assistant");
  return {
    ...message,
    body: message.body || assistant?.content || result.answer,
    sourceRefs: result.source_refs,
    usedRequirementVersions: result.used_requirement_versions,
    usedExplorationRuns: result.used_exploration_runs,
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
  onProjectScopeChange,
  onShowThinkingChange,
  onStop,
  onSubmit,
  projectConversationEnabled,
  projectScopeOptions,
  projectSelected,
  running,
  selectedModelProviderId,
  selectedProjectScope,
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
  onProjectScopeChange: (value: string) => void;
  onShowThinkingChange: (value: boolean) => void;
  onStop: () => void;
  onSubmit: (instruction: string) => void;
  projectConversationEnabled: boolean;
  projectScopeOptions: Array<{ value: string; label: string; locked?: boolean }>;
  projectSelected: boolean;
  running: boolean;
  selectedModelProviderId: string;
  selectedProjectScope: string;
  showThinking: boolean;
  value: string;
  onValueChange: (value: string) => void;
}) {
  const hasConversation = messages.length > 0 || running;
  const [historyOpen, setHistoryOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const latestMessage = messages[messages.length - 1];
  const latestMessageSourceCount = latestMessage?.sourceRefs?.length ?? 0;
  const projectHistoryOpen = historyOpen;
  const latestMessageScrollKey = [
    messages.length,
    latestMessage?.id,
    latestMessage?.body,
    latestMessageSourceCount,
    error,
    projectHistoryOpen,
    running,
  ].join("|");
  const projectScopeDisabled = projectScopeOptions.some(
    (option) => option.value === selectedProjectScope && option.locked,
  );

  useLayoutEffect(() => {
    if (!hasConversation || latestMessageScrollKey.length === 0) {
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ block: "end" });
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [hasConversation, latestMessageScrollKey]);

  useEffect(() => {
    if (!projectSelected) {
      setHistoryOpen(false);
    }
  }, [projectSelected]);

  return (
    <ShellSection className="h-[clamp(30rem,calc(100dvh-14rem),42rem)] p-0">
      <div
        className={
          projectHistoryOpen
            ? "grid h-full overflow-hidden rounded-lg border bg-background lg:grid-cols-[18rem_minmax(0,1fr)]"
            : "relative grid h-full overflow-hidden rounded-lg border bg-background"
        }
      >
        {!projectHistoryOpen ? (
          <KnowledgeChatTopControls
            onConversationCreate={onConversationCreate}
            onHistoryOpen={() => {
              if (!projectSelected || running) {
                return;
              }
              setHistoryOpen(true);
            }}
            projectConversationEnabled={projectConversationEnabled}
            projectSelected={projectSelected}
            running={running}
          />
        ) : null}
        {projectHistoryOpen ? (
          <aside className="flex min-h-0 flex-col border-b bg-muted/20 lg:border-r lg:border-b-0">
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
            <div className="min-h-0 flex-1 space-y-1 overflow-auto p-2">
              {!projectConversationEnabled ? (
                <div className="px-2 py-3 text-muted-foreground text-sm">
                  全部项目知识库暂不保存历史对话，可切换到具体项目查看项目对话历史。
                </div>
              ) : loading ? (
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
          <div className="relative flex min-h-0 flex-col items-center justify-center overflow-hidden px-4 py-6 min-[900px]:py-10">
            <div className="relative mb-5 text-center min-[900px]:mb-8">
              <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-lg border bg-primary text-primary-foreground shadow-sm min-[900px]:mb-6 min-[900px]:size-20">
                <Command className="size-8 min-[900px]:size-10" />
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
              loading={running}
              modelLoading={modelLoading}
              modelProviders={modelProviders}
              modelSaving={modelSaving}
              onModelProviderChange={onModelProviderChange}
              onProjectScopeChange={onProjectScopeChange}
              onShowThinkingChange={onShowThinkingChange}
              onStop={onStop}
              onSubmit={onSubmit}
              onValueChange={onValueChange}
              projectScopeDisabled={projectScopeDisabled}
              projectScopeOptions={projectScopeOptions}
              selectedModelProviderId={selectedModelProviderId}
              selectedProjectScope={selectedProjectScope}
              showThinking={showThinking}
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
          <div className="flex min-h-0 min-w-0 flex-col overflow-hidden">
            <div
              className={
                projectHistoryOpen
                  ? "min-h-0 flex-1 space-y-4 overflow-auto bg-muted/20 p-4"
                  : "min-h-0 flex-1 space-y-4 overflow-auto bg-muted/20 px-4 pt-16 pb-4"
              }
            >
              {messages.map((message) => (
                <ChatMessage
                  body={message.body}
                  icon={message.role === "user" ? User : Bot}
                  key={message.id}
                  loading={
                    running &&
                    message.role === "assistant" &&
                    message.body.length === 0 &&
                    (message.thinking?.length ?? 0) === 0
                  }
                  thinking={message.thinking}
                  title={message.role === "user" ? "你" : "项目知识库 AI"}
                  tone={message.role === "user" ? "user" : "assistant"}
                >
                  {message.sourceRefs?.length ? (
                    <div className="mt-3 space-y-2 border-t pt-3">
                      <div className="font-medium text-muted-foreground text-xs">来源引用</div>
                      {message.sourceRefs.slice(0, 6).map((ref) => (
                        <div
                          className="rounded-md border bg-muted/30 p-2 text-xs"
                          key={`${ref.source_type}-${ref.source_id}-${ref.location}-${ref.excerpt}`}
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="outline">{ref.source_type === "requirement" ? "需求" : "探索"}</Badge>
                            {ref.project_name ? <Badge variant="secondary">{ref.project_name}</Badge> : null}
                            <span className="font-medium">{ref.source_title}</span>
                          </div>
                          {ref.location ? <div className="mt-1 text-muted-foreground">{ref.location}</div> : null}
                          {ref.excerpt ? (
                            <p className="mt-1 line-clamp-2 text-muted-foreground">{ref.excerpt}</p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </ChatMessage>
              ))}
              {error ? <ChatMessage body={error} icon={TriangleAlert} title="查询失败" tone="warning" /> : null}
              <div ref={messagesEndRef} />
            </div>
            <div className="bg-muted/20 p-4">
              <KnowledgeChatInput
                compact
                disabled={!projectSelected}
                loading={running}
                modelLoading={modelLoading}
                modelProviders={modelProviders}
                modelSaving={modelSaving}
                onModelProviderChange={onModelProviderChange}
                onProjectScopeChange={onProjectScopeChange}
                onShowThinkingChange={onShowThinkingChange}
                onStop={onStop}
                onSubmit={onSubmit}
                onValueChange={onValueChange}
                projectScopeDisabled={projectScopeDisabled}
                projectScopeOptions={projectScopeOptions}
                selectedModelProviderId={selectedModelProviderId}
                selectedProjectScope={selectedProjectScope}
                showThinking={showThinking}
                value={value}
              />
            </div>
          </div>
        )}
      </div>
    </ShellSection>
  );
}

function KnowledgeChatTopControls({
  onConversationCreate,
  onHistoryOpen,
  projectConversationEnabled,
  projectSelected,
  running,
}: {
  onConversationCreate: () => void;
  onHistoryOpen: () => void;
  projectConversationEnabled: boolean;
  projectSelected: boolean;
  running: boolean;
}) {
  const controlDisabledReason = !projectSelected ? "请选择知识库后使用对话" : "查询中";
  const historyTitle =
    projectSelected && !running
      ? projectConversationEnabled
        ? "展开对话历史"
        : "查看全部项目对话状态"
      : controlDisabledReason;
  const createTitle = projectSelected && !running ? "新建对话" : controlDisabledReason;

  return (
    <div className="pointer-events-none absolute top-4 left-4 z-50 flex items-center gap-3">
      <div className="pointer-events-auto flex h-10 items-center gap-1 rounded-lg border bg-background/95 px-2 shadow-sm backdrop-blur">
        <button
          aria-label="展开对话历史"
          className="inline-flex size-8 items-center justify-center rounded-md text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-45"
          disabled={!projectSelected || running}
          onClick={onHistoryOpen}
          title={historyTitle}
          type="button"
        >
          <PanelLeftOpen className="size-4" />
        </button>
        <button
          aria-label="新建对话"
          className="inline-flex size-8 items-center justify-center rounded-md text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-45"
          disabled={!projectSelected || running}
          onClick={onConversationCreate}
          title={createTitle}
          type="button"
        >
          <Plus className="size-4" />
        </button>
      </div>
    </div>
  );
}

function ChatMessage({
  body,
  children,
  icon: Icon,
  loading = false,
  thinking = "",
  title,
  tone,
}: {
  body: string;
  children?: React.ReactNode;
  icon: React.ComponentType<{ className?: string }>;
  loading?: boolean;
  thinking?: string;
  title: string;
  tone: "assistant" | "user" | "warning";
}) {
  const isUser = tone === "user";
  const showThinking = tone === "assistant" && thinking.trim().length > 0;
  return (
    <div className={isUser ? "flex justify-end" : "flex justify-start"}>
      <div className={isUser ? "max-w-[82%]" : "max-w-[88%]"}>
        <div className={isUser ? "flex flex-row-reverse items-center gap-2" : "flex items-center gap-2"}>
          <div className="flex size-7 items-center justify-center rounded-md border bg-background">
            <Icon className={loading ? "size-4 animate-spin" : "size-4"} />
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
            <details className="mb-3 rounded-md border bg-muted/30 p-2 text-muted-foreground text-xs" open={loading}>
              <summary className="flex cursor-pointer list-none items-center gap-1.5 font-medium text-foreground">
                <Brain className="size-3.5" />
                深度思考
              </summary>
              <p className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap leading-5">{thinking.trim()}</p>
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

function CompanyKnowledgeVault({
  activeNodeId,
  expandedFolderIds,
  file,
  onDelete,
  onFileSelect,
  onFolderCreate,
  onFolderSelect,
  onFolderToggle,
  onFolderUpload,
  root,
  running,
}: {
  activeNodeId: string;
  expandedFolderIds: string[];
  file: ApiCompanyKnowledgeFile | null;
  onDelete: (node: ApiCompanyKnowledgeTreeNode) => void;
  onFileSelect: (fileId: string) => void;
  onFolderCreate: (folderId: string) => void;
  onFolderSelect: (folder: ApiCompanyKnowledgeFolder) => void;
  onFolderToggle: (folderId: string) => void;
  onFolderUpload: (folderId: string) => void;
  root: ApiCompanyKnowledgeFolder;
  running: boolean;
}) {
  return (
    <div className="grid min-h-[32rem] overflow-hidden rounded-lg border bg-background lg:grid-cols-[18rem_minmax(0,1fr)]">
      <aside className="min-h-0 border-b bg-muted/20 lg:border-r lg:border-b-0">
        <div className="border-b px-3 py-2 font-medium text-sm">目录</div>
        <div className="max-h-[34rem] overflow-auto p-2">
          <CompanyTreeNode
            activeNodeId={activeNodeId}
            depth={0}
            expandedFolderIds={expandedFolderIds}
            node={root}
            onDelete={onDelete}
            onFileSelect={onFileSelect}
            onFolderCreate={onFolderCreate}
            onFolderSelect={onFolderSelect}
            onFolderToggle={onFolderToggle}
            onFolderUpload={onFolderUpload}
            running={running}
          />
        </div>
      </aside>
      <main className="min-w-0 overflow-hidden">
        {file ? (
          <div className="flex h-full min-h-0 flex-col">
            <div className="flex items-center gap-2 border-b px-4 py-3">
              <FileText className="size-4 text-muted-foreground" />
              <div className="min-w-0 flex-1 truncate font-medium text-sm">{file.display_name}</div>
              <StatusBadge tone={fileConversionTone(file.conversion_status)}>
                {file.conversion_status === "success" ? "可用" : file.conversion_status}
              </StatusBadge>
            </div>
            <div className="min-h-0 flex-1 overflow-auto p-4">
              {file.conversion_status === "failed" ? (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-destructive text-sm">
                  {file.conversion_summary || "文件转换失败。"}
                </div>
              ) : (
                <MarkdownPreview content={file.markdown_content ?? ""} emptyText="暂无 Markdown 内容。" />
              )}
            </div>
          </div>
        ) : (
          <div className="flex h-full min-h-[32rem] items-center justify-center px-4 text-center text-muted-foreground text-sm">
            从左侧选择文件，或在文件夹菜单中上传文件。
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
                  上传文件
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
  onFormChange,
  onOpenChange,
  onSubmit,
  open,
  running,
}: {
  form: typeof emptyCompanyForm;
  onFormChange: (form: typeof emptyCompanyForm) => void;
  onOpenChange: (open: boolean) => void;
  onSubmit: () => void;
  open: boolean;
  running: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>创建知识库</DialogTitle>
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
            {running ? "处理中" : "创建"}
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
  uploadStates,
}: {
  files: File[];
  onFilesChange: (files: File[]) => void;
  onOpenChange: (open: boolean) => void;
  onSubmit: () => void;
  open: boolean;
  running: boolean;
  uploadStates: Record<string, { progress: number; status: "idle" | "uploading" | "completed" | "error" }>;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>上传文件</DialogTitle>
          <DialogDescription>文件会上传到当前文件夹，支持 PDF、Word（doc/docx）、TXT、MD 格式。</DialogDescription>
        </DialogHeader>
        <FileUpload1
          accept={{
            "application/pdf": [".pdf"],
            "application/msword": [".doc"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
            "text/markdown": [".md", ".markdown"],
            "text/plain": [".txt"],
          }}
          files={files}
          hint="仅支持 PDF、Word（doc/docx）、TXT、MD 文件"
          maxFiles={10}
          title="上传知识库文件"
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
