"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useParams, useRouter, useSearchParams } from "next/navigation";

import {
  ArrowLeft,
  Check,
  Download,
  FileSearch,
  FileText,
  GitMerge,
  Info,
  Loader2,
  Pencil,
  Save,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { OriginalFilePreview } from "@/components/ai-testing/original-file-preview";
import { ListToolbar, PageShell, RowActions, ShellSection, SoonPage } from "@/components/ai-testing/page-shell";
import {
  RequirementFileSwitcher,
  type RequirementSwitcherFile,
} from "@/components/ai-testing/requirement-file-switcher";
import { StandardMarkdownEditor } from "@/components/ai-testing/standard-markdown-editor";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { AiEditInput } from "@/components/ui/ai-input";
import { Badge } from "@/components/ui/badge";
import { Banner } from "@/components/ui/banner";
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
import { DynamicIslandTOC } from "@/components/ui/dynamic-island-toc";
import FileUpload1 from "@/components/ui/file-upload-1";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import { apiBlobRequest, apiRequest, formatDateTime } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";

const STANDARD_FILE_SECTION_ID = "standard-file-section";
const ORIGINAL_FILE_SECTION_ID = "original-file-section";
const INITIAL_REQUIREMENT_SECTION_ID = "initial-requirement-section";
const FINAL_REQUIREMENT_SECTION_ID = "final-requirement-section";
const MERGED_REQUIREMENT_TAB_KEY = "requirement";
const REQUIREMENT_DOCUMENT_TOC_SELECTOR =
  '[data-state="active"] .requirement-document-preview h1, [data-state="active"] .requirement-document-preview h2, [data-state="active"] .requirement-document-preview h3, [data-state="active"] .requirement-document-preview h4, [data-state="active"] .requirement-document-preview [data-toc], [data-state="active"] .requirement-artifact-preview h1, [data-state="active"] .requirement-artifact-preview h2, [data-state="active"] .requirement-artifact-preview h3, [data-state="active"] .requirement-artifact-preview h4, [data-state="active"] .requirement-artifact-preview [data-toc]';

type RequirementConflict = {
  id: string;
  title: string;
  source_file_names: string;
  fragment_a: string;
  fragment_b: string;
  resolution: string;
  resolution_type: string;
  status: string;
};

type SourceFile = RequirementSwitcherFile & {
  version_id: string | null;
  version_no: number | null;
  markdown_file_path: string | null;
  conversion_summary: string;
  standard_file_status?: "generating" | "ready" | "edited" | "failed";
  conflict_status?: string;
};

type RequirementOverviewResponse = {
  document: {
    id: string;
    project_id: string;
    name: string;
    document_type: string;
    status: string;
    updated_at: string;
    current_version_id: string | null;
  };
  stats: {
    total_files: number;
    conversion_success: number;
    conversion_warning: number;
    conversion_failed: number;
    mergeable_files: number;
    open_conflicts: number;
    initial_requirement_status: string;
  };
  files: SourceFile[];
  has_open_conflicts: boolean;
  merge_sync_status: "synced" | "outdated";
  changed_standard_files: SourceFile[];
  initial_markdown_content: string;
  artifact_tabs: MergeArtifactTab[];
};

type OriginalPreview = {
  title: string;
  fileFormat: string;
  contentType: "text" | "file";
  content: string;
  objectUrl?: string;
};

type StandardPreview = {
  fileId: string;
  title: string;
  markdownContent: string;
  conversionSummary: string;
};

type DocumentEditResponse = {
  edited_content: string;
  change_summary: string;
};

type MergePreview = {
  previewId: string;
  markdownContent: string;
  mergeSummary: string;
  qualityResult?: "passed" | "warning" | "failed";
  artifactTabs: MergeArtifactTab[];
};

type MergeArtifactTab = {
  key: "quality" | "confirmations" | "merged" | "mapping" | "conflicts";
  label: string;
  path: string;
  content: string;
};

type RequirementAnalysisQuestion = {
  id: string;
  module_key: string;
  module_name: string;
  question: string;
  reason: string;
  impact: string;
  dimension: string;
  severity: "blocker" | "major" | "minor";
  source_excerpt: string;
};

type RequirementAnalysisResult = {
  id: string;
  document_id: string;
  version_id: string;
  status: "completed" | "needs_clarification" | "blocked";
  analysis_summary: string;
  quality_result: "passed" | "warning" | "blocked";
  testability_score: number;
  created_by: string;
  created_at: string;
  output: {
    status: "completed" | "needs_clarification" | "blocked";
    analysis_summary: string;
    modules: Array<{
      module_key: string;
      module_name: string;
      summary: string;
      business_objects: string[];
      capabilities: string[];
      rules: string[];
      fields: string[];
      state_flows: string[];
      dependencies: string[];
      risks: string[];
    }>;
    clarification_questions: RequirementAnalysisQuestion[];
    coverage_audit: Array<{
      module_key: string;
      module_name: string;
      source_excerpt: string;
      analysis_status: string;
      reason: string;
    }>;
    quality_gate: {
      result: "passed" | "warning" | "blocked";
      testability_score: number;
      blocking_issues: string[];
      warning_issues: string[];
      passed_checks: string[];
    };
    next_actions: string[];
  };
};

function fallbackMergeArtifactTabs(previewId: string): MergeArtifactTab[] {
  return [
    {
      key: "quality",
      label: "质量检测",
      path: `quality/${previewId}.md`,
      content: "# 质量检测\n\n暂无质量检测产物。",
    },
    {
      key: "confirmations",
      label: "待确认项",
      path: `confirmations/${previewId}.md`,
      content: "# 待确认项\n\n本次未发现需要人工确认的差异。",
    },
  ];
}

function normalizeMergeArtifactTabs(tabs: MergeArtifactTab[] | undefined): MergeArtifactTab[] {
  const normalized = (tabs ?? [])
    .map((artifact) => {
      if (artifact.key === "mapping") {
        return { ...artifact, key: "quality" as const, label: "质量检测" };
      }
      if (artifact.key === "conflicts") {
        return { ...artifact, key: "confirmations" as const, label: "待确认项" };
      }
      return artifact;
    })
    .filter((artifact) => artifact.key === "quality" || artifact.key === "confirmations");
  const seen = new Set<string>();
  return normalized.filter((artifact) => {
    if (seen.has(artifact.key)) {
      return false;
    }
    seen.add(artifact.key);
    return true;
  });
}

function mergeResponseArtifactTabs(tabs: MergeArtifactTab[] | undefined, fallbackId: string): MergeArtifactTab[] {
  return tabs && tabs.length > 0 ? normalizeMergeArtifactTabs(tabs) : fallbackMergeArtifactTabs(fallbackId);
}

type MergeResponse =
  | {
      status: "merged";
      version_id: string;
      version_no: number;
      markdown_content: string;
      merge_summary: string;
      source_file_ids: string[];
      quality_result?: "passed" | "warning" | "failed";
      artifact_tabs?: MergeArtifactTab[];
    }
  | {
      status: "preview";
      preview_id: string;
      markdown_preview: string;
      merge_summary: string;
      diff_summary: string;
      affected_modules: string[];
      source_file_ids: string[];
      quality_result?: "passed" | "warning" | "failed";
      artifact_tabs?: MergeArtifactTab[];
      conflict_count?: number;
      conflicts?: RequirementConflict[];
    }
  | {
      status: "conflict";
      run_id: string;
      merge_summary: string;
      diff_summary: string;
      affected_modules: string[];
      source_file_ids: string[];
      conflict_count: number;
      conflicts: RequirementConflict[];
    };

const conversionLabels: Record<string, string> = {
  pending: "待转换",
  processing: "转换中",
  success: "转换成功",
  warning: "有警告",
  failed: "转换失败",
};

const mappingLabels: Record<string, string> = {
  pending_merge: "待归并",
  pending_review: "待评审",
  merged: "已归并",
  discarded: "已废弃",
};

const standardFileLabels: Record<string, string> = {
  generating: "生成中",
  ready: "可合并",
  edited: "已修改",
  failed: "生成失败",
};

const initialRequirementLabels: Record<string, string> = {
  generated: "已生成",
  not_generated: "未生成",
};

export default function DocumentDetailPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const params = useParams<{ projectId: string; documentId: string }>();
  const { projectId, documentId } = params;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [overview, setOverview] = useState<RequirementOverviewResponse | null>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [selectedFileId, setSelectedFileId] = useState("");
  const [originalPreview, setOriginalPreview] = useState<OriginalPreview | null>(null);
  const [standardPreview, setStandardPreview] = useState<StandardPreview | null>(null);
  const [standardLoading, setStandardLoading] = useState(false);
  const [standardError, setStandardError] = useState("");
  const [markdownDraft, setMarkdownDraft] = useState("");
  const [editingStandard, setEditingStandard] = useState(false);
  const [savingStandard, setSavingStandard] = useState(false);
  const [editingStandardWithAi, setEditingStandardWithAi] = useState(false);
  const [initialMarkdownDraft, setInitialMarkdownDraft] = useState("");
  const [editingInitial, setEditingInitial] = useState(false);
  const [savingInitial, setSavingInitial] = useState(false);
  const [merging, setMerging] = useState(false);
  const [mergeError, setMergeError] = useState("");
  const [mergePreview, setMergePreview] = useState<MergePreview | null>(null);
  const [mergeArtifactTab, setMergeArtifactTab] = useState(MERGED_REQUIREMENT_TAB_KEY);
  const [mergeArtifactTabs, setMergeArtifactTabs] = useState<MergeArtifactTab[]>([]);
  const [analysisResult, setAnalysisResult] = useState<RequirementAnalysisResult | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [conflicts, setConflicts] = useState<RequirementConflict[]>([]);
  const [conflictDrafts, setConflictDrafts] = useState<Record<string, string>>({});
  const token = useAuthStore((state) => state.token);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadSubmitting, setUploadSubmitting] = useState(false);
  const [uploadStates, setUploadStates] = useState<
    Record<string, { progress: number; status: "idle" | "uploading" | "completed" | "error" }>
  >({});
  const [fileSearchText, setFileSearchText] = useState("");
  const {
    allSelected: allFilesSelected,
    clearSelection: clearFileSelection,
    partiallySelected: partiallyFilesSelected,
    rows: fileRows,
    selectedCount: fileSelectedCount,
    selectedIds: fileSelectedIds,
    setRows: setFileRows,
    toggleAll: toggleAllFiles,
    toggleOne: toggleOneFile,
  } = useLocalTableSelection<SourceFile>([]);

  const selectedFile = useMemo(
    () => overview?.files.find((file) => file.id === selectedFileId) ?? overview?.files[0] ?? null,
    [overview?.files, selectedFileId],
  );
  const selectedFileRef = useRef<SourceFile | null>(null);
  const filteredFiles = useMemo(
    () =>
      fileRows.filter((file) =>
        [file.original_filename, file.file_format, file.conversion_status, file.mapping_status].some((value) =>
          value?.toLowerCase().includes(fileSearchText.trim().toLowerCase()),
        ),
      ),
    [fileRows, fileSearchText],
  );
  const currentStandardPreview = standardPreview?.fileId === selectedFile?.id ? standardPreview : null;
  const canEditStandard = Boolean(currentStandardPreview) && !standardLoading && standardError.length === 0;
  const selectedStandardGenerating = Boolean(
    selectedFile &&
      (selectedFile.standard_file_status === "generating" ||
        ["pending", "processing"].includes(selectedFile.conversion_status)),
  );
  const showConflictTab = Boolean(overview?.has_open_conflicts || conflicts.length > 0);
  const rawInitialArtifactTabs = mergePreview?.artifactTabs?.length ? mergePreview.artifactTabs : mergeArtifactTabs;
  const initialArtifactTabs = useMemo(
    () => normalizeMergeArtifactTabs(rawInitialArtifactTabs),
    [rawInitialArtifactTabs],
  );
  const changedStandardFiles = overview?.changed_standard_files ?? [];
  const isInitialRequirementOutdated =
    Boolean(overview?.initial_markdown_content.trim()) &&
    overview?.merge_sync_status === "outdated" &&
    changedStandardFiles.length > 0;
  const initialMarkdownContent = mergePreview?.markdownContent ?? overview?.initial_markdown_content ?? "";
  const displayInitialMarkdownContent = merging && !mergePreview ? "" : initialMarkdownContent;
  const hasRunningConversions = Boolean(
    overview?.files.some((file) => ["pending", "processing"].includes(file.conversion_status)),
  );
  const selectedFileEffectKey = selectedFile
    ? [selectedFile.id, selectedFile.conversion_status, selectedFile.standard_file_status].join(":")
    : "";

  const updateConflicts = useCallback((nextConflicts: unknown) => {
    const normalizedConflicts: RequirementConflict[] = Array.isArray(nextConflicts) ? nextConflicts : [];
    setConflicts(normalizedConflicts as RequirementConflict[]);
    setConflictDrafts(
      Object.fromEntries(
        normalizedConflicts.map((conflict) => [conflict.id, conflict.resolution || conflict.fragment_a]),
      ),
    );
  }, []);

  const loadConflicts = useCallback(async () => {
    try {
      const data = await apiRequest<RequirementConflict[]>(
        `/projects/${projectId}/requirements/${documentId}/conflicts`,
      );
      updateConflicts(data);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "冲突列表加载失败");
    }
  }, [documentId, projectId, updateConflicts]);

  const loadOverview = useCallback(
    async ({ refreshArtifacts = true, silent = false }: { refreshArtifacts?: boolean; silent?: boolean } = {}) => {
      if (!silent) {
        setLoading(true);
      }
      setError("");
      try {
        const data = await apiRequest<RequirementOverviewResponse>(
          `/projects/${projectId}/requirements/${documentId}/overview`,
        );
        setOverview(data);
        setFileRows(data.files);
        if (refreshArtifacts) {
          setMergeArtifactTabs(data.artifact_tabs ?? []);
        }
        setSelectedFileId((current) => current || data.files[0]?.id || "");
        if (data.has_open_conflicts) {
          void loadConflicts();
        } else {
          updateConflicts([]);
        }
        return data;
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "需求概览加载失败");
        return null;
      } finally {
        if (!silent) {
          setLoading(false);
        }
      }
    },
    [documentId, loadConflicts, projectId, setFileRows, updateConflicts],
  );

  const loadReadableOriginalPreview = useCallback(async (file: SourceFile) => {
    setOriginalPreview(null);
    try {
      const data = await apiRequest<{
        original_filename: string;
        file_format: string;
        content_type: "text" | "download";
        content?: string;
        download_path?: string;
      }>(`/requirement-files/${file.id}/original`);
      if (data.content_type === "text") {
        setOriginalPreview({
          title: data.original_filename,
          fileFormat: data.file_format,
          contentType: "text",
          content: data.content ?? "",
        });
        return;
      }
      const blob = await apiBlobRequest(`/requirement-files/${file.id}/original/content`);
      setOriginalPreview({
        title: data.original_filename,
        fileFormat: data.file_format,
        contentType: "file",
        content: data.download_path ?? "",
        objectUrl: URL.createObjectURL(blob),
      });
    } catch (requestError) {
      setOriginalPreview(null);
      toast.error(requestError instanceof Error ? requestError.message : "原始文件预览失败");
    }
  }, []);

  const loadStandardPreview = useCallback(async (file: SourceFile) => {
    setStandardLoading(true);
    setStandardError("");
    if (file.standard_file_status === "generating" || ["pending", "processing"].includes(file.conversion_status)) {
      setStandardLoading(false);
      return;
    }
    try {
      const data = await apiRequest<{
        original_filename: string;
        markdown_content: string;
        conversion_summary: string;
      }>(`/requirement-files/${file.id}/markdown`);
      setStandardPreview({
        fileId: file.id,
        title: standardMarkdownFilename(data.original_filename),
        markdownContent: data.markdown_content,
        conversionSummary: data.conversion_summary,
      });
      setMarkdownDraft(data.markdown_content);
    } catch (requestError) {
      setStandardPreview(null);
      setMarkdownDraft("");
      setStandardError(requestError instanceof Error ? requestError.message : "标准文件生成失败");
      toast.error(requestError instanceof Error ? requestError.message : "标准文件加载失败");
    } finally {
      setStandardLoading(false);
    }
  }, []);

  useEffect(() => {
    const queryTab = searchParams.get("tab");
    if (
      queryTab &&
      ["overview", "original", "standard", "initial", "clarification", "final", "conflicts"].includes(queryTab)
    ) {
      setActiveTab(queryTab);
    }
    void loadOverview();
  }, [loadOverview, searchParams]);

  useEffect(() => {
    selectedFileRef.current = selectedFile;
  }, [selectedFile]);

  useEffect(() => {
    if (!selectedFileEffectKey) {
      return;
    }
    const file = selectedFileRef.current;
    if (!file) {
      return;
    }
    if (activeTab === "original") {
      void loadReadableOriginalPreview(file);
    }
    if (activeTab === "standard") {
      setEditingStandard(false);
      void loadStandardPreview(file);
    }
  }, [activeTab, loadReadableOriginalPreview, loadStandardPreview, selectedFileEffectKey]);

  useEffect(() => {
    if (activeTab !== "initial") {
      setEditingInitial(false);
      return;
    }
    setInitialMarkdownDraft(initialMarkdownContent);
  }, [activeTab, initialMarkdownContent]);

  useEffect(() => {
    if (!initialArtifactTabs.length) {
      return;
    }
    if (
      mergeArtifactTab !== MERGED_REQUIREMENT_TAB_KEY &&
      !initialArtifactTabs.some((artifact) => artifact.key === mergeArtifactTab)
    ) {
      setMergeArtifactTab(MERGED_REQUIREMENT_TAB_KEY);
    }
  }, [initialArtifactTabs, mergeArtifactTab]);

  useEffect(() => {
    if (!hasRunningConversions) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadOverview({ silent: true });
    }, 3000);
    return () => window.clearInterval(timer);
  }, [hasRunningConversions, loadOverview]);

  useEffect(() => {
    return () => {
      if (originalPreview?.objectUrl) {
        URL.revokeObjectURL(originalPreview.objectUrl);
      }
    };
  }, [originalPreview?.objectUrl]);

  function selectFileForTab(fileId: string, tab: string) {
    setSelectedFileId(fileId);
    setActiveTab(tab);
  }

  async function saveStandardMarkdown() {
    if (!selectedFile) {
      return;
    }
    setSavingStandard(true);
    try {
      const data = await apiRequest<{
        original_filename: string;
        markdown_content: string;
        conversion_summary: string;
      }>(`/requirement-files/${selectedFile.id}/markdown`, {
        method: "PUT",
        body: JSON.stringify({ markdown_content: markdownDraft, change_summary: "人工修订标准文件" }),
      });
      setStandardPreview({
        fileId: selectedFile.id,
        title: data.original_filename,
        markdownContent: data.markdown_content,
        conversionSummary: data.conversion_summary,
      });
      setEditingStandard(false);
      toast.success("标准文件已保存");
      await loadOverview({ silent: true });
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "标准文件保存失败");
    } finally {
      setSavingStandard(false);
    }
  }

  async function editStandardMarkdownWithAi(instruction: string) {
    if (!selectedFile || !currentStandardPreview) {
      return;
    }
    setEditingStandardWithAi(true);
    try {
      const editResult = await apiRequest<DocumentEditResponse>("/agents/document-editor/run", {
        method: "POST",
        body: JSON.stringify({
          content: currentStandardPreview.markdownContent,
          instruction,
        }),
      });
      if (!editResult.edited_content.trim()) {
        toast.info(editResult.change_summary || "AI 未修改文档");
        return;
      }
      const savedResult = await apiRequest<{
        original_filename: string;
        markdown_content: string;
        conversion_summary: string;
      }>(`/requirement-files/${selectedFile.id}/markdown`, {
        method: "PUT",
        body: JSON.stringify({
          markdown_content: editResult.edited_content,
          change_summary: `AI修改：${editResult.change_summary}`,
        }),
      });
      setStandardPreview({
        fileId: selectedFile.id,
        title: savedResult.original_filename,
        markdownContent: savedResult.markdown_content,
        conversionSummary: savedResult.conversion_summary,
      });
      setMarkdownDraft(savedResult.markdown_content);
      setEditingStandard(false);
      toast.success(editResult.change_summary || "AI修改已保存");
      await loadOverview({ silent: true });
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "智能修改失败");
    } finally {
      setEditingStandardWithAi(false);
    }
  }

  async function saveInitialRequirement() {
    if (!overview) {
      return;
    }
    setSavingInitial(true);
    try {
      const detail = await apiRequest<{ document?: { name?: string }; initial_markdown_content?: string }>(
        `/projects/${projectId}/requirements/${documentId}`,
        {
          method: "PUT",
          body: JSON.stringify({
            name: overview.document.name,
            markdown_content: initialMarkdownDraft,
            change_summary: "人工编辑初始需求",
          }),
        },
      );
      const nextContent = detail.initial_markdown_content ?? initialMarkdownDraft;
      setMergePreview(null);
      setInitialMarkdownDraft(nextContent);
      setEditingInitial(false);
      toast.success("初始需求已保存为新版本");
      await loadOverview({ silent: true });
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "初始需求保存失败");
    } finally {
      setSavingInitial(false);
    }
  }

  async function runRequirementAnalysis() {
    setAnalysisLoading(true);
    try {
      const result = await apiRequest<RequirementAnalysisResult>(
        `/projects/${projectId}/requirements/${documentId}/analysis`,
        {
          method: "POST",
        },
      );
      setAnalysisResult(result);
      toast.success("需求分析已完成");
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "需求分析失败");
    } finally {
      setAnalysisLoading(false);
    }
  }

  async function mergeRequirement() {
    setMerging(true);
    setMergeError("");
    setMergePreview(null);
    setMergeArtifactTabs([]);
    setMergeArtifactTab(MERGED_REQUIREMENT_TAB_KEY);
    notifyAiTaskStarted();
    try {
      const result = await apiRequest<MergeResponse>(`/projects/${projectId}/requirements/${documentId}/merge`, {
        method: "POST",
        body: JSON.stringify({ merge_mode: "rebuild", force_rebuild: true }),
      });
      if (result.status === "merged") {
        setMergeError("");
        const artifactTabs = mergeResponseArtifactTabs(result.artifact_tabs, result.version_id);
        setMergeArtifactTabs(artifactTabs);
        setMergePreview({
          previewId: result.version_id,
          markdownContent: result.markdown_content,
          mergeSummary: result.merge_summary,
          qualityResult: result.quality_result,
          artifactTabs,
        });
        setMergeArtifactTab(MERGED_REQUIREMENT_TAB_KEY);
        toast.success("合并需求稿已写入最终需求");
        await loadOverview({ silent: true });
        setActiveTab("initial");
        return;
      }
      if (result.status === "preview") {
        setMergeError("");
        const artifactTabs = mergeResponseArtifactTabs(result.artifact_tabs, result.preview_id);
        setMergeArtifactTabs(artifactTabs);
        setMergePreview({
          previewId: result.preview_id,
          markdownContent: result.markdown_preview,
          mergeSummary: result.merge_summary,
          qualityResult: result.quality_result,
          artifactTabs,
        });
        setMergeArtifactTab(MERGED_REQUIREMENT_TAB_KEY);
        updateConflicts(result.conflicts ?? []);
        toast.warning("合并未写入最终需求，请查看质量检测和待确认项");
        await loadOverview({ silent: true });
        setActiveTab("initial");
        return;
      }
      if (result.status === "conflict") {
        setMergeError("");
        setMergePreview(null);
        setMergeArtifactTabs([]);
        updateConflicts(result.conflicts ?? []);
        toast.warning(`发现 ${result.conflict_count} 个待确认项，请先处理后再生成合并需求稿`);
        await loadOverview({ refreshArtifacts: false, silent: true });
        setActiveTab("conflicts");
        return;
      }
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "需求合并失败";
      setMergeError(message);
      toast.error(message);
      setMergePreview(null);
      setMergeArtifactTabs([]);
      await loadOverview({ refreshArtifacts: false, silent: true });
      setMergeArtifactTab(MERGED_REQUIREMENT_TAB_KEY);
      setActiveTab("initial");
    } finally {
      setMerging(false);
    }
  }

  async function deleteSourceFiles(ids: string[]) {
    if (ids.length === 0) return;
    try {
      await Promise.all(ids.map((id) => apiRequest(`/requirement-files/${id}`, { method: "DELETE" })));
      setFileRows((current) => current.filter((row) => !ids.includes(row.id)));
      clearFileSelection();
      toast.success(`已删除 ${ids.length} 个原始文件`);
      await loadOverview({ silent: true });
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "原始文件删除失败");
    }
  }

  function downloadOriginalPreview() {
    if (!originalPreview) {
      return;
    }
    const filename = originalPreview.title || selectedFile?.original_filename || "原始文件";
    let href = originalPreview.objectUrl;
    let shouldRevoke = false;

    if (originalPreview.contentType === "text") {
      const blob = new Blob([originalPreview.content], {
        type: "text/plain;charset=utf-8",
      });
      href = URL.createObjectURL(blob);
      shouldRevoke = true;
    }

    if (!href) {
      toast.error("当前文件尚未加载完成，无法下载");
      return;
    }

    const link = document.createElement("a");
    link.href = href;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();

    if (shouldRevoke) {
      URL.revokeObjectURL(href);
    }
  }

  function openUploadDialog() {
    setUploadFiles([]);
    setUploadStates({});
    setUploadDialogOpen(true);
  }

  async function submitUploadFiles() {
    if (uploadFiles.length === 0) {
      toast.error("请选择至少一个文件");
      return;
    }
    const unsupported = uploadFiles.find((f) => !/\.(pdf|doc|docx|txt|md|markdown)$/i.test(f.name));
    if (unsupported) {
      toast.error(`仅支持 PDF、Word、TXT、MD 文件：${unsupported.name}`);
      return;
    }

    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
    setUploadSubmitting(true);
    setUploadStates(
      Object.fromEntries(
        uploadFiles.map((f) => [`${f.name}-${f.size}`, { progress: 1, status: "uploading" as const }]),
      ),
    );

    try {
      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${apiBase}/projects/${projectId}/requirements`);
        if (token) {
          xhr.setRequestHeader("Authorization", `Bearer ${token}`);
        }
        xhr.upload.onprogress = (event) => {
          if (!event.lengthComputable) return;
          const progress = Math.min(99, Math.round((event.loaded / event.total) * 100));
          setUploadStates(
            Object.fromEntries(
              uploadFiles.map((f) => [`${f.name}-${f.size}`, { progress, status: "uploading" as const }]),
            ),
          );
        };
        xhr.onload = () => {
          const payload = (() => {
            try {
              return JSON.parse(xhr.responseText);
            } catch {
              return null;
            }
          })();
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
            return;
          }
          reject(new Error(payload?.detail?.message ?? payload?.detail ?? "文件上传失败"));
        };
        xhr.onerror = () => reject(new Error("网络异常，文件上传失败"));
        const formData = new FormData();
        formData.append("mode", "append");
        formData.append("existing_document_id", documentId);
        for (const f of uploadFiles) {
          formData.append("files", f);
        }
        xhr.send(formData);
      });
      setUploadStates(
        Object.fromEntries(
          uploadFiles.map((f) => [`${f.name}-${f.size}`, { progress: 100, status: "completed" as const }]),
        ),
      );
      toast.success("文件已上传，正在后台生成标准文件");
      setUploadDialogOpen(false);
      notifyAiTaskStarted();
      await loadOverview({ silent: true });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "文件上传失败");
      setUploadStates(
        Object.fromEntries(uploadFiles.map((f) => [`${f.name}-${f.size}`, { progress: 0, status: "error" as const }])),
      );
    } finally {
      setUploadSubmitting(false);
    }
  }

  async function saveConflictResolution(conflict: RequirementConflict) {
    const resolution = conflictDrafts[conflict.id]?.trim();
    if (!resolution) {
      toast.error("请填写冲突解决结果");
      return;
    }
    try {
      const result = await apiRequest<{ success: boolean; has_open_conflicts: boolean }>(
        `/projects/${projectId}/requirements/${documentId}/conflicts/${conflict.id}`,
        {
          method: "PUT",
          body: JSON.stringify({ resolution, resolution_type: "manual" }),
        },
      );
      toast.success("冲突解决结果已保存");
      await loadConflicts();
      await loadOverview({ silent: true });
      if (!result.has_open_conflicts) {
        setActiveTab("standard");
      }
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "冲突解决结果保存失败");
    }
  }

  if (loading) {
    return <SoonPage description="正在加载需求概览。" title="需求概览" />;
  }

  if (error || !overview) {
    return (
      <PageShell breadcrumbs={["项目", "需求"]} description="查看需求文件处理进度。" title="需求概览">
        <ShellSection>
          <div className="flex items-center justify-between gap-3">
            <div className="text-destructive text-sm">{error || "未找到需求文档。"}</div>
            <Button onClick={() => router.back()} variant="outline">
              <ArrowLeft className="size-4" />
              返回
            </Button>
          </div>
        </ShellSection>
      </PageShell>
    );
  }

  const showRequirementToc =
    (activeTab === "standard" && !editingStandard && Boolean(currentStandardPreview?.markdownContent.trim())) ||
    (activeTab === "initial" && !editingInitial && Boolean(initialMarkdownContent.trim())) ||
    (activeTab === "final" && Boolean(overview.initial_markdown_content.trim()));
  const requirementTocRefreshKey = [
    activeTab,
    selectedFile?.id ?? "",
    mergeArtifactTab,
    currentStandardPreview?.markdownContent.length ?? 0,
    initialMarkdownContent.length,
    overview.initial_markdown_content.length,
  ].join(":");
  const requirementTocAnchorSelector =
    activeTab === "standard"
      ? `#${STANDARD_FILE_SECTION_ID} .requirement-document-preview`
      : activeTab === "initial"
        ? `#${INITIAL_REQUIREMENT_SECTION_ID} [data-state="active"] .requirement-document-preview, #${INITIAL_REQUIREMENT_SECTION_ID} [data-state="active"] .requirement-artifact-preview`
        : `#${FINAL_REQUIREMENT_SECTION_ID} .requirement-document-preview`;
  const outdatedMergeBanner = isInitialRequirementOutdated ? (
    <Banner
      action={
        <Button disabled={merging} onClick={mergeRequirement} size="sm" type="button">
          {merging ? <Loader2 className="size-3.5 animate-spin" /> : <GitMerge className="size-3.5" />}
          {merging ? "合并中" : "重新合并"}
        </Button>
      }
      className="mb-4 border-sky-200 bg-sky-50 text-sky-950 dark:border-sky-800/70 dark:bg-sky-950/30 dark:text-sky-100"
      icon={<Info className="size-4" />}
      layout="complex"
      rounded="default"
      variant="default"
    >
      <div className="min-w-0">
        <div className="font-medium">标准文件已变更，当前合并需求稿可能不是最新</div>
        <div className="mt-1 text-current/75 text-xs">
          {overview.files.length} 个标准文件中有 {changedStandardFiles.length} 个在当前版本生成后变更：
          {changedStandardFiles
            .slice(0, 3)
            .map((file) => standardMarkdownFilename(file.original_filename))
            .join("、")}
          {changedStandardFiles.length > 3 ? " 等" : ""}。建议重新合并后查看归并产物。
        </div>
        {mergeError ? <div className="mt-2 text-destructive text-xs">合并失败：{mergeError}</div> : null}
      </div>
    </Banner>
  ) : null;

  return (
    <PageShell
      breadcrumbs={["项目", "需求", overview.document.name]}
      description="查看原始文件、标准文件、合并冲突和初始需求。"
      title="需求概览"
    >
      {showRequirementToc ? (
        <DynamicIslandTOC
          anchorSelector={requirementTocAnchorSelector}
          refreshKey={requirementTocRefreshKey}
          selector={REQUIREMENT_DOCUMENT_TOC_SELECTOR}
        />
      ) : null}
      <Tabs className="space-y-4" onValueChange={setActiveTab} value={activeTab}>
        <TabsList>
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="original">原始文件</TabsTrigger>
          <TabsTrigger value="standard">标准文件</TabsTrigger>
          <TabsTrigger value="initial">初始需求</TabsTrigger>
          <TabsTrigger value="clarification">需求澄清</TabsTrigger>
          <TabsTrigger value="final">最终需求</TabsTrigger>
          {showConflictTab ? <TabsTrigger value="conflicts">冲突处理</TabsTrigger> : null}
        </TabsList>

        <TabsContent value="overview">
          <div className="grid gap-3 md:grid-cols-4">
            <SummaryMetric label="原始文件" value={`${overview.stats.total_files}`} />
            <SummaryMetric label="可合并" value={`${overview.stats.mergeable_files}`} />
            <SummaryMetric label="待处理冲突" value={`${overview.stats.open_conflicts}`} />
            <SummaryMetric
              label="初始需求"
              value={initialRequirementLabels[overview.stats.initial_requirement_status] ?? "未生成"}
            />
          </div>
          <ShellSection className="mt-6">
            <ListToolbar
              description={`转换成功 ${overview.stats.conversion_success} · 有警告 ${overview.stats.conversion_warning} · 失败 ${overview.stats.conversion_failed}`}
              onBatchDelete={() => deleteSourceFiles(fileSelectedIds)}
              onCreate={openUploadDialog}
              onSearch={setFileSearchText}
              createLabel="上传文件"
              placeholder="搜索文件名或状态"
              selectedCount={fileSelectedCount}
              title="原始文件列表"
            />
            <div className="overflow-hidden rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <Checkbox
                        aria-label="选择全部文件"
                        checked={allFilesSelected || (partiallyFilesSelected ? "indeterminate" : false)}
                        onCheckedChange={(checked) => toggleAllFiles(Boolean(checked))}
                      />
                    </TableHead>
                    <TableHead>文件名</TableHead>
                    <TableHead>上传时间</TableHead>
                    <TableHead>转换状态</TableHead>
                    <TableHead>标准文件</TableHead>
                    <TableHead>合并状态</TableHead>
                    <TableHead className="w-16">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredFiles.map((file) => (
                    <TableRow data-state={fileSelectedIds.includes(file.id) ? "selected" : undefined} key={file.id}>
                      <TableCell>
                        <Checkbox
                          aria-label={`选择 ${displayFilename(file.original_filename)}`}
                          checked={fileSelectedIds.includes(file.id)}
                          onCheckedChange={(checked) => toggleOneFile(file.id, Boolean(checked))}
                        />
                      </TableCell>
                      <TableCell className="font-medium">
                        <button
                          className="block truncate text-left hover:underline"
                          onClick={() => selectFileForTab(file.id, "original")}
                          type="button"
                        >
                          {displayFilename(file.original_filename)}
                        </button>
                      </TableCell>
                      <TableCell>{formatDateTime(file.created_at)}</TableCell>
                      <TableCell>
                        <StatusBadge
                          loading={["pending", "processing"].includes(file.conversion_status)}
                          status={file.conversion_status}
                          statusLabels={conversionLabels}
                        />
                      </TableCell>
                      <TableCell>
                        <Button
                          className="h-auto px-0"
                          disabled={!["success", "warning", "failed"].includes(file.conversion_status)}
                          onClick={() => selectFileForTab(file.id, "standard")}
                          type="button"
                          variant="link"
                        >
                          {standardFileLabels[file.standard_file_status ?? ""] ?? "未生成"}
                        </Button>
                      </TableCell>
                      <TableCell>
                        <Badge variant={file.mapping_status === "pending_merge" ? "outline" : "secondary"}>
                          {mappingLabels[file.mapping_status] ?? file.mapping_status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <RowActions
                          actions={[
                            {
                              label: "查看原文",
                              icon: FileText,
                              onSelect: () => selectFileForTab(file.id, "original"),
                            },
                            {
                              label: "查看标准文件",
                              icon: FileText,
                              onSelect: () => selectFileForTab(file.id, "standard"),
                              disabled: !["success", "warning", "failed"].includes(file.conversion_status),
                            },
                            {
                              label: "删除",
                              icon: Trash2,
                              destructive: true,
                              onSelect: () => deleteSourceFiles([file.id]),
                            },
                          ]}
                          label={`打开 ${displayFilename(file.original_filename)} 操作菜单`}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                  {filteredFiles.length === 0 ? (
                    <TableRow>
                      <TableCell className="py-8 text-center text-muted-foreground text-sm" colSpan={7}>
                        暂无原始文件。上传需求文件后，可发起格式转换、归并和分析。
                      </TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </div>
          </ShellSection>

          <Dialog onOpenChange={setUploadDialogOpen} open={uploadDialogOpen}>
            <DialogContent className="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>上传原始文件</DialogTitle>
                <DialogDescription>
                  选择文件后直接追加到当前需求，支持 PDF、Word（doc/docx）、TXT、MD 格式。
                </DialogDescription>
              </DialogHeader>
              <FileUpload1
                accept={{
                  "application/pdf": [".pdf"],
                  "application/msword": [".doc"],
                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
                  "text/markdown": [".md", ".markdown"],
                  "text/plain": [".txt"],
                }}
                files={uploadFiles}
                hint="仅支持 PDF、Word（doc/docx）、TXT、MD 文件"
                maxFiles={10}
                uploadStates={uploadStates}
                onFilesChange={setUploadFiles}
              />
              <DialogFooter>
                <Button
                  disabled={uploadSubmitting}
                  onClick={() => setUploadDialogOpen(false)}
                  type="button"
                  variant="outline"
                >
                  取消
                </Button>
                <Button
                  disabled={uploadSubmitting || uploadFiles.length === 0}
                  onClick={submitUploadFiles}
                  type="button"
                >
                  {uploadSubmitting ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
                  {uploadSubmitting ? "上传中" : "上传"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </TabsContent>

        <TabsContent value="original">
          <ShellSection id={ORIGINAL_FILE_SECTION_ID}>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <RequirementFileSwitcher
                files={overview.files}
                onSelect={setSelectedFileId}
                selectedFileId={selectedFile?.id ?? ""}
              />
              <Button disabled={!originalPreview} onClick={downloadOriginalPreview} type="button" variant="outline">
                <Download className="size-4" />
                下载文件
              </Button>
            </div>
            <OriginalFilePreview preview={originalPreview} selectedFilename={selectedFile?.original_filename} />
          </ShellSection>
        </TabsContent>

        <TabsContent value="standard">
          <ShellSection id={STANDARD_FILE_SECTION_ID}>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <RequirementFileSwitcher
                  files={overview.files}
                  getFileLabel={standardMarkdownFilename}
                  onSelect={setSelectedFileId}
                  selectedFileId={selectedFile?.id ?? ""}
                />
              </div>
              <div className="flex flex-wrap items-center justify-end gap-2">
                {editingStandard ? (
                  <>
                    <Button disabled={savingStandard} onClick={saveStandardMarkdown} type="button">
                      <Save className="size-4" />
                      {savingStandard ? "保存中" : "保存"}
                    </Button>
                    <Button
                      disabled={savingStandard}
                      onClick={() => {
                        setMarkdownDraft(currentStandardPreview?.markdownContent ?? "");
                        setEditingStandard(false);
                      }}
                      type="button"
                      variant="outline"
                    >
                      <X className="size-4" />
                      取消
                    </Button>
                  </>
                ) : (
                  <>
                    <AiEditInput
                      disabled={!canEditStandard || editingStandardWithAi}
                      loading={editingStandardWithAi}
                      onSubmit={editStandardMarkdownWithAi}
                      placeholder="描述你希望如何修改当前标准文件..."
                    />
                    <Button
                      disabled={!canEditStandard}
                      onClick={() => setEditingStandard(true)}
                      type="button"
                      variant="outline"
                    >
                      <Pencil className="size-4" />
                      修改
                    </Button>
                    <Button
                      disabled={merging || overview.stats.mergeable_files === 0}
                      onClick={mergeRequirement}
                      type="button"
                    >
                      <GitMerge className="size-4" />
                      {merging ? "合并中" : "合并全部文件"}
                    </Button>
                  </>
                )}
              </div>
            </div>
            {selectedStandardGenerating ? (
              <StandardFileState description="该原始文件正在转换为 Markdown 标准文件，转换完成后会在这里展示。" />
            ) : standardLoading ? (
              <StandardFileState
                description="系统正在生成该原始文件对应的 Markdown 标准文件，请稍后刷新。"
                title="标准文件生成中"
              />
            ) : standardError ? (
              <StandardFileState description={standardError} tone="failed" title="标准文件生成失败" />
            ) : editingStandard ? (
              <StandardMarkdownEditor content={markdownDraft} onChange={setMarkdownDraft} />
            ) : (
              <MarkdownPreview
                className="requirement-document-preview"
                content={currentStandardPreview?.markdownContent ?? ""}
                emptyText="当前文件暂无可展示的标准 Markdown。"
              />
            )}
          </ShellSection>
        </TabsContent>

        <TabsContent value="initial">
          <ShellSection id={INITIAL_REQUIREMENT_SECTION_ID}>
            {outdatedMergeBanner}
            {merging ? (
              <div className="flex min-h-[220px] items-center justify-center text-center text-muted-foreground text-sm">
                正在合并需求中，完成后会展示合并需求稿。
              </div>
            ) : initialArtifactTabs.length && !editingInitial ? (
              <Tabs className="space-y-4" onValueChange={setMergeArtifactTab} value={mergeArtifactTab}>
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <TabsList className="h-auto min-h-10 max-w-full overflow-x-auto overflow-y-hidden">
                    <TabsTrigger className="h-8 whitespace-nowrap" value={MERGED_REQUIREMENT_TAB_KEY}>
                      合并需求稿
                    </TabsTrigger>
                    {initialArtifactTabs.map((artifact) => (
                      <TabsTrigger className="h-8 whitespace-nowrap" key={artifact.key} value={artifact.key}>
                        {artifact.label}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <Button
                      disabled={!displayInitialMarkdownContent.trim()}
                      onClick={() => {
                        setInitialMarkdownDraft(displayInitialMarkdownContent);
                        setEditingInitial(true);
                      }}
                      type="button"
                      variant="outline"
                    >
                      <Pencil className="size-4" />
                      编辑
                    </Button>
                    <Button
                      disabled={!displayInitialMarkdownContent.trim()}
                      onClick={runRequirementAnalysis}
                      type="button"
                      variant="outline"
                    >
                      {analysisLoading ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <FileSearch className="size-4" />
                      )}
                      {analysisLoading ? "分析中" : "需求分析"}
                    </Button>
                  </div>
                </div>
                <TabsContent value={MERGED_REQUIREMENT_TAB_KEY}>
                  <MarkdownPreview
                    className="requirement-document-preview"
                    content={displayInitialMarkdownContent}
                    emptyText={
                      merging
                        ? "正在合并需求中，完成后会展示合并需求稿。"
                        : "尚未生成初始需求，请先在标准文件中发起合并。"
                    }
                  />
                </TabsContent>
                {initialArtifactTabs.map((artifact) => (
                  <TabsContent key={artifact.key} value={artifact.key}>
                    <MarkdownPreview
                      className="requirement-artifact-preview"
                      content={artifact.content}
                      emptyText="该归并产物暂无内容。"
                    />
                  </TabsContent>
                ))}
              </Tabs>
            ) : (
              <>
                <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
                  {editingInitial ? (
                    <>
                      <Button disabled={savingInitial} onClick={saveInitialRequirement} type="button">
                        {savingInitial ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
                        {savingInitial ? "保存中" : "保存"}
                      </Button>
                      <Button
                        disabled={savingInitial}
                        onClick={() => {
                          setInitialMarkdownDraft(displayInitialMarkdownContent);
                          setEditingInitial(false);
                        }}
                        type="button"
                        variant="outline"
                      >
                        <X className="size-4" />
                        取消
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button
                        disabled={!displayInitialMarkdownContent.trim()}
                        onClick={() => {
                          setInitialMarkdownDraft(displayInitialMarkdownContent);
                          setEditingInitial(true);
                        }}
                        type="button"
                        variant="outline"
                      >
                        <Pencil className="size-4" />
                        编辑
                      </Button>
                      <Button
                        disabled={!displayInitialMarkdownContent.trim()}
                        onClick={runRequirementAnalysis}
                        type="button"
                        variant="outline"
                      >
                        {analysisLoading ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <FileSearch className="size-4" />
                        )}
                        {analysisLoading ? "分析中" : "需求分析"}
                      </Button>
                    </>
                  )}
                </div>
                {editingInitial ? (
                  <Textarea
                    className="min-h-[560px] font-mono text-sm"
                    onChange={(event) => setInitialMarkdownDraft(event.target.value)}
                    value={initialMarkdownDraft}
                  />
                ) : (
                  <MarkdownPreview
                    className="requirement-document-preview"
                    content={displayInitialMarkdownContent}
                    emptyClassName="flex items-center justify-center text-center"
                    emptyText={
                      merging
                        ? "正在合并需求中，完成后会展示合并需求稿。"
                        : "尚未生成初始需求，请先在标准文件中发起合并。"
                    }
                  />
                )}
              </>
            )}
          </ShellSection>
        </TabsContent>

        <TabsContent value="clarification">
          <ShellSection>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-medium text-sm">需求澄清</h2>
                <p className="mt-1 text-muted-foreground text-xs">集中处理需求分析识别出的待澄清问题。</p>
              </div>
              <Button
                disabled={!overview.initial_markdown_content.trim()}
                onClick={runRequirementAnalysis}
                type="button"
                variant="outline"
              >
                {analysisLoading ? <Loader2 className="size-4 animate-spin" /> : <FileSearch className="size-4" />}
                {analysisLoading ? "分析中" : "需求分析"}
              </Button>
            </div>
            {analysisResult?.output.clarification_questions.length ? (
              <div className="space-y-3">
                {analysisResult.output.clarification_questions.map((question) => (
                  <div className="rounded-lg border bg-background p-4" key={question.id}>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={question.severity === "blocker" ? "destructive" : "secondary"}>
                        {question.severity}
                      </Badge>
                      <span className="font-medium text-sm">{question.module_name}</span>
                    </div>
                    <div className="mt-3 text-sm">{question.question}</div>
                    <div className="mt-2 text-muted-foreground text-xs">{question.reason}</div>
                    {question.impact ? (
                      <div className="mt-2 text-muted-foreground text-xs">影响：{question.impact}</div>
                    ) : null}
                    {question.source_excerpt ? (
                      <div className="mt-3 rounded-md bg-muted/40 p-3 text-xs">{question.source_excerpt}</div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex min-h-[280px] items-center justify-center rounded-lg border bg-muted/20 text-center text-muted-foreground text-sm">
                {analysisResult ? "暂无待澄清问题。" : "尚未执行需求分析，生成分析结果后会在这里展示澄清问题。"}
              </div>
            )}
          </ShellSection>
        </TabsContent>

        <TabsContent value="final">
          <ShellSection id={FINAL_REQUIREMENT_SECTION_ID}>
            <div className="mb-3">
              <div>
                <h2 className="font-medium text-sm">最终需求</h2>
                <p className="mt-1 text-muted-foreground text-xs">当前已生效的需求版本内容。</p>
              </div>
            </div>
            <MarkdownPreview
              className="requirement-document-preview"
              content={overview.initial_markdown_content}
              emptyClassName="flex items-center justify-center text-center"
              emptyText="尚未生成最终需求，请先完成标准文件合并。"
            />
            <div className="mt-6 rounded-lg border bg-muted/20 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-medium text-sm">最近一次需求分析</h3>
                  <p className="mt-1 text-muted-foreground text-xs">
                    {analysisResult
                      ? `状态：${analysisResult.status} · 可测试性：${analysisResult.testability_score}`
                      : "尚未执行需求分析。"}
                  </p>
                </div>
                <Button
                  disabled={!overview.initial_markdown_content.trim()}
                  onClick={runRequirementAnalysis}
                  type="button"
                  variant="outline"
                >
                  {analysisLoading ? <Loader2 className="size-4 animate-spin" /> : <FileSearch className="size-4" />}
                  {analysisLoading ? "分析中" : "重新分析"}
                </Button>
              </div>
              {analysisResult ? (
                <div className="mt-4 space-y-4">
                  <div className="text-sm">{analysisResult.analysis_summary}</div>
                  {analysisResult.output.quality_gate.blocking_issues.length ? (
                    <div className="space-y-2">
                      <div className="font-medium text-xs">阻塞项</div>
                      <ul className="list-disc space-y-1 pl-5 text-sm">
                        {analysisResult.output.quality_gate.blocking_issues.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </ShellSection>
        </TabsContent>

        {showConflictTab ? (
          <TabsContent value="conflicts">
            <div className="space-y-4">
              {conflicts.map((conflict) => (
                <ShellSection key={conflict.id}>
                  <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="font-medium text-sm">{conflict.title}</h2>
                      <p className="text-muted-foreground text-xs">来源：{conflict.source_file_names}</p>
                    </div>
                    <Badge variant="outline">待处理</Badge>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <pre className="whitespace-pre-wrap rounded-lg border bg-muted/30 p-3 text-sm">
                      {conflict.fragment_a}
                    </pre>
                    <pre className="whitespace-pre-wrap rounded-lg border bg-muted/30 p-3 text-sm">
                      {conflict.fragment_b}
                    </pre>
                  </div>
                  <div className="mt-4 grid gap-2">
                    <Textarea
                      className="min-h-28"
                      onChange={(event) =>
                        setConflictDrafts((current) => ({ ...current, [conflict.id]: event.target.value }))
                      }
                      value={conflictDrafts[conflict.id] ?? ""}
                    />
                    <div className="flex justify-end">
                      <Button onClick={() => saveConflictResolution(conflict)} type="button">
                        <Check className="size-4" />
                        保存解决结果
                      </Button>
                    </div>
                  </div>
                </ShellSection>
              ))}
              {conflicts.length === 0 ? (
                <ShellSection>
                  <div className="text-muted-foreground text-sm">暂无待处理冲突。</div>
                </ShellSection>
              ) : null}
            </div>
          </TabsContent>
        ) : null}
      </Tabs>
    </PageShell>
  );
}

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <ShellSection>
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="mt-2 font-semibold text-2xl tabular-nums">{value}</div>
    </ShellSection>
  );
}

function StatusBadge({
  loading = false,
  status,
  statusLabels,
}: {
  loading?: boolean;
  status: string;
  statusLabels: Record<string, string>;
}) {
  return (
    <Badge className="gap-1.5" variant={status === "failed" ? "destructive" : "secondary"}>
      {loading ? <Loader2 className="size-3 animate-spin" /> : null}
      {statusLabels[status] ?? status}
    </Badge>
  );
}

function StandardFileState({
  description,
  title,
  tone = "generating",
}: {
  description: string;
  title?: string;
  tone?: "generating" | "failed";
}) {
  return (
    <div className="rounded-lg border bg-muted/20 p-6 text-sm">
      {tone === "generating" ? (
        <div className="flex min-h-40 items-center justify-center px-4 text-center">
          <div className="whitespace-nowrap text-muted-foreground text-sm">{title ?? description}</div>
        </div>
      ) : (
        <>
          <div className={tone === "failed" ? "font-medium text-destructive" : "font-medium"}>{title}</div>
          <div className="mt-2 text-muted-foreground">{description}</div>
        </>
      )}
    </div>
  );
}

function displayFilename(filename: string) {
  return filename.split(/[\\/]/).filter(Boolean).pop() ?? filename;
}

function standardMarkdownFilename(filename: string) {
  const displayName = displayFilename(filename);
  return `${displayName.replace(/\.[^.]+$/, "")}.md`;
}
