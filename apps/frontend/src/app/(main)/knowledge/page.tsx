"use client";

import { useCallback, useEffect, useState } from "react";

import { Archive, BookOpen, Building2, Eye, FilePlus2, FolderKanban, RefreshCw, Rocket, Upload } from "lucide-react";

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
  type ApiKnowledgeBuild,
  type ApiKnowledgeBuildDetail,
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

export default function Page() {
  const [activeScope, setActiveScope] = useState<(typeof knowledgeScopes)[number]["value"]>("project");
  const [searchText, setSearchText] = useState("");
  const { currentProjectId, hydrate, scope } = useProjectContextStore();
  const [builds, setBuilds] = useState<ApiKnowledgeBuild[]>([]);
  const [selectedBuild, setSelectedBuild] = useState<ApiKnowledgeBuildDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [companyDocs, setCompanyDocs] = useState<ApiGlobalKnowledgeDocument[]>([]);
  const [selectedCompanyDoc, setSelectedCompanyDoc] = useState<ApiGlobalKnowledgeDetail | null>(null);
  const [companyDialogOpen, setCompanyDialogOpen] = useState(false);
  const [versionDialogOpen, setVersionDialogOpen] = useState(false);
  const [companyForm, setCompanyForm] = useState(emptyCompanyForm);
  const [companyFiles, setCompanyFiles] = useState<FileList | null>(null);
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(builds);
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
  const filteredRows = rows.filter((item) =>
    [item.build_no, item.status_label, item.summary, item.change_summary, item.updated_at].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );
  const filteredCompanyRows = companyRows.filter((item) =>
    [item.name, item.knowledge_type_label, item.version, item.scope, item.description, item.status_label].some(
      (value) => value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );
  const isCompanyKnowledge = activeScope === "company";
  const projectId = scope === "project" ? currentProjectId : null;
  const cannotGenerate = isCompanyKnowledge ? true : running ? true : projectId === null;

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const openBuild = useCallback(async (targetProjectId: string, buildId: string) => {
    const detail = await apiRequest<ApiKnowledgeBuildDetail>(
      `/projects/${targetProjectId}/knowledge/builds/${buildId}`,
    );
    setSelectedBuild(detail);
  }, []);

  const loadBuilds = useCallback(
    async (targetProjectId: string) => {
      setLoading(true);
      setError("");
      try {
        const nextBuilds = await apiRequest<ApiKnowledgeBuild[]>(`/projects/${targetProjectId}/knowledge/builds`);
        setBuilds(nextBuilds);
        if (nextBuilds[0]) {
          await openBuild(targetProjectId, nextBuilds[0].id);
        } else {
          setSelectedBuild(null);
        }
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "加载知识库失败。");
        setBuilds([]);
        setSelectedBuild(null);
      } finally {
        setLoading(false);
      }
    },
    [openBuild],
  );

  useEffect(() => {
    if (isCompanyKnowledge || projectId === null) {
      setBuilds([]);
      setSelectedBuild(null);
      return;
    }
    void loadBuilds(projectId);
  }, [isCompanyKnowledge, loadBuilds, projectId]);

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

  async function generateKnowledge() {
    if (!projectId) {
      setError("请先在顶部选择具体项目。");
      return;
    }
    setRunning(true);
    setError("");
    notifyAiTaskStarted();
    try {
      const detail = await apiRequest<ApiKnowledgeBuildDetail>(`/projects/${projectId}/knowledge/builds`, {
        method: "POST",
      });
      setSelectedBuild(detail);
      await loadBuilds(projectId);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "生成知识库失败。");
    } finally {
      setRunning(false);
    }
  }

  async function publishKnowledge(buildId: string) {
    if (!projectId) {
      return;
    }
    setRunning(true);
    setError("");
    try {
      const detail = await apiRequest<ApiKnowledgeBuildDetail>(
        `/projects/${projectId}/knowledge/builds/${buildId}/publish`,
        {
          method: "POST",
        },
      );
      setSelectedBuild(detail);
      await loadBuilds(projectId);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "发布知识库失败。");
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
      <ShellSection>
        {isCompanyKnowledge ? (
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
        ) : (
          <ListToolbar
            actions={
              <Button
                disabled={loading || running || !projectId}
                onClick={() => projectId && void loadBuilds(projectId)}
                variant="outline"
              >
                <RefreshCw className="size-4" />
                刷新
              </Button>
            }
            createDisabled={cannotGenerate}
            createLabel={running ? "生成中" : "生成知识库"}
            createTitle={!projectId ? "请先选择具体项目" : undefined}
            description={
              projectId ? "项目知识库基于已确认需求版本和已完成探索结果生成。" : "请先在顶部项目切换器选择具体项目。"
            }
            onBatchDelete={deleteSelected}
            onCreate={() => void generateKnowledge()}
            onSearch={setSearchText}
            placeholder="搜索模块、来源或版本"
            selectedCount={selectedCount}
            title="项目知识库列表"
          />
        )}
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部知识库"
                    checked={
                      isCompanyKnowledge
                        ? allCompanySelected || (partiallyCompanySelected ? "indeterminate" : false)
                        : allSelected || (partiallySelected ? "indeterminate" : false)
                    }
                    onCheckedChange={(checked) =>
                      isCompanyKnowledge ? toggleAllCompany(Boolean(checked)) : toggleAll(Boolean(checked))
                    }
                  />
                </TableHead>
                <TableHead>{isCompanyKnowledge ? "知识名称" : "构建编号"}</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>{isCompanyKnowledge ? "知识类型" : "来源"}</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isCompanyKnowledge
                ? filteredCompanyRows.map((item) => (
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
                  ))
                : filteredRows.map((item) => (
                    <TableRow data-state={selectedIds.includes(item.id) ? "selected" : undefined} key={item.id}>
                      <TableCell>
                        <Checkbox
                          aria-label={`选择 ${item.id}`}
                          checked={selectedIds.includes(item.id)}
                          onCheckedChange={(checked) => toggleOne(item.id, Boolean(checked))}
                        />
                      </TableCell>
                      <TableCell>
                        <button
                          className="text-left font-medium hover:underline"
                          onClick={() => projectId && void openBuild(projectId, item.id)}
                          type="button"
                        >
                          {item.build_no}
                        </button>
                        <div className="text-muted-foreground text-xs">{item.summary}</div>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            item.status === "published"
                              ? "secondary"
                              : item.status === "blocked"
                                ? "destructive"
                                : "outline"
                          }
                        >
                          {item.status_label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {item.source_document_version_ids.length} 个需求版本 / {item.exploration_run_ids.length} 个探索
                      </TableCell>
                      <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                      <TableCell>
                        <RowActions
                          actions={[
                            {
                              label: "查看",
                              icon: Eye,
                              onSelect: () => projectId && void openBuild(projectId, item.id),
                            },
                            {
                              label: "发布",
                              icon: Rocket,
                              disabled: item.status !== "draft" || running,
                              onSelect: () => void publishKnowledge(item.id),
                            },
                          ]}
                          label="打开操作菜单"
                        />
                      </TableCell>
                    </TableRow>
                  ))}
              {(isCompanyKnowledge ? filteredCompanyRows.length : filteredRows.length) === 0 ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
                    {isCompanyKnowledge
                      ? loading
                        ? "正在加载公司知识库。"
                        : "暂无公司知识。管理员可上传测试规范、模板、术语或流程。"
                      : loading
                        ? "正在加载项目知识库。"
                        : "暂无项目知识库。选择具体项目后点击生成知识库。"}
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
        {error ? <p className="mt-3 text-destructive text-sm">{error}</p> : null}
      </ShellSection>
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
      {!isCompanyKnowledge && selectedBuild ? (
        <ShellSection className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <BookOpen className="size-4 text-muted-foreground" />
              <h2 className="font-medium text-sm">{selectedBuild.build.build_no} 页面</h2>
              <Badge variant="outline">{selectedBuild.pages.length} 页</Badge>
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              {selectedBuild.pages.map((page) => (
                <div className="rounded-lg border p-3" key={page.id}>
                  <div className="font-medium text-sm">{page.title}</div>
                  <div className="mt-1 text-muted-foreground text-xs">{page.relative_path}</div>
                  <p className="mt-2 line-clamp-2 text-muted-foreground text-xs">
                    {page.summary || "模块化 wiki 页面。"}
                  </p>
                </div>
              ))}
            </div>
          </div>
          <aside className="space-y-3">
            <div>
              <h3 className="font-medium text-sm">构建摘要</h3>
              <p className="mt-1 text-muted-foreground text-xs">{selectedBuild.build.change_summary}</p>
            </div>
            <div>
              <h3 className="font-medium text-sm">阻塞项</h3>
              <div className="mt-2 space-y-2">
                {selectedBuild.build.blockers.length ? (
                  selectedBuild.build.blockers.map((blocker) => (
                    <div className="rounded-md border border-destructive/30 p-2 text-destructive text-xs" key={blocker}>
                      {blocker}
                    </div>
                  ))
                ) : (
                  <p className="text-muted-foreground text-xs">无阻塞项。</p>
                )}
              </div>
            </div>
            <div>
              <h3 className="font-medium text-sm">质量检查</h3>
              <div className="mt-2 space-y-2">
                {selectedBuild.lint_issues.map((issue) => (
                  <div className="rounded-md border p-2 text-xs" key={issue.id}>
                    <span className="font-medium">{issue.title}</span>
                    <p className="mt-1 text-muted-foreground">{issue.detail}</p>
                  </div>
                ))}
                {selectedBuild.lint_issues.length === 0 ? (
                  <p className="text-muted-foreground text-xs">暂无 lint 问题。</p>
                ) : null}
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
