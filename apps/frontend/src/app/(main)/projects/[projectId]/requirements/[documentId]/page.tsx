"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useParams, useRouter, useSearchParams } from "next/navigation";

import {
  ArrowLeft,
  Check,
  Download,
  Eye,
  FileSearch,
  FileText,
  History,
  Loader2,
  Pencil,
  RotateCcw,
  Save,
  SkipForward,
  Square,
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
import {
  isFinalRequirementVersion,
  type RequirementVersionDetail,
  RequirementVersionDetailContent,
  requirementVersionActionLabel,
  requirementVersionSummary,
} from "@/components/ai-testing/requirement-version-detail-content";
import { StandardMarkdownEditor } from "@/components/ai-testing/standard-markdown-editor";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { AiEditInput } from "@/components/ui/ai-input";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { BadgeDot, Badge as RequirementRoleBadge } from "@/components/ui/badge-2";
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
import {
  ApiRequestError,
  type ApiTaskItem,
  apiBlobRequest,
  apiErrorFromXhr,
  apiRequest,
  formatDateTime,
} from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";

const STANDARD_FILE_SECTION_ID = "standard-file-section";
const ORIGINAL_FILE_SECTION_ID = "original-file-section";
const FINAL_REQUIREMENT_SECTION_ID = "final-requirement-section";
const REQUIREMENT_DOCUMENT_TOC_SELECTOR =
  '[data-state="active"] .requirement-document-preview h1, [data-state="active"] .requirement-document-preview h2, [data-state="active"] .requirement-document-preview h3, [data-state="active"] .requirement-document-preview h4, [data-state="active"] .requirement-document-preview [data-toc]';
const REQUIREMENT_REVIEW_ACTIVE_STATUSES = new Set(["queued", "running", "stopping"]);
const REQUIREMENT_REVIEW_POLL_INTERVAL_MS = 2000;
const REQUIREMENT_REVIEW_MAX_POLLS = 90;
const pendingSeverityLabels: Record<"blocker" | "major" | "minor", string> = {
  blocker: "阻塞",
  major: "重要",
  minor: "一般",
};
const pendingIssueTypeLabels: Record<RequirementAnalysisIssueType, string> = {
  missing: "缺失",
  confirmation: "待确认",
  conflict: "冲突",
  ambiguous: "模糊",
};

function optionBadge(index: number) {
  return String.fromCharCode(65 + index);
}

function pendingItemNumber(index: number) {
  return index >= 0 ? String(index + 1).padStart(2, "0") : "--";
}

function normalizePendingQuestionText(question: string) {
  return question
    .replace(/^缺少功能[：:]\s*/, "")
    .replace(/^缺少非功能需求[：:]\s*/, "")
    .replace(/^以下细节需要确认[：:]\s*/, "")
    .replace(/^缺失细节[：:]\s*/, "")
    .replace(/^缺失说明[：:]\s*/, "")
    .replace(/^当前缺口[：:]\s*/, "")
    .replace(/^请确认测试覆盖缺口[：:]\s*/, "")
    .replace(/^请确认[“"](.+?)[”"]的验收标准。?$/, "$1")
    .trim();
}

function pendingIssueType(item: RequirementAnalysisPendingItem): RequirementAnalysisIssueType {
  return item.issue_type === "missing" ||
    item.issue_type === "confirmation" ||
    item.issue_type === "conflict" ||
    item.issue_type === "ambiguous"
    ? item.issue_type
    : "confirmation";
}

function pendingItemTitle(item: RequirementAnalysisPendingItem) {
  const issueType = pendingIssueType(item);
  const title = item.title?.trim();
  const genericTitles = new Set(["缺失功能", "缺失非功能需求", "待确认细节", "模糊表述", "歧义表述"]);
  if (title && !genericTitles.has(title)) {
    return title;
  }
  const questionTitle = item.question ? normalizePendingQuestionText(item.question) : "";
  if (questionTitle) {
    return questionTitle;
  }
  if (title) {
    return title;
  }
  const moduleName = item.module_name?.trim();
  if (moduleName) {
    return moduleName;
  }
  return pendingIssueTypeLabels[issueType] ?? "待确认项";
}

function pendingItemHeading(item: RequirementAnalysisPendingItem) {
  const title = pendingItemTitle(item);
  const questionText = item.question ? normalizePendingQuestionText(item.question) : "";
  return questionText && questionText !== title ? `${title}：${questionText}` : title;
}

function pendingItemSourceExcerpt(item: RequirementAnalysisPendingItem) {
  if ("primary_excerpt" in item && item.primary_excerpt?.trim()) {
    return item.primary_excerpt.trim();
  }
  return item.source_excerpt?.trim() ?? "";
}

function pendingRecommendedOptions(item: RequirementAnalysisPendingItem): RequirementClarificationOption[] {
  if (item.decision_options?.length) {
    return item.decision_options;
  }
  if (item.recommended_options?.length) {
    return item.recommended_options;
  }
  return [];
}

function pendingItemAnswerStatus(item: RequirementAnalysisPendingItem) {
  return item.answer?.apply_status ?? "";
}

function isPendingItemOpen(item: RequirementAnalysisPendingItem) {
  return !["applied", "not_applicable"].includes(pendingItemAnswerStatus(item));
}

function isPendingItemHandled(item: RequirementAnalysisPendingItem) {
  return ["applied", "not_applicable"].includes(pendingItemAnswerStatus(item));
}

function handledPendingItemLabel(item: RequirementAnalysisPendingItem) {
  return item.answer?.apply_status === "not_applicable" ? "暂不处理" : "已写入";
}

function extractMarkdownSection(content: string, heading: string) {
  const markdown = content.trim();
  if (!markdown) {
    return "";
  }
  const escapedHeading = heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const startPattern = new RegExp(`^##\\s+\\d*\\.?\\s*${escapedHeading}\\s*$`, "m");
  const startMatch = markdown.match(startPattern);
  if (!startMatch || startMatch.index === undefined) {
    return "";
  }
  const sectionStart = startMatch.index;
  const afterHeadingIndex = sectionStart + startMatch[0].length;
  const nextSectionMatch = markdown.slice(afterHeadingIndex).match(/^---$|^##\s+/m);
  const sectionEnd =
    nextSectionMatch?.index === undefined ? markdown.length : afterHeadingIndex + nextSectionMatch.index;
  return markdown.slice(sectionStart, sectionEnd).trim();
}

function latestRequirementAnalysisRunFromTask(
  task: ApiTaskItem,
): RequirementOverviewResponse["document"]["latest_requirement_analysis_run"] {
  return {
    id: task.source_id,
    status: task.status,
    summary: task.summary,
    failure_reason: "",
    created_at: task.created_at,
    updated_at: task.updated_at,
  };
}

type SourceFile = RequirementSwitcherFile & {
  version_id: string | null;
  version_no: number | null;
  markdown_file_path: string | null;
  conversion_summary: string;
  file_role: "primary" | "supporting";
  standard_file_status?: "generating" | "ready" | "edited" | "failed";
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
    latest_requirement_analysis_run: {
      id: string;
      status: string;
      summary: string;
      failure_reason: string;
      created_at: string;
      updated_at: string;
    } | null;
  };
  stats: {
    total_files: number;
    conversion_success: number;
    conversion_warning: number;
    conversion_failed: number;
    primary_files: number;
    initial_requirement_status: string;
  };
  files: SourceFile[];
  initial_markdown_content: string;
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

type RequirementAnalysisQuestion = {
  id: string;
  title?: string;
  issue_type?: RequirementAnalysisIssueType;
  module_key: string;
  module_name: string;
  question: string;
  impact: string;
  dimension: string;
  severity: "blocker" | "major" | "minor";
  source_excerpt: string;
  clarification_bucket?: "blocker" | "risk" | "acceptance";
  decision_point?: string;
  current_gap?: string;
  test_impact?: string;
  risk_scenario?: string;
  affected_surfaces?: string[];
  decision_options?: RequirementClarificationOption[];
  recommended_decision?: string;
  human_question?: string;
  draft_acceptance_tests?: string[];
  recommended_options?: RequirementClarificationOption[];
  answer?: RequirementClarificationAnswer;
};

type RequirementAnalysisConflict = {
  id: string;
  title?: string;
  module_key: string;
  module_name: string;
  issue_type: RequirementAnalysisIssueType | string;
  question: string;
  impact: string;
  severity: "blocker" | "major" | "minor";
  primary_excerpt: string;
  source_excerpt?: string;
  clarification_bucket?: "blocker" | "risk" | "acceptance";
  decision_point?: string;
  current_gap?: string;
  test_impact?: string;
  risk_scenario?: string;
  affected_surfaces?: string[];
  decision_options?: RequirementClarificationOption[];
  recommended_decision?: string;
  human_question?: string;
  draft_acceptance_tests?: string[];
  evidence?: Array<{
    mapping_id: string;
    filename: string;
    excerpt: string;
    section_hint: string;
  }>;
  recommended_options?: RequirementClarificationOption[];
  answer?: RequirementClarificationAnswer;
};

type RequirementAnalysisIssueType = "missing" | "confirmation" | "conflict" | "ambiguous";

type RequirementAnalysisPendingItem = RequirementAnalysisQuestion | RequirementAnalysisConflict;

type RequirementClarificationOption = {
  id: string;
  label: string;
  answer_markdown: string;
  rationale?: string;
  confidence?: "high" | "medium" | "low";
};

type RequirementClarificationAnswer = {
  id: string;
  question_id: string;
  answer_type: "recommended_option" | "custom" | "defer";
  selected_option_id: string;
  answer_markdown: string;
  user_note: string;
  apply_status: "not_applicable" | "applied" | "failed";
  insertion_anchor: string;
  failure_reason: string;
  created_at?: string;
  updated_at?: string;
};

type PendingAnswerDraft = {
  selectedOptionId: string;
  customAnswer: string;
  answerType: "recommended_option" | "custom" | "defer";
};

type RequirementAnalysisResult = {
  id: string;
  project_id: string;
  document_id: string;
  version_id: string | null;
  primary_mapping_id: string | null;
  status: "completed" | "needs_clarification" | "blocked";
  analysis_summary: string;
  quality_result: "passed" | "warning" | "blocked";
  testability_score: number;
  draft_content_hash: string;
  finalized_version_id: string | null;
  finalized_at: string | null;
  finalized_by: string | null;
  created_by: string;
  created_at: string;
  output: {
    status: "completed" | "needs_clarification" | "blocked";
    analysis_summary: string;
    preliminary_requirement_markdown: string;
    analysis_report_markdown: string;
    clarification_report_markdown?: string;
    quality_assurance_report_markdown?: string;
    enhanced_requirement_markdown?: string;
    applied_supplements: unknown[];
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
    conflicts: RequirementAnalysisConflict[];
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

type RequirementAnalysisResponse = {
  analysis: RequirementAnalysisResult | null;
};

type RequirementAnalysisFinalizeResponse = {
  analysis: RequirementAnalysisResult;
  version: {
    id: string;
    document_id: string;
    version_no: number;
    source_action: string;
    change_summary: string;
    created_by: string;
    created_at: string;
  };
  document: {
    id: string;
    current_version_id: string | null;
  };
  markdown_content: string;
};

type RequirementVersion = RequirementVersionDetail;

type RequirementClarificationAnswerResponse = {
  answer: RequirementClarificationAnswer;
  analysis: RequirementAnalysisResult;
};

type RequirementProgressStepStatus = "completed" | "running" | "upcoming";

type RequirementProgressStep = {
  id: string;
  title: string;
  status: RequirementProgressStepStatus;
};

const conversionLabels: Record<string, string> = {
  pending: "待转换",
  processing: "转换中",
  success: "转换成功",
  warning: "有警告",
  failed: "转换失败",
};

const fileRoleLabels: Record<string, string> = {
  primary: "主需求",
  supporting: "辅助文件",
};

function defaultRequirementFileId(files: SourceFile[]) {
  return files.find((file) => file.file_role === "primary")?.id ?? files[0]?.id ?? "";
}

export default function DocumentDetailPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const params = useParams<{ projectId: string; documentId: string }>();
  const { projectId, documentId } = params;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [overview, setOverview] = useState<RequirementOverviewResponse | null>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [analysisTab, setAnalysisTab] = useState("analysis-report");
  const [selectedFileId, setSelectedFileId] = useState("");
  const [originalPreview, setOriginalPreview] = useState<OriginalPreview | null>(null);
  const [standardPreview, setStandardPreview] = useState<StandardPreview | null>(null);
  const [standardLoading, setStandardLoading] = useState(false);
  const [standardError, setStandardError] = useState("");
  const [markdownDraft, setMarkdownDraft] = useState("");
  const [editingStandard, setEditingStandard] = useState(false);
  const [savingStandard, setSavingStandard] = useState(false);
  const [editingStandardWithAi, setEditingStandardWithAi] = useState(false);
  const [settingPrimaryFileId, setSettingPrimaryFileId] = useState("");
  const [analysisResult, setAnalysisResult] = useState<RequirementAnalysisResult | null>(null);
  const [requirementVersions, setRequirementVersions] = useState<RequirementVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [versionsError, setVersionsError] = useState("");
  const [selectedRequirementVersion, setSelectedRequirementVersion] = useState<RequirementVersion | null>(null);
  const [selectedRequirementVersionLoading, setSelectedRequirementVersionLoading] = useState(false);
  const [switchingRequirementVersionId, setSwitchingRequirementVersionId] = useState("");
  const [reviewLoading, setReviewLoading] = useState(false);
  const [activeReviewRunId, setActiveReviewRunId] = useState("");
  const [stoppingReview, setStoppingReview] = useState(false);
  const [reviewStopConfirmOpen, setReviewStopConfirmOpen] = useState(false);
  const [finalizingRequirement, setFinalizingRequirement] = useState(false);
  const [savingClarificationId, setSavingClarificationId] = useState("");
  const [pendingAnswerDrafts, setPendingAnswerDrafts] = useState<Record<string, PendingAnswerDraft>>({});
  const [sourceExcerptItem, setSourceExcerptItem] = useState<RequirementAnalysisPendingItem | null>(null);
  const [handledClarificationDialogOpen, setHandledClarificationDialogOpen] = useState(false);
  const [handledClarificationFilter, setHandledClarificationFilter] = useState<"all" | "applied" | "not_applicable">(
    "all",
  );
  const [activeRestoredPendingItemId, setActiveRestoredPendingItemId] = useState("");
  const [finalizeConfirmOpen, setFinalizeConfirmOpen] = useState(false);
  const [reviewClearConfirmOpen, setReviewClearConfirmOpen] = useState(false);
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
    () =>
      overview?.files.find((file) => file.id === selectedFileId) ??
      overview?.files.find((file) => file.file_role === "primary") ??
      overview?.files[0] ??
      null,
    [overview?.files, selectedFileId],
  );
  const selectedFileRef = useRef<SourceFile | null>(null);
  const filteredFiles = useMemo(
    () =>
      fileRows.filter((file) =>
        [file.original_filename, file.file_format, file.conversion_status, file.file_role].some((value) =>
          value?.toLowerCase().includes(fileSearchText.trim().toLowerCase()),
        ),
      ),
    [fileRows, fileSearchText],
  );
  const currentStandardPreview = standardPreview?.fileId === selectedFile?.id ? standardPreview : null;
  const currentPrimaryFile = useMemo(
    () => overview?.files.find((file) => file.file_role === "primary") ?? null,
    [overview?.files],
  );
  const canEditStandard = Boolean(currentStandardPreview) && !standardLoading && standardError.length === 0;
  const selectedStandardGenerating = Boolean(
    selectedFile &&
      (selectedFile.standard_file_status === "generating" ||
        ["pending", "processing"].includes(selectedFile.conversion_status)),
  );
  const initialMarkdownContent = overview?.initial_markdown_content ?? "";
  const preliminaryMarkdown = analysisResult?.output.preliminary_requirement_markdown ?? "";
  const analysisReportMarkdown = analysisResult?.output.analysis_report_markdown ?? "";
  const qualityAssuranceMarkdown =
    analysisResult?.output.quality_assurance_report_markdown?.trim() ||
    extractMarkdownSection(analysisReportMarkdown, "质量评估");
  const clarificationQuestions = analysisResult?.output.clarification_questions ?? [];
  const analysisConflicts = analysisResult?.output.conflicts ?? [];
  const pendingAnalysisItems: RequirementAnalysisPendingItem[] = [...clarificationQuestions, ...analysisConflicts];
  const visiblePendingAnalysisItems = pendingAnalysisItems.filter(isPendingItemOpen);
  const handledPendingAnalysisItems = pendingAnalysisItems.filter(
    (item) => isPendingItemHandled(item) && !pendingAnswerDrafts[item.id],
  );
  const appliedPendingAnalysisCount = handledPendingAnalysisItems.filter(
    (item) => item.answer?.apply_status === "applied",
  ).length;
  const deferredPendingAnalysisCount = handledPendingAnalysisItems.filter(
    (item) => item.answer?.apply_status === "not_applicable",
  ).length;
  const filteredHandledPendingAnalysisItems = handledPendingAnalysisItems.filter((item) =>
    handledClarificationFilter === "all" ? true : item.answer?.apply_status === handledClarificationFilter,
  );
  const isBlocked =
    analysisResult?.status === "blocked" ||
    analysisResult?.quality_result === "blocked" ||
    analysisResult?.output.quality_gate.result === "blocked";
  const isFinalized = Boolean(analysisResult?.finalized_version_id);
  const isPrimaryAnalysisChanged = Boolean(
    analysisResult?.primary_mapping_id && analysisResult.primary_mapping_id !== currentPrimaryFile?.id,
  );
  const finalizeDisabledReason = (() => {
    if (reviewLoading) {
      return "需求分析中";
    }
    if (!analysisResult) {
      return "尚未生成初步需求";
    }
    if (!preliminaryMarkdown.trim()) {
      return "初步需求为空";
    }
    if (isFinalized) {
      return "已转为最终需求";
    }
    if (isBlocked) {
      return "存在阻塞问题，不能转为最终需求";
    }
    if (isPrimaryAnalysisChanged) {
      return "主需求已变更，请重新分析";
    }
    return "";
  })();
  const hasRunningConversions = Boolean(
    overview?.files.some((file) => ["pending", "processing"].includes(file.conversion_status)),
  );
  const hasFinalRequirementContent = Boolean(initialMarkdownContent.trim());
  const hasStandardRequirement = Boolean(
    overview && overview.stats.conversion_success + overview.stats.conversion_warning > 0,
  );
  const latestRequirementAnalysisRunStatus = overview?.document.latest_requirement_analysis_run?.status ?? "";
  const latestRequirementAnalysisRunId = overview?.document.latest_requirement_analysis_run?.id ?? "";
  const requirementReviewRunning =
    reviewLoading ||
    REQUIREMENT_REVIEW_ACTIVE_STATUSES.has(latestRequirementAnalysisRunStatus) ||
    Boolean(overview?.document.status === "pending_review" && !analysisResult && !latestRequirementAnalysisRunStatus);
  const requirementReviewRunningRef = useRef(false);
  const requirementAnalysisDisabledReason = (() => {
    if (!currentPrimaryFile) {
      return "请先设置主需求文件";
    }
    if (!["success", "warning"].includes(currentPrimaryFile.conversion_status)) {
      return "主需求标准文件未生成";
    }
    return "";
  })();
  const requirementReviewPassed = Boolean(
    analysisResult?.status && ["completed", "needs_clarification"].includes(analysisResult.status) && !isBlocked,
  );
  const canFinalizeRequirement = Boolean(requirementReviewPassed && !finalizeDisabledReason);
  const requirementProgressSteps: RequirementProgressStep[] = [
    {
      id: "raw",
      title: "原始需求",
      status: uploadSubmitting ? "running" : overview?.stats.total_files ? "completed" : "upcoming",
    },
    {
      id: "standard",
      title: "标准需求",
      status: hasRunningConversions ? "running" : hasStandardRequirement ? "completed" : "upcoming",
    },
    {
      id: "review",
      title: "需求分析",
      status: requirementReviewRunning ? "running" : requirementReviewPassed ? "completed" : "upcoming",
    },
    {
      id: "final",
      title: "最终需求",
      status: finalizingRequirement ? "running" : isFinalized && hasFinalRequirementContent ? "completed" : "upcoming",
    },
  ];
  const analysisReportEmptyText = reviewLoading
    ? "需求分析中，分析完成后会在这里展示需求分析报告。"
    : "尚未生成需求分析报告，请先执行需求分析。";
  const finalRequirementEmptyText = reviewLoading
    ? "需求分析中，当前最终需求已清空，分析完成并转为最终需求后会在这里展示。"
    : "尚未生成最终需求，请先在初步需求中点击“转为最终需求”。";
  const finalRequirementVersions = useMemo(
    () => requirementVersions.filter(isFinalRequirementVersion),
    [requirementVersions],
  );
  const currentRequirementVersion = useMemo(
    () => finalRequirementVersions.find((version) => version.id === overview?.document.current_version_id) ?? null,
    [finalRequirementVersions, overview?.document.current_version_id],
  );
  const currentRequirementVersionText = overview?.document.current_version_id
    ? currentRequirementVersion
      ? `当前生效版本 v${currentRequirementVersion.version_no}`
      : "当前最终需求版本已生成"
    : "当前没有生效最终需求";
  const selectedFileEffectKey = selectedFile
    ? [selectedFile.id, selectedFile.conversion_status, selectedFile.standard_file_status].join(":")
    : "";
  const loadOverview = useCallback(
    async ({ silent = false }: { silent?: boolean } = {}) => {
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
        setSelectedFileId((current) =>
          current && data.files.some((file) => file.id === current) ? current : defaultRequirementFileId(data.files),
        );
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
    [documentId, projectId, setFileRows],
  );

  const loadLatestAnalysis = useCallback(async () => {
    try {
      const data = await apiRequest<RequirementAnalysisResponse>(
        `/projects/${projectId}/requirements/${documentId}/analysis`,
      );
      setAnalysisResult(data.analysis);
      return data.analysis;
    } catch (_requestError) {
      setAnalysisResult(null);
      return null;
    }
  }, [documentId, projectId]);

  const loadRequirementVersions = useCallback(
    async ({ silent = false }: { silent?: boolean } = {}) => {
      if (!silent) {
        setVersionsLoading(true);
      }
      setVersionsError("");
      try {
        const data = await apiRequest<RequirementVersion[]>(
          `/projects/${projectId}/requirements/${documentId}/versions`,
        );
        setRequirementVersions(data);
        return data;
      } catch (requestError) {
        setVersionsError(requestError instanceof Error ? requestError.message : "版本记录加载失败");
        return [];
      } finally {
        if (!silent) {
          setVersionsLoading(false);
        }
      }
    },
    [documentId, projectId],
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
      reportError(requestError, {
        fallbackMessage: "原始文件预览失败",
        actionLabel: "预览原始文件",
        method: "GET",
        path: `/requirement-files/${file.id}/original`,
      });
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
      reportError(requestError, {
        fallbackMessage: "标准文件加载失败",
        actionLabel: "加载标准文件",
        method: "GET",
        path: `/requirement-files/${file.id}/markdown`,
      });
    } finally {
      setStandardLoading(false);
    }
  }, []);

  useEffect(() => {
    const queryTab = searchParams.get("tab");
    if (queryTab === "initial") {
      setActiveTab("analysis");
      setAnalysisTab("analysis-report");
    } else if (queryTab === "clarification") {
      setActiveTab("analysis");
      setAnalysisTab("clarification");
    } else if (queryTab && ["overview", "original", "standard", "analysis", "final", "versions"].includes(queryTab)) {
      setActiveTab(queryTab);
    }
    void loadOverview();
    void loadLatestAnalysis();
    void loadRequirementVersions({ silent: true });
  }, [loadLatestAnalysis, loadOverview, loadRequirementVersions, searchParams]);

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

  useEffect(() => {
    if (requirementReviewRunningRef.current && !requirementReviewRunning && analysisResult) {
      setActiveTab("analysis");
      setAnalysisTab("analysis-report");
    }
    requirementReviewRunningRef.current = requirementReviewRunning;
  }, [analysisResult, requirementReviewRunning]);

  useEffect(() => {
    if (
      !latestRequirementAnalysisRunId ||
      !REQUIREMENT_REVIEW_ACTIVE_STATUSES.has(latestRequirementAnalysisRunStatus)
    ) {
      return;
    }

    let cancelled = false;
    const refreshRequirementAnalysis = async () => {
      const latestOverview = await loadOverview({ silent: true });
      if (cancelled) {
        return;
      }
      const latestRunStatus = latestOverview?.document.latest_requirement_analysis_run?.status ?? "";
      const latestAnalysis = await loadLatestAnalysis();
      if (cancelled) {
        return;
      }
      if (!REQUIREMENT_REVIEW_ACTIVE_STATUSES.has(latestRunStatus) && latestAnalysis) {
        setActiveTab("analysis");
        setAnalysisTab("analysis-report");
      }
    };

    const timer = window.setInterval(() => {
      void refreshRequirementAnalysis();
    }, REQUIREMENT_REVIEW_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [latestRequirementAnalysisRunId, latestRequirementAnalysisRunStatus, loadLatestAnalysis, loadOverview]);

  function handleDetailTabChange(nextTab: string) {
    setActiveTab(nextTab);
  }

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
      reportError(requestError, {
        fallbackMessage: "标准文件保存失败",
        actionLabel: "保存标准文件",
        method: "PUT",
        path: selectedFile ? `/requirement-files/${selectedFile.id}/markdown` : undefined,
      });
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
      reportError(requestError, {
        fallbackMessage: "智能修改失败",
        actionLabel: "AI 修改标准文件",
        method: "POST",
        path: "/agents/document-editor/run",
      });
    } finally {
      setEditingStandardWithAi(false);
    }
  }

  async function reviewPrimaryRequirement() {
    if (!currentPrimaryFile) {
      toast.error("请先设置主需求文件");
      return;
    }
    if (!["success", "warning"].includes(currentPrimaryFile.conversion_status)) {
      toast.error("主需求标准文件未生成");
      return;
    }
    setReviewClearConfirmOpen(true);
  }

  function clearRequirementAnalysisTabs() {
    setAnalysisResult(null);
    setFinalizeConfirmOpen(false);
    setReviewClearConfirmOpen(false);
    setOverview((current) =>
      current
        ? {
            ...current,
            document: {
              ...current.document,
              current_version_id: null,
            },
            stats: {
              ...current.stats,
              initial_requirement_status: "not_generated",
            },
            initial_markdown_content: "",
          }
        : current,
    );
  }

  async function submitRequirementAnalysis() {
    setReviewLoading(true);
    clearRequirementAnalysisTabs();
    let runId = "";
    try {
      const task = await apiRequest<ApiTaskItem>(`/projects/${projectId}/requirements/${documentId}/review`, {
        method: "POST",
      });
      runId = task.source_id;
      setActiveReviewRunId(runId);
      setOverview((current) =>
        current
          ? {
              ...current,
              document: {
                ...current.document,
                current_version_id: null,
                latest_requirement_analysis_run: latestRequirementAnalysisRunFromTask(task),
                status: "pending_review",
              },
              stats: {
                ...current.stats,
                initial_requirement_status: "not_generated",
              },
              initial_markdown_content: "",
            }
          : current,
      );
      notifyAiTaskStarted();
      toast.success("需求分析已提交，正在分析中");
      setActiveTab("analysis");
      setAnalysisTab("analysis-report");
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "需求分析提交失败",
        actionLabel: "提交需求分析",
        method: "POST",
        path: `/projects/${projectId}/requirements/${documentId}/review`,
      });
      setReviewLoading(false);
      await loadOverview({ silent: true });
      await loadLatestAnalysis();
      return;
    }

    try {
      await waitForRequirementReviewTask(runId);
      await loadOverview({ silent: true });
      const latestAnalysis = await loadLatestAnalysis();
      if (latestAnalysis) {
        setActiveTab("analysis");
        setAnalysisTab("analysis-report");
      }
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "需求分析状态同步失败",
        actionLabel: "同步需求分析状态",
        method: "GET",
        path: `/tasks?project_id=${projectId}&module=requirement&page_size=100`,
      });
    } finally {
      setReviewLoading(false);
      setActiveReviewRunId("");
    }
  }

  async function stopRequirementAnalysis() {
    const runId = activeReviewRunId || overview?.document.latest_requirement_analysis_run?.id || "";
    if (!runId) {
      toast.error("当前没有可停止的需求分析任务");
      return;
    }

    setStoppingReview(true);
    setReviewStopConfirmOpen(false);
    try {
      const stoppedTask = await apiRequest<ApiTaskItem>(
        `/projects/${projectId}/requirements/${documentId}/analysis-runs/${runId}/stop`,
        { method: "POST" },
      );
      if (stoppedTask.status === "cancelled") {
        toast.success("需求分析已停止");
      } else {
        toast.success("已请求停止需求分析");
        await waitForRequirementReviewTask(runId);
      }
      clearRequirementAnalysisTabs();
      await loadOverview({ silent: true });
      await loadLatestAnalysis();
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "停止需求分析失败",
        actionLabel: "停止需求分析",
        method: "POST",
        path: `/projects/${projectId}/requirements/${documentId}/analysis-runs/${runId}/stop`,
      });
    } finally {
      setStoppingReview(false);
      setReviewLoading(false);
      setActiveReviewRunId("");
    }
  }

  async function waitForRequirementReviewTask(runId: string) {
    for (let index = 0; index < REQUIREMENT_REVIEW_MAX_POLLS; index += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, REQUIREMENT_REVIEW_POLL_INTERVAL_MS));
      const params = new URLSearchParams({
        project_id: projectId,
        module: "requirement",
        page_size: "100",
      });
      const data = await apiRequest<{ items: ApiTaskItem[] }>(`/tasks?${params.toString()}`);
      const task = data.items.find(
        (item) => item.source_type === "requirement_analysis_run" && item.source_id === runId,
      );
      if (!task || !REQUIREMENT_REVIEW_ACTIVE_STATUSES.has(task.status)) {
        return;
      }
    }
  }

  async function finalizePreliminaryRequirement(confirmUnresolved = false) {
    if (!analysisResult) {
      toast.error("尚未生成初步需求");
      return;
    }
    setFinalizingRequirement(true);
    try {
      const result = await apiRequest<RequirementAnalysisFinalizeResponse>(
        `/projects/${projectId}/requirements/${documentId}/analysis/finalize`,
        {
          method: "POST",
          body: JSON.stringify({
            analysis_id: analysisResult.id,
            confirm_unresolved: confirmUnresolved,
          }),
        },
      );
      setAnalysisResult(result.analysis);
      setFinalizeConfirmOpen(false);
      toast.success("已转为最终需求");
      await loadOverview({ silent: true });
      await loadRequirementVersions({ silent: true });
      setActiveTab("final");
    } catch (requestError) {
      if (!confirmUnresolved && isConfirmRequired(requestError)) {
        setFinalizeConfirmOpen(true);
        return;
      }
      reportError(requestError, {
        fallbackMessage: "转为最终需求失败",
        actionLabel: "转为最终需求",
        method: "POST",
        path: `/projects/${projectId}/requirements/${documentId}/analysis/finalize`,
      });
    } finally {
      setFinalizingRequirement(false);
    }
  }

  async function openRequirementVersionDetail(version: RequirementVersion) {
    setSelectedRequirementVersion(version);
    setSelectedRequirementVersionLoading(true);
    try {
      const detail = await apiRequest<RequirementVersion>(
        `/projects/${projectId}/requirements/${documentId}/versions/${version.id}`,
      );
      setSelectedRequirementVersion(detail);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "版本详情加载失败",
        actionLabel: "查看需求版本",
        method: "GET",
        path: `/projects/${projectId}/requirements/${documentId}/versions/${version.id}`,
      });
      setSelectedRequirementVersion(null);
    } finally {
      setSelectedRequirementVersionLoading(false);
    }
  }

  async function switchRequirementVersion(version: RequirementVersion) {
    setSwitchingRequirementVersionId(version.id);
    try {
      await apiRequest(`/projects/${projectId}/requirements/${documentId}/versions/${version.id}/current`, {
        method: "PUT",
      });
      toast.success(`已切换为 v${version.version_no}`);
      setSelectedRequirementVersion((current) => (current ? { ...current, is_current: true } : current));
      await loadOverview({ silent: true });
      await loadRequirementVersions({ silent: true });
      setActiveTab("final");
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "版本切换失败",
        actionLabel: "切换最终需求版本",
        method: "PUT",
        path: `/projects/${projectId}/requirements/${documentId}/versions/${version.id}/current`,
      });
    } finally {
      setSwitchingRequirementVersionId("");
    }
  }

  function updatePendingAnswerDraft(questionId: string, patch: Partial<PendingAnswerDraft>) {
    setPendingAnswerDrafts((current) => {
      const existing = current[questionId] ?? {
        selectedOptionId: "",
        customAnswer: "",
        answerType: "recommended_option",
      };
      return {
        ...current,
        [questionId]: {
          ...existing,
          ...patch,
        },
      };
    });
  }

  function restoreHandledPendingItem(item: RequirementAnalysisPendingItem) {
    setPendingAnswerDrafts((current) => ({
      ...current,
      [item.id]: {
        selectedOptionId: item.answer?.selected_option_id ?? "",
        customAnswer: item.answer?.answer_type === "custom" ? item.answer.answer_markdown : "",
        answerType: item.answer?.answer_type === "custom" ? "custom" : "recommended_option",
      },
    }));
    setActiveRestoredPendingItemId(item.id);
    setAnalysisTab("clarification");
    toast.info("已移回待澄清列表，关闭弹窗后可编辑");
  }

  async function saveClarificationAnswer(item: RequirementAnalysisPendingItem, forcedAnswerType?: "defer") {
    if (!analysisResult) {
      toast.error("尚未生成需求分析结果");
      return;
    }
    const draft = pendingAnswerDrafts[item.id] ?? {
      selectedOptionId: item.answer?.selected_option_id ?? "",
      customAnswer: "",
      answerType: item.answer?.answer_type ?? "recommended_option",
    };
    const customAnswer = draft.customAnswer.trim();
    const selectedFallbackOption = pendingRecommendedOptions(item).find(
      (option) => option.id === draft.selectedOptionId && option.id.startsWith("__fallback_"),
    );
    const answerType = forcedAnswerType ?? (customAnswer || selectedFallbackOption ? "custom" : draft.answerType);
    if (answerType === "recommended_option" && !draft.selectedOptionId) {
      toast.error("请选择推荐选项，或填写自定义说明");
      return;
    }
    setSavingClarificationId(item.id);
    try {
      const result = await apiRequest<RequirementClarificationAnswerResponse>(
        `/projects/${projectId}/requirements/${documentId}/analysis/${analysisResult.id}/clarification-answers`,
        {
          method: "POST",
          body: JSON.stringify({
            question_id: item.id,
            answer_type: answerType,
            selected_option_id: answerType === "recommended_option" ? draft.selectedOptionId : "",
            custom_answer:
              answerType === "defer"
                ? ""
                : selectedFallbackOption
                  ? selectedFallbackOption.answer_markdown
                  : customAnswer,
          }),
        },
      );
      setAnalysisResult(result.analysis);
      setPendingAnswerDrafts((current) => {
        const next = { ...current };
        delete next[item.id];
        return next;
      });
      setActiveRestoredPendingItemId("");
      toast.success(answerType === "defer" ? "已标记暂不处理" : "答复已写入初步需求");
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "保存答复失败",
        actionLabel: "保存待澄清答复",
        method: "POST",
        path: analysisResult
          ? `/projects/${projectId}/requirements/${documentId}/analysis/${analysisResult.id}/clarification-answers`
          : undefined,
      });
    } finally {
      setSavingClarificationId("");
    }
  }

  async function setPrimaryFile(file: SourceFile) {
    setSettingPrimaryFileId(file.id);
    try {
      await apiRequest(`/projects/${projectId}/requirements/${documentId}/files/${file.id}/primary`, {
        method: "PUT",
      });
      toast.success("已设为主需求文件");
      await loadOverview({ silent: true });
      setSelectedFileId(file.id);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "主需求文件设置失败",
        actionLabel: "设为主需求文件",
        method: "PUT",
        path: `/projects/${projectId}/requirements/${documentId}/files/${file.id}/primary`,
      });
    } finally {
      setSettingPrimaryFileId("");
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
      reportError(requestError, {
        fallbackMessage: "原始文件删除失败",
        actionLabel: "删除原始文件",
        method: "DELETE",
        path: "/requirement-files/{id}",
      });
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
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
            return;
          }
          reject(apiErrorFromXhr(xhr, "文件上传失败"));
        };
        xhr.onerror = () => reject(apiErrorFromXhr(xhr, "网络异常，文件上传失败"));
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
      reportError(err, {
        fallbackMessage: "文件上传失败",
        actionLabel: "追加需求文件",
        method: "POST",
        path: `/projects/${projectId}/requirements`,
      });
      setUploadStates(
        Object.fromEntries(uploadFiles.map((f) => [`${f.name}-${f.size}`, { progress: 0, status: "error" as const }])),
      );
    } finally {
      setUploadSubmitting(false);
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
    (activeTab === "analysis" &&
      ((analysisTab === "analysis-report" && Boolean(analysisReportMarkdown.trim())) ||
        (analysisTab === "quality" && Boolean(qualityAssuranceMarkdown.trim())) ||
        (analysisTab === "enhanced" && Boolean(preliminaryMarkdown.trim())))) ||
    (activeTab === "final" && Boolean(overview.initial_markdown_content.trim()));
  const requirementTocRefreshKey = [
    activeTab,
    analysisTab,
    selectedFile?.id ?? "",
    currentStandardPreview?.markdownContent.length ?? 0,
    analysisReportMarkdown.length,
    qualityAssuranceMarkdown.length,
    preliminaryMarkdown.length,
    initialMarkdownContent.length,
    analysisResult?.finalized_version_id ?? "",
  ].join(":");
  const requirementTocAnchorSelector =
    activeTab === "standard"
      ? `#${STANDARD_FILE_SECTION_ID} .requirement-document-preview`
      : activeTab === "analysis"
        ? analysisTab === "quality"
          ? `#quality-assurance-section .requirement-document-preview`
          : analysisTab === "enhanced"
            ? `#enhanced-requirement-section .requirement-document-preview`
            : `#analysis-report-section .requirement-document-preview`
        : `#${FINAL_REQUIREMENT_SECTION_ID} .requirement-document-preview`;
  return (
    <PageShell
      breadcrumbs={["项目", "需求", overview.document.name]}
      description="查看原始文件、标准文件、主需求和分析结果。"
      title="需求概览"
    >
      {showRequirementToc ? (
        <DynamicIslandTOC
          anchorSelector={requirementTocAnchorSelector}
          refreshKey={requirementTocRefreshKey}
          selector={REQUIREMENT_DOCUMENT_TOC_SELECTOR}
        />
      ) : null}
      <Tabs className="space-y-4" onValueChange={handleDetailTabChange} value={activeTab}>
        <TabsList>
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="original">原始文件</TabsTrigger>
          <TabsTrigger value="standard">标准文件</TabsTrigger>
          <TabsTrigger value="analysis">需求分析</TabsTrigger>
          <TabsTrigger value="final">最终需求</TabsTrigger>
          <TabsTrigger value="versions">版本记录</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <RequirementProgressSteps steps={requirementProgressSteps} />
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
                    <TableHead>文件角色</TableHead>
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
                        <Badge variant={file.file_role === "primary" ? "default" : "secondary"}>
                          {fileRoleLabels[file.file_role] ?? file.file_role}
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
                              label: file.file_role === "primary" ? "已是主需求" : "设为主需求",
                              icon: Check,
                              onSelect: () => setPrimaryFile(file),
                              disabled:
                                file.file_role === "primary" ||
                                settingPrimaryFileId === file.id ||
                                !["success", "warning"].includes(file.conversion_status),
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
                      <TableCell className="py-8 text-center text-muted-foreground text-sm" colSpan={6}>
                        暂无原始文件。上传需求文件后，可生成标准文件并选择主需求进行分析。
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
              <div className="flex flex-wrap items-center gap-2">
                <RequirementFileSwitcher
                  files={overview.files}
                  onSelect={setSelectedFileId}
                  selectedFileId={selectedFile?.id ?? ""}
                />
                {selectedFile ? <FileRoleBadge file={selectedFile} /> : null}
              </div>
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
                {selectedFile ? <FileRoleBadge file={selectedFile} /> : null}
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
                    {selectedFile?.file_role !== "primary" ? (
                      <Button
                        disabled={
                          !selectedFile ||
                          settingPrimaryFileId === selectedFile.id ||
                          !["success", "warning"].includes(selectedFile.conversion_status)
                        }
                        onClick={() => selectedFile && setPrimaryFile(selectedFile)}
                        type="button"
                      >
                        {settingPrimaryFileId === selectedFile?.id ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <Check className="size-4" />
                        )}
                        设为主需求
                      </Button>
                    ) : null}
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

        <TabsContent value="analysis">
          <ShellSection>
            <Tabs className="space-y-4" onValueChange={setAnalysisTab} value={analysisTab}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <TabsList>
                  <TabsTrigger value="analysis-report">需求分析</TabsTrigger>
                  <TabsTrigger value="clarification">待澄清</TabsTrigger>
                  <TabsTrigger value="quality">质量保障</TabsTrigger>
                  <TabsTrigger value="enhanced">初步需求</TabsTrigger>
                </TabsList>
                <div className="flex flex-wrap items-center justify-end gap-2">
                  {analysisTab === "clarification" ? (
                    <Button className="gap-2" onClick={() => setHandledClarificationDialogOpen(true)} type="button">
                      <History className="size-4" />
                      已处理项
                      <RequirementRoleBadge shape="circle" size="xs" variant="destructive">
                        {handledPendingAnalysisItems.length}
                      </RequirementRoleBadge>
                    </Button>
                  ) : null}
                  {requirementReviewRunning ? (
                    <Button
                      disabled={stoppingReview}
                      onClick={() => setReviewStopConfirmOpen(true)}
                      type="button"
                      variant="destructive"
                    >
                      {stoppingReview ? <Loader2 className="size-4 animate-spin" /> : <Square className="size-4" />}
                      {stoppingReview ? "停止中" : "停止分析"}
                    </Button>
                  ) : (
                    <Button
                      disabled={Boolean(requirementAnalysisDisabledReason)}
                      onClick={reviewPrimaryRequirement}
                      title={requirementAnalysisDisabledReason || undefined}
                      type="button"
                    >
                      <FileSearch className="size-4" />
                      {reviewLoading ? "分析中" : "需求分析"}
                    </Button>
                  )}
                  {canFinalizeRequirement ? (
                    <Button
                      disabled={finalizingRequirement}
                      onClick={() => void finalizePreliminaryRequirement()}
                      type="button"
                    >
                      {finalizingRequirement ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <Check className="size-4" />
                      )}
                      {finalizingRequirement ? "转换中" : "转为最终需求"}
                    </Button>
                  ) : null}
                </div>
              </div>
              <TabsContent id="analysis-report-section" value="analysis-report">
                <MarkdownPreview
                  className="requirement-document-preview"
                  content={analysisReportMarkdown}
                  emptyClassName="flex items-center justify-center text-center"
                  emptyText={analysisReportEmptyText}
                />
              </TabsContent>
              <TabsContent value="clarification">
                {visiblePendingAnalysisItems.length || Object.keys(pendingAnswerDrafts).length ? (
                  <div className="space-y-3">
                    {pendingAnalysisItems
                      .filter((item) => isPendingItemOpen(item) || Boolean(pendingAnswerDrafts[item.id]))
                      .map((item) => {
                        const itemNumber = pendingItemNumber(
                          pendingAnalysisItems.findIndex((pendingItem) => pendingItem.id === item.id),
                        );
                        const isAppliedAnswer = item.answer?.apply_status === "applied";
                        const savedCustomAnswer =
                          isAppliedAnswer && item.answer?.answer_type === "custom" ? item.answer.answer_markdown : "";
                        const isEditingHandledAnswer = Boolean(pendingAnswerDrafts[item.id]);
                        const draft = pendingAnswerDrafts[item.id] ?? {
                          selectedOptionId: item.answer?.selected_option_id ?? "",
                          customAnswer: savedCustomAnswer,
                          answerType: item.answer?.answer_type ?? "recommended_option",
                        };
                        const isSaving = savingClarificationId === item.id;
                        const issueType = pendingIssueType(item);
                        const sourceExcerpt = pendingItemSourceExcerpt(item);
                        const itemHeading = pendingItemHeading(item);
                        const questionBody = normalizePendingQuestionText(item.question);
                        const recommendedOptions = pendingRecommendedOptions(item);
                        return (
                          <div
                            className={cn(
                              "overflow-hidden rounded-lg border bg-card text-card-foreground shadow-sm transition-colors dark:shadow-none",
                              activeRestoredPendingItemId === item.id
                                ? "border-primary/50 ring-2 ring-primary/15"
                                : "border-border",
                            )}
                            data-pending-item-id={item.id}
                            key={item.id}
                          >
                            <div className="bg-muted/20 px-4 py-3">
                              <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
                                <div className="grid min-w-0 grid-cols-[auto_auto_auto_minmax(0,1fr)] items-center gap-2">
                                  <span className="inline-flex h-7 min-w-8 items-center justify-center rounded-md border border-border bg-background px-2 font-medium text-[11px] text-muted-foreground tabular-nums">
                                    {itemNumber}
                                  </span>
                                  <Badge variant="outline">{pendingIssueTypeLabels[issueType]}</Badge>
                                  <Badge variant={item.severity === "blocker" ? "destructive" : "secondary"}>
                                    {pendingSeverityLabels[item.severity] ?? item.severity}
                                  </Badge>
                                  <span className="min-w-0 break-words font-medium text-foreground text-sm leading-6">
                                    {itemHeading}
                                  </span>
                                </div>
                                <Button
                                  className="h-8 shrink-0 px-2.5 text-xs"
                                  disabled={!sourceExcerpt}
                                  onClick={() => setSourceExcerptItem(item)}
                                  type="button"
                                  variant="outline"
                                >
                                  <Eye className="size-3.5" />
                                  查看原文
                                </Button>
                              </div>
                            </div>
                            <div className="space-y-3 px-4 pt-2 pb-4">
                              {item.impact ? (
                                <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-amber-800 text-xs leading-5 dark:text-amber-200">
                                  <span className="font-medium">影响</span>
                                  <span className="mx-1 text-amber-700/70 dark:text-amber-200/70">/</span>
                                  {item.impact}
                                </div>
                              ) : null}

                              {questionBody ? (
                                <div className="rounded-md border border-border bg-background px-3 py-2 dark:bg-input/20">
                                  <div className="text-foreground text-sm leading-6">{questionBody}</div>
                                </div>
                              ) : null}

                              <div className="rounded-md border border-border bg-muted/25 p-3 dark:bg-muted/15">
                                <div className="mb-2 font-medium text-[11px] text-muted-foreground">推荐处理</div>
                                {recommendedOptions.length ? (
                                  <div className="space-y-2">
                                    {recommendedOptions.slice(0, 2).map((option, index) => {
                                      const selected =
                                        draft.answerType === "recommended_option" &&
                                        draft.selectedOptionId === option.id;
                                      return (
                                        <button
                                          className={cn(
                                            "grid w-full grid-cols-[28px_1fr] items-start gap-2 rounded-md border bg-background px-3 py-2.5 text-left text-sm transition-all dark:bg-input/20",
                                            selected
                                              ? "border-primary/45 shadow-sm ring-1 ring-primary/15 dark:bg-primary/10 dark:shadow-none dark:ring-primary/25"
                                              : "border-transparent hover:border-border hover:bg-muted/30 hover:shadow-sm dark:hover:bg-input/35 dark:hover:shadow-none",
                                          )}
                                          disabled={isSaving || isFinalized}
                                          key={option.id}
                                          onClick={() =>
                                            updatePendingAnswerDraft(item.id, {
                                              answerType: "recommended_option",
                                              selectedOptionId: option.id,
                                            })
                                          }
                                          type="button"
                                        >
                                          <span
                                            className={cn(
                                              "inline-flex h-6 w-6 items-center justify-center rounded-full border font-medium text-xs",
                                              selected
                                                ? "border-primary bg-primary text-primary-foreground"
                                                : "border-border bg-muted/50 text-muted-foreground",
                                            )}
                                          >
                                            {optionBadge(index)}
                                          </span>
                                          <span className="min-w-0 text-muted-foreground leading-6">
                                            {option.answer_markdown}
                                          </span>
                                        </button>
                                      );
                                    })}
                                  </div>
                                ) : null}

                                <div
                                  className={cn(
                                    "mt-2 grid w-full grid-cols-[28px_1fr] items-start gap-2 rounded-md border bg-background px-3 py-2.5 transition-all dark:bg-input/20",
                                    draft.answerType === "custom"
                                      ? "border-primary/45 shadow-sm ring-1 ring-primary/15 dark:bg-primary/10 dark:shadow-none dark:ring-primary/25"
                                      : "border-transparent hover:border-border hover:bg-muted/30 dark:hover:bg-input/35",
                                  )}
                                >
                                  <span
                                    className={cn(
                                      "inline-flex h-6 w-6 items-center justify-center rounded-full border font-medium text-xs",
                                      draft.answerType === "custom"
                                        ? "border-primary bg-primary text-primary-foreground"
                                        : "border-border bg-muted/50 text-muted-foreground",
                                    )}
                                  >
                                    {optionBadge(recommendedOptions.slice(0, 2).length)}
                                  </span>
                                  <Textarea
                                    className="min-h-6 w-full resize-none border-0 bg-transparent p-0 text-muted-foreground text-sm leading-6 shadow-none placeholder:text-muted-foreground focus-visible:ring-0 focus-visible:ring-offset-0 dark:bg-transparent dark:disabled:bg-transparent"
                                    disabled={isSaving || isFinalized}
                                    onChange={(event) =>
                                      updatePendingAnswerDraft(item.id, {
                                        answerType: "custom",
                                        customAnswer: event.target.value,
                                      })
                                    }
                                    onFocus={() =>
                                      updatePendingAnswerDraft(item.id, {
                                        answerType: "custom",
                                        customAnswer: draft.customAnswer,
                                      })
                                    }
                                    placeholder={draft.answerType === "custom" ? "" : "手动补充确认口径"}
                                    value={draft.customAnswer}
                                  />
                                </div>
                              </div>

                              <div className="mt-4 flex flex-wrap items-center justify-end gap-2 border-t pt-3">
                                <Button
                                  className="h-8 px-3 text-xs"
                                  disabled={isSaving || isFinalized || (isAppliedAnswer && !isEditingHandledAnswer)}
                                  onClick={() => void saveClarificationAnswer(item, "defer")}
                                  type="button"
                                  variant="outline"
                                >
                                  <SkipForward className="size-4" />
                                  暂不处理
                                </Button>
                                <Button
                                  className="h-8 px-3 text-xs"
                                  disabled={isSaving || isFinalized}
                                  onClick={() => void saveClarificationAnswer(item)}
                                  type="button"
                                >
                                  {isSaving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
                                  保存答复
                                </Button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                  </div>
                ) : (
                  <div className="flex min-h-[280px] flex-col items-center justify-center rounded-lg border border-dashed bg-muted/15 text-center text-muted-foreground text-sm">
                    <div className="font-medium text-foreground">
                      {analysisResult
                        ? handledPendingAnalysisItems.length
                          ? "当前没有待处理澄清项"
                          : "暂无待澄清事项"
                        : "尚未执行需求分析"}
                    </div>
                    <div className="mt-1">
                      {analysisResult
                        ? handledPendingAnalysisItems.length
                          ? "已写入和暂不处理的条目可在“已处理项”中修改。"
                          : "完成分析后会在这里展示需要确认的内容。"
                        : "完成分析后会在这里展示待澄清事项。"}
                    </div>
                  </div>
                )}
              </TabsContent>
              <TabsContent id="quality-assurance-section" value="quality">
                <MarkdownPreview
                  className="requirement-document-preview"
                  content={qualityAssuranceMarkdown}
                  emptyClassName="flex items-center justify-center text-center"
                  emptyText={
                    reviewLoading
                      ? "需求分析中，完成后会在这里展示质量保障报告。"
                      : "尚未生成质量保障报告，请先执行需求分析。"
                  }
                />
              </TabsContent>
              <TabsContent id="enhanced-requirement-section" value="enhanced">
                <MarkdownPreview
                  className="requirement-document-preview markdown-enhanced"
                  content={preliminaryMarkdown}
                  emptyClassName="flex items-center justify-center text-center"
                  emptyText={
                    reviewLoading
                      ? "需求分析中，完成后会在这里展示增强版需求文档。"
                      : "尚未生成增强版需求文档，请先执行需求分析。"
                  }
                />
              </TabsContent>
            </Tabs>
          </ShellSection>
        </TabsContent>

        <TabsContent value="final">
          <ShellSection id={FINAL_REQUIREMENT_SECTION_ID}>
            <div className="mb-3">
              <h2 className="font-medium text-sm">最终需求</h2>
              <p className="mt-1 text-muted-foreground text-xs">当前已生效的需求版本内容。</p>
            </div>
            <MarkdownPreview
              className="requirement-document-preview"
              content={overview.initial_markdown_content}
              emptyClassName="flex items-center justify-center text-center"
              emptyText={finalRequirementEmptyText}
            />
          </ShellSection>
        </TabsContent>

        <TabsContent value="versions">
          <ShellSection>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-medium text-sm">版本记录</h2>
                <p className="mt-1 text-muted-foreground text-xs">{currentRequirementVersionText}。</p>
              </div>
              <Button
                disabled={versionsLoading}
                onClick={() => {
                  void loadRequirementVersions();
                }}
                type="button"
                variant="outline"
              >
                {versionsLoading ? <Loader2 className="size-4 animate-spin" /> : <History className="size-4" />}
                刷新
              </Button>
            </div>
            {versionsError ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-destructive text-sm">
                {versionsError}
              </div>
            ) : (
              <div className="overflow-hidden rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>版本</TableHead>
                      <TableHead>摘要</TableHead>
                      <TableHead>创建时间</TableHead>
                      <TableHead className="w-20">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {finalRequirementVersions.map((version) => (
                      <TableRow key={version.id}>
                        <TableCell>{`v${version.version_no}`}</TableCell>
                        <TableCell className="max-w-2xl whitespace-normal">
                          {requirementVersionSummary(version)}
                        </TableCell>
                        <TableCell>{formatDateTime(version.created_at)}</TableCell>
                        <TableCell>
                          <Button
                            aria-label="查看版本详情"
                            onClick={() => {
                              void openRequirementVersionDetail(version);
                            }}
                            size="icon-sm"
                            type="button"
                            variant="ghost"
                          >
                            <Eye className="size-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                    {finalRequirementVersions.length === 0 ? (
                      <TableRow>
                        <TableCell className="py-8 text-center text-muted-foreground text-sm" colSpan={4}>
                          尚未生成最终需求版本
                        </TableCell>
                      </TableRow>
                    ) : null}
                  </TableBody>
                </Table>
              </div>
            )}
          </ShellSection>
        </TabsContent>
      </Tabs>
      <Dialog onOpenChange={(open) => !open && setSourceExcerptItem(null)} open={Boolean(sourceExcerptItem)}>
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden p-0 sm:max-w-3xl">
          <DialogHeader className="shrink-0 gap-2 px-6 pt-6 pb-4">
            <DialogTitle>{sourceExcerptItem ? pendingItemTitle(sourceExcerptItem) : "需求原文"}</DialogTitle>
            <DialogDescription>
              {sourceExcerptItem ? (
                <span className="inline-flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{pendingIssueTypeLabels[pendingIssueType(sourceExcerptItem)]}</Badge>
                  <Badge variant={sourceExcerptItem.severity === "blocker" ? "destructive" : "secondary"}>
                    {pendingSeverityLabels[sourceExcerptItem.severity] ?? sourceExcerptItem.severity}
                  </Badge>
                </span>
              ) : (
                "查看待澄清项关联的需求原文"
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 overflow-auto px-6 pb-6">
            <pre className="whitespace-pre-wrap rounded-lg border bg-muted/30 p-4 text-sm leading-6">
              {sourceExcerptItem ? pendingItemSourceExcerpt(sourceExcerptItem) || "暂无关联原文" : ""}
            </pre>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog onOpenChange={setHandledClarificationDialogOpen} open={handledClarificationDialogOpen}>
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden p-0 sm:max-w-3xl">
          <DialogHeader className="shrink-0 gap-3 border-b bg-muted/10 py-5 pr-24 pl-6">
            <DialogTitle>管理已处理</DialogTitle>
            <Tabs
              className="w-fit"
              onValueChange={(value) => setHandledClarificationFilter(value as "all" | "applied" | "not_applicable")}
              value={handledClarificationFilter}
            >
              <TabsList>
                {[
                  { value: "all", label: "全部", count: handledPendingAnalysisItems.length },
                  { value: "applied", label: "已写入", count: appliedPendingAnalysisCount },
                  { value: "not_applicable", label: "暂不处理", count: deferredPendingAnalysisCount },
                ].map((filter) => (
                  <TabsTrigger className="min-w-20 px-3" key={filter.value} value={filter.value}>
                    {filter.label}
                    <RequirementRoleBadge shape="circle" size="xs" variant="destructive">
                      {filter.count}
                    </RequirementRoleBadge>
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </DialogHeader>
          <div className="min-h-0 overflow-y-auto px-6 py-5">
            {filteredHandledPendingAnalysisItems.length ? (
              <div className="space-y-2.5">
                {filteredHandledPendingAnalysisItems.map((item) => {
                  const itemNumber = pendingItemNumber(
                    pendingAnalysisItems.findIndex((pendingItem) => pendingItem.id === item.id),
                  );
                  const itemHeading = pendingItemHeading(item);
                  const answerText = item.answer?.answer_markdown?.trim() || item.answer?.user_note?.trim() || "";
                  const isDeferredAnswer = item.answer?.apply_status === "not_applicable";
                  return (
                    <div
                      className="grid grid-cols-[5px_minmax(0,1fr)] overflow-hidden rounded-md border border-border bg-card text-card-foreground transition-colors hover:border-muted-foreground/30"
                      key={item.id}
                    >
                      <div className={isDeferredAnswer ? "bg-slate-400 dark:bg-slate-500" : "bg-emerald-500"} />
                      <div className="p-4">
                        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
                          <div className="min-w-0">
                            <div className="flex min-w-0 flex-wrap items-center gap-2">
                              <span className="inline-flex h-7 min-w-8 items-center justify-center rounded-sm border border-border bg-muted/40 px-2 font-medium text-[11px] text-muted-foreground tabular-nums">
                                {itemNumber}
                              </span>
                              <Badge variant={isDeferredAnswer ? "secondary" : "outline"}>
                                {handledPendingItemLabel(item)}
                              </Badge>
                              <Badge variant={item.severity === "blocker" ? "destructive" : "secondary"}>
                                {pendingSeverityLabels[item.severity] ?? item.severity}
                              </Badge>
                            </div>
                            <div className="mt-3 break-words text-foreground text-sm leading-6">{itemHeading}</div>
                          </div>
                          <Button
                            className="h-8 shrink-0 justify-self-end px-3 text-xs"
                            disabled={isFinalized}
                            onClick={() => restoreHandledPendingItem(item)}
                            type="button"
                            variant={isDeferredAnswer ? "default" : "outline"}
                          >
                            <Pencil className="size-3.5" />
                            {isDeferredAnswer ? "移回处理" : "移回修改"}
                          </Button>
                        </div>
                        {answerText ? (
                          <div className="mt-3 border-muted-foreground/20 border-l-2 pl-3 text-muted-foreground text-sm leading-6">
                            <span className="mr-2 font-medium text-foreground">澄清：</span>
                            {answerText}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="flex min-h-52 flex-col items-center justify-center rounded-lg border border-dashed bg-muted/15 text-center text-muted-foreground text-sm">
                <RotateCcw className="mb-3 size-5" />
                <div className="font-medium text-foreground">
                  {handledPendingAnalysisItems.length ? "当前筛选下暂无条目" : "暂无已处理条目"}
                </div>
                <div className="mt-1">
                  {handledPendingAnalysisItems.length
                    ? "切换右上角筛选查看其他处理状态。"
                    : "保存答复或标记暂不处理后，会在这里集中管理。"}
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
      <Dialog
        onOpenChange={(open) => {
          if (!open) {
            setSelectedRequirementVersion(null);
            setSelectedRequirementVersionLoading(false);
          }
        }}
        open={Boolean(selectedRequirementVersion)}
      >
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:max-w-4xl">
          <DialogHeader className="shrink-0 gap-2 px-6 pt-6 pb-4">
            <DialogTitle>版本详情</DialogTitle>
            <DialogDescription>
              {selectedRequirementVersion
                ? `v${selectedRequirementVersion.version_no} / ${requirementVersionActionLabel()}`
                : "加载中"}
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 space-y-4 overflow-auto px-6 pb-6">
            {selectedRequirementVersionLoading ? (
              <div className="flex items-center gap-2 rounded-lg border bg-muted/20 p-4 text-muted-foreground text-sm">
                <Loader2 className="size-4 animate-spin" />
                正在加载版本最终需求
              </div>
            ) : null}
            {selectedRequirementVersion ? (
              <RequirementVersionDetailContent version={selectedRequirementVersion} />
            ) : null}
          </div>
          <DialogFooter className="border-t px-6 py-4">
            <Button
              disabled={[
                !selectedRequirementVersion,
                selectedRequirementVersionLoading,
                selectedRequirementVersion ? switchingRequirementVersionId === selectedRequirementVersion.id : false,
                selectedRequirementVersion
                  ? selectedRequirementVersion.id === overview.document.current_version_id
                  : false,
                selectedRequirementVersion?.is_current === true,
              ].some(Boolean)}
              onClick={() => {
                if (selectedRequirementVersion) {
                  void switchRequirementVersion(selectedRequirementVersion);
                }
              }}
              type="button"
            >
              {selectedRequirementVersion && switchingRequirementVersionId === selectedRequirementVersion.id ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Check className="size-4" />
              )}
              {[
                selectedRequirementVersion?.id === overview.document.current_version_id,
                selectedRequirementVersion?.is_current,
              ].some(Boolean)
                ? "当前生效版本"
                : "切换为当前版本"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <AlertDialog onOpenChange={setReviewStopConfirmOpen} open={reviewStopConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <div
              aria-hidden="true"
              className="flex size-12 shrink-0 items-center justify-center rounded-full bg-destructive/10 text-destructive ring-1 ring-destructive/15"
            >
              <Square className="size-5" />
            </div>
            <div className="flex flex-col gap-2">
              <AlertDialogTitle>停止需求分析？</AlertDialogTitle>
              <AlertDialogDescription>
                停止后将终止 AI 分析，并删除本次分析产生的模型调用记录与工作区产物。需求分析 run
                记录会保留，但分析报告、待澄清事项和增强版需求等内容不会保留。
              </AlertDialogDescription>
            </div>
          </AlertDialogHeader>
          <AlertDialogFooter className="sm:justify-center">
            <AlertDialogCancel disabled={stoppingReview}>继续分析</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              disabled={stoppingReview}
              onClick={() => {
                void stopRequirementAnalysis();
              }}
            >
              {stoppingReview ? <Loader2 className="size-4 animate-spin" /> : <Square className="size-4" />}
              停止分析
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <AlertDialog onOpenChange={setReviewClearConfirmOpen} open={reviewClearConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <div
              aria-hidden="true"
              className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary ring-1 ring-primary/15"
            >
              <FileSearch className="size-5" />
            </div>
            <div className="flex flex-col gap-2">
              <AlertDialogTitle>{hasFinalRequirementContent ? "重新需求分析" : "开始需求分析？"}</AlertDialogTitle>
              <AlertDialogDescription>
                {hasFinalRequirementContent
                  ? "当前已有最终需求内容。重新执行需求分析会清空需求分析和最终需求 tab 内容，分析完成后需要重新转为最终需求。是否继续？"
                  : "将基于当前主需求标准文件生成需求分析、待澄清事项和质量保障结果。分析开始后会清空旧的需求分析和最终需求内容。"}
              </AlertDialogDescription>
            </div>
          </AlertDialogHeader>
          <AlertDialogFooter className="sm:justify-center">
            <AlertDialogCancel disabled={reviewLoading}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={reviewLoading}
              onClick={() => {
                void submitRequirementAnalysis();
              }}
            >
              {reviewLoading ? <Loader2 className="size-4 animate-spin" /> : <FileSearch className="size-4" />}
              继续分析
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <Dialog onOpenChange={setFinalizeConfirmOpen} open={finalizeConfirmOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>转为最终需求</DialogTitle>
            <DialogDescription>
              当前需求分析仍存在待澄清事项或质量警告。转为最终需求后会生成新的最终需求版本，后续可继续通过版本记录追溯。是否继续？
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              disabled={finalizingRequirement}
              onClick={() => setFinalizeConfirmOpen(false)}
              type="button"
              variant="outline"
            >
              取消
            </Button>
            <Button
              disabled={finalizingRequirement}
              onClick={() => {
                setFinalizeConfirmOpen(false);
                void finalizePreliminaryRequirement(true);
              }}
              type="button"
            >
              {finalizingRequirement ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
              继续转换
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}

function RequirementProgressSteps({ steps }: { steps: RequirementProgressStep[] }) {
  return (
    <ShellSection>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-medium text-sm">需求处理进度</h2>
          <p className="mt-1 text-muted-foreground text-xs">按原始需求、标准需求、需求分析、最终需求推进。</p>
        </div>
      </div>
      <div className="relative">
        <div className="absolute top-4 bottom-4 left-4 w-px bg-border md:top-5 md:right-[12.5%] md:left-[12.5%] md:h-px md:w-auto" />
        <div className="relative grid gap-5 md:grid-cols-4">
          {steps.map((step) => (
            <div className="relative flex gap-3 md:flex-col md:items-center md:gap-2 md:text-center" key={step.id}>
              <RequirementStepMarker status={step.status} />
              <div className="min-w-0">
                <h3
                  className={cn(
                    "font-medium text-sm",
                    step.status === "completed" && "text-emerald-700 dark:text-emerald-300",
                    step.status === "running" && "text-primary",
                    step.status === "upcoming" && "text-muted-foreground",
                  )}
                >
                  {step.title}
                </h3>
              </div>
            </div>
          ))}
        </div>
      </div>
    </ShellSection>
  );
}

function RequirementStepMarker({ status }: { status: RequirementProgressStepStatus }) {
  return (
    <span
      className={cn(
        "z-10 flex size-8 shrink-0 items-center justify-center rounded-full border bg-card",
        status === "completed" &&
          "border-emerald-500 bg-emerald-500 text-white shadow-[0_0_0_4px] shadow-emerald-500/15",
        status === "running" &&
          "border-primary bg-primary text-primary-foreground shadow-[0_0_0_4px] shadow-primary/15",
        status === "upcoming" && "border-border bg-muted/80 text-muted-foreground",
      )}
    >
      {status === "completed" ? <Check className="size-4" /> : null}
      {status === "running" ? <Loader2 className="size-4 animate-spin" /> : null}
      {status === "upcoming" ? <span className="size-2 rounded-full bg-current" /> : null}
    </span>
  );
}

function FileRoleBadge({ file }: { file: SourceFile }) {
  return (
    <RequirementRoleBadge
      appearance="outline"
      className={
        file.file_role === "primary"
          ? "border-primary/20 bg-primary/5 text-foreground"
          : "border-border bg-muted/40 text-muted-foreground"
      }
      shape="circle"
      variant="secondary"
    >
      <BadgeDot className={file.file_role === "primary" ? "bg-primary" : "bg-muted-foreground"} />
      {fileRoleLabels[file.file_role] ?? file.file_role}
    </RequirementRoleBadge>
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
  return displayName.replace(/\.[^.]+$/, "");
}

function isConfirmRequired(error: unknown) {
  return error instanceof ApiRequestError && error.code === "REQUIREMENT_ANALYSIS_CONFIRM_REQUIRED";
}
