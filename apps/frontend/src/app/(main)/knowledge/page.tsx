"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Archive,
  BookOpen,
  Bot,
  Building2,
  Command,
  Eye,
  FilePlus2,
  FolderKanban,
  Lightbulb,
  MapIcon,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  TriangleAlert,
  Upload,
  User,
} from "lucide-react";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
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
import { Input } from "@/components/ui/input";
import { KnowledgeChatInput } from "@/components/ui/knowledge-chat-input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import {
  type ApiGlobalKnowledgeDetail,
  type ApiGlobalKnowledgeDocument,
  type ApiGlobalKnowledgeList,
  type ApiKnowledgeConversation,
  type ApiKnowledgeConversationDetail,
  type ApiKnowledgeConversationMessage,
  type ApiKnowledgeQueryResult,
  apiFormRequest,
  apiRequest,
  formatDateTime,
} from "@/lib/api-client";
import { useProjectContextStore } from "@/stores/project-context-store";

const knowledgeScopes = [
  { value: "project", label: "项目知识库", icon: FolderKanban },
  { value: "company", label: "公司知识库", icon: Building2 },
] as const;
const knowledgeTypes = [
  { value: "platform_prd", label: "平台 PRD" },
  { value: "test_standard", label: "测试规范" },
  { value: "case_template", label: "用例模板" },
  { value: "review_rule", label: "评审规则" },
  { value: "automation_standard", label: "自动化规范" },
  { value: "term", label: "通用术语" },
  { value: "workflow", label: "通用流程" },
  { value: "other", label: "其他" },
] as const;
const emptyCompanyForm = {
  name: "",
  knowledge_type: "test_standard",
  version: "v1",
  scope: "全部项目",
  source_note: "",
  description: "",
  change_summary: "",
};
const emptyProjectBuildForm = {
  includeRequirements: true,
  includeExplorations: true,
};
const projectKnowledgeQuickPrompts = [
  { icon: Search, label: "查需求", prompt: "帮我查询当前项目最终需求文档中的核心业务规则。" },
  { icon: MapIcon, label: "看探索", prompt: "帮我总结当前项目探索记录覆盖了哪些页面和模块。" },
  { icon: ShieldCheck, label: "找风险", prompt: "结合最终需求和探索记录，列出测试设计需要关注的风险点。" },
  { icon: Lightbulb, label: "补缺口", prompt: "帮我找出需求文档和探索记录之间还缺少哪些确认信息。" },
] as const;

type ProjectChatMessage = {
  id: string;
  role: "assistant" | "user";
  body: string;
  sourceRefs?: ApiKnowledgeQueryResult["source_refs"];
  usedRequirementVersions?: string[];
  usedExplorationRuns?: string[];
};

export default function Page() {
  const [activeScope, setActiveScope] = useState<(typeof knowledgeScopes)[number]["value"]>("project");
  const [searchText, setSearchText] = useState("");
  const { currentProjectId, hydrate, scope } = useProjectContextStore();
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [companyDocs, setCompanyDocs] = useState<ApiGlobalKnowledgeDocument[]>([]);
  const [selectedCompanyDoc, setSelectedCompanyDoc] = useState<ApiGlobalKnowledgeDetail | null>(null);
  const [companyDialogOpen, setCompanyDialogOpen] = useState(false);
  const [versionDialogOpen, setVersionDialogOpen] = useState(false);
  const [companyForm, setCompanyForm] = useState(emptyCompanyForm);
  const [projectBuildForm, setProjectBuildForm] = useState(emptyProjectBuildForm);
  const [projectChatDraft, setProjectChatDraft] = useState("");
  const [projectMessages, setProjectMessages] = useState<ProjectChatMessage[]>([]);
  const [projectConversations, setProjectConversations] = useState<ApiKnowledgeConversation[]>([]);
  const [activeProjectConversationId, setActiveProjectConversationId] = useState<string | null>(null);
  const [companyFiles, setCompanyFiles] = useState<FileList | null>(null);
  const {
    allSelected: allCompanySelected,
    deleteSelected: deleteCompanySelected,
    partiallySelected: partiallyCompanySelected,
    rows: companyRows,
    selectedCount: selectedCompanyCount,
    selectedIds: selectedCompanyIds,
    toggleAll: toggleAllCompany,
    toggleOne: toggleOneCompany,
  } = useLocalTableSelection(companyDocs);
  const filteredCompanyRows = companyRows.filter((item) =>
    [item.name, item.knowledge_type_label, item.version, item.scope, item.description, item.status_label].some(
      (value) => value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );
  const isCompanyKnowledge = activeScope === "company";
  const projectId = scope === "project" ? currentProjectId : null;
  const projectResetKey = `${scope}:${currentProjectId ?? ""}`;

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    void projectResetKey;
    setProjectMessages([]);
    setProjectChatDraft("");
    setProjectConversations([]);
    setActiveProjectConversationId(null);
    setError("");
  }, [projectResetKey]);

  const loadProjectConversations = useCallback(async (targetProjectId: string) => {
    setLoading(true);
    setError("");
    try {
      const conversations = await apiRequest<ApiKnowledgeConversation[]>(
        `/projects/${targetProjectId}/knowledge/conversations`,
      );
      setProjectConversations(conversations);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "加载项目知识库对话失败。");
      setProjectConversations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const openProjectConversation = useCallback(async (targetProjectId: string, conversationId: string) => {
    setLoading(true);
    setError("");
    try {
      const detail = await apiRequest<ApiKnowledgeConversationDetail>(
        `/projects/${targetProjectId}/knowledge/conversations/${conversationId}`,
      );
      setActiveProjectConversationId(detail.conversation.id);
      setProjectMessages(detail.messages.map(projectMessageFromApi));
      setProjectChatDraft("");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "打开项目知识库对话失败。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isCompanyKnowledge || !projectId) {
      return;
    }
    void loadProjectConversations(projectId);
  }, [isCompanyKnowledge, loadProjectConversations, projectId]);

  function createProjectConversation() {
    setActiveProjectConversationId(null);
    setProjectMessages([]);
    setProjectChatDraft("");
    setError("");
  }

  async function deleteProjectConversation(conversationId: string) {
    if (!projectId) {
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

  const openCompanyDoc = useCallback(async (documentId: string) => {
    const detail = await apiRequest<ApiGlobalKnowledgeDetail>(`/global-knowledge/documents/${documentId}`);
    setSelectedCompanyDoc(detail);
  }, []);

  const loadCompanyDocs = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await apiRequest<ApiGlobalKnowledgeList>("/global-knowledge/documents");
      setCompanyDocs(result.items);
      if (result.items[0]) {
        await openCompanyDoc(result.items[0].id);
      } else {
        setSelectedCompanyDoc(null);
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "加载公司知识库失败。");
      setCompanyDocs([]);
      setSelectedCompanyDoc(null);
    } finally {
      setLoading(false);
    }
  }, [openCompanyDoc]);

  useEffect(() => {
    if (isCompanyKnowledge) {
      void loadCompanyDocs();
    }
  }, [isCompanyKnowledge, loadCompanyDocs]);

  async function queryProjectKnowledge(question: string) {
    if (!projectId) {
      setError("请先在顶部选择具体项目。");
      return;
    }
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      return;
    }
    if (!projectBuildForm.includeRequirements && !projectBuildForm.includeExplorations) {
      setError("请至少选择需求文件或探索文件作为知识库来源。");
      return;
    }
    const userMessage: ProjectChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      body: trimmedQuestion,
    };
    setProjectMessages((messages) => [...messages, userMessage]);
    setRunning(true);
    setError("");
    notifyAiTaskStarted();
    try {
      const result = await apiRequest<ApiKnowledgeQueryResult>(`/projects/${projectId}/knowledge/query`, {
        method: "POST",
        body: JSON.stringify({
          question: trimmedQuestion,
          include_requirements: projectBuildForm.includeRequirements,
          include_explorations: projectBuildForm.includeExplorations,
          conversation_id: activeProjectConversationId,
        }),
      });
      setActiveProjectConversationId(result.conversation.id);
      setProjectConversations((items) => upsertConversation(items, result.conversation));
      setProjectMessages((messages) => [
        ...messages,
        ...result.messages.filter((message) => message.role === "assistant").map(projectMessageFromApi),
      ]);
      setProjectChatDraft("");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "查询项目知识库失败。");
    } finally {
      setRunning(false);
    }
  }

  async function uploadCompanyKnowledge() {
    if (!companyFiles?.length) {
      setError("请先选择公司知识文件。");
      return;
    }
    setRunning(true);
    setError("");
    try {
      const formData = new FormData();
      formData.set("name", companyForm.name);
      formData.set("knowledge_type", companyForm.knowledge_type);
      formData.set("version", companyForm.version);
      formData.set("scope", companyForm.scope);
      formData.set("source_note", companyForm.source_note);
      formData.set("description", companyForm.description);
      Array.from(companyFiles).forEach((file) => {
        formData.append("files", file);
      });
      const detail = await apiFormRequest<ApiGlobalKnowledgeDetail>("/global-knowledge/documents", formData, {
        method: "POST",
      });
      setSelectedCompanyDoc(detail);
      setCompanyDialogOpen(false);
      setCompanyForm(emptyCompanyForm);
      setCompanyFiles(null);
      await loadCompanyDocs();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "上传公司知识失败。");
    } finally {
      setRunning(false);
    }
  }

  async function createCompanyVersion() {
    if (!selectedCompanyDoc || !companyFiles?.length) {
      setError("请先选择要上传的新版本文件。");
      return;
    }
    setRunning(true);
    setError("");
    try {
      const formData = new FormData();
      formData.set("version", companyForm.version);
      formData.set("source_note", companyForm.source_note);
      formData.set("change_summary", companyForm.change_summary);
      Array.from(companyFiles).forEach((file) => {
        formData.append("files", file);
      });
      const detail = await apiFormRequest<ApiGlobalKnowledgeDetail>(
        `/global-knowledge/documents/${selectedCompanyDoc.document.id}/versions`,
        formData,
        { method: "POST" },
      );
      setSelectedCompanyDoc(detail);
      setVersionDialogOpen(false);
      setCompanyForm(emptyCompanyForm);
      setCompanyFiles(null);
      await loadCompanyDocs();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "新增公司知识版本失败。");
    } finally {
      setRunning(false);
    }
  }

  async function archiveCompanyDoc(documentId: string) {
    setRunning(true);
    setError("");
    try {
      const detail = await apiRequest<ApiGlobalKnowledgeDetail>(`/global-knowledge/documents/${documentId}/archive`, {
        method: "POST",
      });
      setSelectedCompanyDoc(detail);
      await loadCompanyDocs();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "废弃公司知识失败。");
    } finally {
      setRunning(false);
    }
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
      {isCompanyKnowledge ? (
        <ShellSection>
          <ListToolbar
            actions={
              <Button disabled={loading || running} onClick={() => void loadCompanyDocs()} variant="outline">
                <RefreshCw className="size-4" />
                刷新
              </Button>
            }
            createDisabled={running}
            createLabel={running ? "处理中" : "上传公司知识"}
            description="公司知识库用于维护跨项目复用的测试规范、用例模板、评审规则、自动化规范、术语和流程。"
            onBatchDelete={deleteCompanySelected}
            onCreate={() => {
              setCompanyForm(emptyCompanyForm);
              setCompanyFiles(null);
              setCompanyDialogOpen(true);
            }}
            onSearch={setSearchText}
            placeholder="搜索公司知识、类型或版本"
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
                  <TableHead>知识名称</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>知识类型</TableHead>
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
                        onClick={() => void openCompanyDoc(item.id)}
                        type="button"
                      >
                        {item.name}
                      </button>
                      <div className="text-muted-foreground text-xs">
                        {item.version || "未生成版本"} · {item.scope}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          item.status === "available"
                            ? "secondary"
                            : item.status === "conversion_failed"
                              ? "destructive"
                              : "outline"
                        }
                      >
                        {item.status_label}
                      </Badge>
                    </TableCell>
                    <TableCell>{item.knowledge_type_label}</TableCell>
                    <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                    <TableCell>
                      <RowActions
                        actions={[
                          { label: "查看", icon: Eye, onSelect: () => void openCompanyDoc(item.id) },
                          {
                            label: "新增版本",
                            icon: FilePlus2,
                            disabled: item.status === "archived" || running,
                            onSelect: () => {
                              void openCompanyDoc(item.id);
                              setCompanyForm({ ...emptyCompanyForm, version: "" });
                              setCompanyFiles(null);
                              setVersionDialogOpen(true);
                            },
                          },
                          {
                            label: "废弃",
                            icon: Archive,
                            disabled: item.status === "archived" || running,
                            destructive: true,
                            onSelect: () => void archiveCompanyDoc(item.id),
                          },
                        ]}
                        label="打开操作菜单"
                      />
                    </TableCell>
                  </TableRow>
                ))}
                {filteredCompanyRows.length === 0 ? (
                  <TableRow>
                    <TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
                      {loading ? "正在加载公司知识库。" : "暂无公司知识。管理员可上传测试规范、模板、术语或流程。"}
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>
          {error ? <p className="mt-3 text-destructive text-sm">{error}</p> : null}
        </ShellSection>
      ) : (
        <ProjectKnowledgeWorkspace
          activeConversationId={activeProjectConversationId}
          conversations={projectConversations}
          error={error}
          form={projectBuildForm}
          loading={loading}
          messages={projectMessages}
          onConversationOpen={(conversationId) => projectId && void openProjectConversation(projectId, conversationId)}
          onConversationCreate={createProjectConversation}
          onConversationDelete={(conversationId) => void deleteProjectConversation(conversationId)}
          onFormChange={setProjectBuildForm}
          onSubmit={(question) => void queryProjectKnowledge(question)}
          projectSelected={Boolean(projectId)}
          running={running}
          value={projectChatDraft}
          onValueChange={setProjectChatDraft}
        />
      )}
      {isCompanyKnowledge && selectedCompanyDoc ? (
        <ShellSection className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <BookOpen className="size-4 text-muted-foreground" />
              <h2 className="font-medium text-sm">{selectedCompanyDoc.document.name}</h2>
              <Badge variant="outline">{selectedCompanyDoc.document.version || "无版本"}</Badge>
              <Badge variant={selectedCompanyDoc.document.status === "available" ? "secondary" : "outline"}>
                {selectedCompanyDoc.document.status_label}
              </Badge>
            </div>
            <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/30 p-4 text-sm">
              {selectedCompanyDoc.current_version?.markdown_content || "暂无 Markdown 预览。"}
            </pre>
          </div>
          <aside className="space-y-3">
            <div>
              <h3 className="font-medium text-sm">基础信息</h3>
              <div className="mt-2 space-y-1 text-muted-foreground text-xs">
                <p>类型：{selectedCompanyDoc.document.knowledge_type_label}</p>
                <p>范围：{selectedCompanyDoc.document.scope}</p>
                <p>文件：{selectedCompanyDoc.files.length} 个</p>
                <p>来源：{selectedCompanyDoc.document.source_note || "-"}</p>
              </div>
            </div>
            <div>
              <h3 className="font-medium text-sm">文件列表</h3>
              <div className="mt-2 space-y-2">
                {selectedCompanyDoc.files.map((file) => (
                  <div className="rounded-md border p-2 text-xs" key={file.id}>
                    <div className="font-medium">{file.original_filename}</div>
                    <div className="text-muted-foreground">
                      {file.file_type || "unknown"} · {file.file_size} bytes
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h3 className="font-medium text-sm">版本记录</h3>
              <div className="mt-2 space-y-2">
                {selectedCompanyDoc.versions.map((version) => (
                  <div className="rounded-md border p-2 text-xs" key={version.id}>
                    <div className="font-medium">{version.version_no}</div>
                    <div className="text-muted-foreground">{version.conversion_summary}</div>
                  </div>
                ))}
              </div>
            </div>
          </aside>
        </ShellSection>
      ) : null}
      <CompanyKnowledgeDialog
        files={companyFiles}
        form={companyForm}
        mode="create"
        onFilesChange={setCompanyFiles}
        onFormChange={setCompanyForm}
        onOpenChange={setCompanyDialogOpen}
        onSubmit={() => void uploadCompanyKnowledge()}
        open={companyDialogOpen}
        running={running}
      />
      <CompanyKnowledgeDialog
        files={companyFiles}
        form={companyForm}
        mode="version"
        onFilesChange={setCompanyFiles}
        onFormChange={setCompanyForm}
        onOpenChange={setVersionDialogOpen}
        onSubmit={() => void createCompanyVersion()}
        open={versionDialogOpen}
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
  form,
  loading,
  messages,
  onConversationCreate,
  onConversationDelete,
  onConversationOpen,
  onFormChange,
  onSubmit,
  projectSelected,
  running,
  value,
  onValueChange,
}: {
  activeConversationId: string | null;
  conversations: ApiKnowledgeConversation[];
  error: string;
  form: typeof emptyProjectBuildForm;
  loading: boolean;
  messages: ProjectChatMessage[];
  onConversationCreate: () => void;
  onConversationDelete: (conversationId: string) => void;
  onConversationOpen: (conversationId: string) => void;
  onFormChange: (form: typeof emptyProjectBuildForm) => void;
  onSubmit: (instruction: string) => void;
  projectSelected: boolean;
  running: boolean;
  value: string;
  onValueChange: (value: string) => void;
}) {
  const hasConversation = messages.length > 0 || running;
  const [historyOpen, setHistoryOpen] = useState(true);

  return (
    <ShellSection className="min-h-[42rem] p-0">
      <div
        className={
          historyOpen
            ? "grid min-h-[42rem] overflow-hidden rounded-lg border bg-background lg:grid-cols-[17rem_minmax(0,1fr)]"
            : "grid min-h-[42rem] overflow-hidden rounded-lg border bg-background lg:grid-cols-[3.5rem_minmax(0,1fr)]"
        }
      >
        <aside
          className={
            historyOpen
              ? "flex min-h-0 flex-col border-b bg-muted/20 lg:border-r lg:border-b-0"
              : "flex min-h-0 flex-col items-center border-b bg-muted/20 p-2 lg:border-r lg:border-b-0"
          }
        >
          {!historyOpen ? (
            <>
              <Button onClick={() => setHistoryOpen(true)} size="icon" title="展开对话历史" variant="ghost">
                <PanelLeftOpen className="size-4" />
              </Button>
              <Button
                className="mt-2"
                disabled={!projectSelected || running}
                onClick={onConversationCreate}
                size="icon"
                title="新建对话"
                variant="ghost"
              >
                <Plus className="size-4" />
              </Button>
            </>
          ) : null}
          {historyOpen ? (
            <>
              <div className="flex items-center justify-between gap-2 border-b p-3">
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
                {loading ? <div className="px-2 py-3 text-muted-foreground text-sm">正在加载对话。</div> : null}
                {!loading && conversations.length === 0 ? (
                  <div className="px-2 py-3 text-muted-foreground text-sm">暂无历史对话。</div>
                ) : null}
                {conversations.map((conversation) => {
                  const active = conversation.id === activeConversationId;
                  return (
                    <div className="group flex items-center gap-1" key={conversation.id}>
                      <button
                        className={
                          active
                            ? "min-w-0 flex-1 rounded-md bg-primary/10 px-2.5 py-2 text-left text-primary text-sm"
                            : "min-w-0 flex-1 rounded-md px-2.5 py-2 text-left text-muted-foreground text-sm transition-colors hover:bg-muted hover:text-foreground"
                        }
                        disabled={running}
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
                        disabled={running}
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
            </>
          ) : null}
        </aside>

        {!hasConversation ? (
          <div className="flex min-h-[42rem] flex-col items-center justify-center overflow-hidden bg-background px-4 py-10">
            <div className="mb-8 text-center">
              <div className="mx-auto mb-6 flex size-20 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-sm">
                <Command className="size-10" />
              </div>
              <h2 className="font-serif text-3xl text-foreground tracking-tight sm:text-4xl">项目知识库</h2>
              <p className="mt-3 text-muted-foreground text-sm">查询最终需求文档和探索记录，答案会附带来源依据。</p>
            </div>
            <KnowledgeChatInput
              disabled={!projectSelected}
              includeExplorations={form.includeExplorations}
              includeRequirements={form.includeRequirements}
              loading={running}
              onSourceChange={(next) => onFormChange({ ...form, ...next })}
              onSubmit={onSubmit}
              onValueChange={onValueChange}
              value={value}
            />
            <div className="mt-4 flex max-w-2xl flex-wrap justify-center gap-2 px-4">
              {projectKnowledgeQuickPrompts.map(({ icon: Icon, label, prompt }) => (
                <button
                  className="inline-flex items-center gap-1.5 rounded-full border bg-transparent px-3 py-1.5 text-muted-foreground text-sm transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={!projectSelected || running}
                  key={label}
                  onClick={() => onSubmit(prompt)}
                  type="button"
                >
                  <Icon className="size-4" />
                  {label}
                </button>
              ))}
            </div>
            {error ? (
              <div className="mt-4 max-w-2xl rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-destructive text-sm">
                {error}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="flex min-h-[42rem] min-w-0 flex-col overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b p-3">
              <div className="flex items-center gap-2">
                <Bot className="size-4 text-primary" />
                <h2 className="font-medium text-sm">项目知识库 AI</h2>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-muted-foreground text-xs">
                <Badge variant={form.includeRequirements ? "secondary" : "outline"}>最终需求文档</Badge>
                <Badge variant={form.includeExplorations ? "secondary" : "outline"}>探索记录</Badge>
              </div>
            </div>
            <div className="min-h-0 flex-1 space-y-4 overflow-auto bg-muted/20 p-4">
              {messages.map((message) => (
                <ChatMessage
                  body={message.body}
                  icon={message.role === "user" ? User : Bot}
                  key={message.id}
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
              {running ? (
                <ChatMessage
                  body="正在读取最终需求文档和探索记录，并执行 agentic search。"
                  icon={RefreshCw}
                  loading
                  title="项目知识库 AI"
                  tone="assistant"
                />
              ) : null}
              {error ? <ChatMessage body={error} icon={TriangleAlert} title="查询失败" tone="warning" /> : null}
            </div>
            <div className="bg-background p-4">
              <KnowledgeChatInput
                disabled={!projectSelected}
                includeExplorations={form.includeExplorations}
                includeRequirements={form.includeRequirements}
                loading={running}
                onSourceChange={(next) => onFormChange({ ...form, ...next })}
                onSubmit={onSubmit}
                onValueChange={onValueChange}
                value={value}
              />
            </div>
          </div>
        )}
      </div>
    </ShellSection>
  );
}

function ChatMessage({
  body,
  children,
  icon: Icon,
  loading = false,
  title,
  tone,
}: {
  body: string;
  children?: React.ReactNode;
  icon: React.ComponentType<{ className?: string }>;
  loading?: boolean;
  title: string;
  tone: "assistant" | "user" | "warning";
}) {
  const isUser = tone === "user";
  return (
    <div className={isUser ? "flex justify-end" : "flex justify-start"}>
      <div className={isUser ? "max-w-[82%]" : "max-w-[88%]"}>
        <div className={isUser ? "flex flex-row-reverse items-center gap-2" : "flex items-center gap-2"}>
          <div className="flex size-7 items-center justify-center rounded-lg border bg-background">
            <Icon className={loading ? "size-4 animate-spin" : "size-4"} />
          </div>
          <div className="font-medium text-muted-foreground text-xs">{title}</div>
        </div>
        <div
          className={
            isUser
              ? "mt-2 rounded-lg bg-primary p-3 text-primary-foreground text-sm"
              : tone === "warning"
                ? "mt-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-destructive text-sm"
                : "mt-2 rounded-lg border bg-background p-3 text-sm"
          }
        >
          <p className="whitespace-pre-wrap leading-6">{body}</p>
          {children}
        </div>
      </div>
    </div>
  );
}

function CompanyKnowledgeDialog({
  files,
  form,
  mode,
  onFilesChange,
  onFormChange,
  onOpenChange,
  onSubmit,
  open,
  running,
}: {
  files: FileList | null;
  form: typeof emptyCompanyForm;
  mode: "create" | "version";
  onFilesChange: (files: FileList | null) => void;
  onFormChange: (form: typeof emptyCompanyForm) => void;
  onOpenChange: (open: boolean) => void;
  onSubmit: () => void;
  open: boolean;
  running: boolean;
}) {
  const isVersionMode = mode === "version";
  const idPrefix = isVersionMode ? "company-knowledge-version" : "company-knowledge-create";
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isVersionMode ? "新增公司知识版本" : "上传公司知识"}</DialogTitle>
          <DialogDescription>公司知识不关联项目，只用于跨项目复用的规范、模板、术语和流程。</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 md:grid-cols-2">
          {!isVersionMode ? (
            <>
              <div className="space-y-1">
                <Label htmlFor={`${idPrefix}-name`}>知识名称</Label>
                <Input
                  id={`${idPrefix}-name`}
                  value={form.name}
                  onChange={(event) => onFormChange({ ...form, name: event.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor={`${idPrefix}-type`}>知识类型</Label>
                <Select
                  value={form.knowledge_type}
                  onValueChange={(value) => onFormChange({ ...form, knowledge_type: value })}
                >
                  <SelectTrigger className="w-full" id={`${idPrefix}-type`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {knowledgeTypes.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </>
          ) : null}
          <div className="space-y-1">
            <Label htmlFor={`${idPrefix}-version`}>版本号</Label>
            <Input
              id={`${idPrefix}-version`}
              placeholder={isVersionMode ? "留空自动生成" : "v1"}
              value={form.version}
              onChange={(event) => onFormChange({ ...form, version: event.target.value })}
            />
          </div>
          {!isVersionMode ? (
            <div className="space-y-1">
              <Label htmlFor={`${idPrefix}-scope`}>适用范围</Label>
              <Input
                id={`${idPrefix}-scope`}
                value={form.scope}
                onChange={(event) => onFormChange({ ...form, scope: event.target.value })}
              />
            </div>
          ) : null}
          <div className="space-y-1 md:col-span-2">
            <Label htmlFor={`${idPrefix}-source-note`}>来源说明</Label>
            <Input
              id={`${idPrefix}-source-note`}
              value={form.source_note}
              onChange={(event) => onFormChange({ ...form, source_note: event.target.value })}
            />
          </div>
          {isVersionMode ? (
            <div className="space-y-1 md:col-span-2">
              <Label htmlFor={`${idPrefix}-change-summary`}>变更摘要</Label>
              <Textarea
                id={`${idPrefix}-change-summary`}
                value={form.change_summary}
                onChange={(event) => onFormChange({ ...form, change_summary: event.target.value })}
              />
            </div>
          ) : (
            <div className="space-y-1 md:col-span-2">
              <Label htmlFor={`${idPrefix}-description`}>描述</Label>
              <Textarea
                id={`${idPrefix}-description`}
                value={form.description}
                onChange={(event) => onFormChange({ ...form, description: event.target.value })}
              />
            </div>
          )}
          <div className="space-y-1 md:col-span-2">
            <Label htmlFor={`${idPrefix}-files`}>上传文件</Label>
            <Input
              id={`${idPrefix}-files`}
              accept=".md,.markdown,.txt,.doc,.docx,.pdf"
              multiple
              onChange={(event) => onFilesChange(event.target.files)}
              type="file"
            />
            <div className="text-muted-foreground text-xs">
              {files?.length ? `已选择 ${files.length} 个文件` : "支持 Markdown、TXT、DOCX、PDF。"}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button disabled={running} onClick={onSubmit}>
            <Upload className="size-4" />
            {running ? "处理中" : isVersionMode ? "上传新版本" : "上传"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
