"use client";

import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { useParams, useSearchParams } from "next/navigation";

import {
  AlertCircle,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleX,
  Clock,
  Download,
  FileText,
  List,
  ListChecks,
  Loader2,
  Network,
  Pencil,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { toast } from "@/lib/toast";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { TestCaseMindMap } from "@/components/ai-testing/test-case-mind-map";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SlidingNumber } from "@/components/ui/sliding-number";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  type ApiTestCase,
  type ApiTestCaseReviewResult,
  type ApiTestCaseReviewStats,
  type ApiTestCaseReviewUpdate,
  type ApiTestCaseSet,
  type ApiTestCaseStep,
  apiBlobRequest,
  apiRequest,
} from "@/lib/api-client";
import { testCasePriorityVisual } from "@/lib/test-case-priority";
import { cn } from "@/lib/utils";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { useProjectContextStore } from "@/stores/project-context-store";

type ReviewFilter = "all" | "ready_for_review" | "approved" | "rejected";

type RejectDialogState = {
  open: boolean;
  caseId: string;
  feedback: string;
};

type InlineEditStep = ApiTestCaseStep & {
  editKey: string;
};

type InlineEditState = {
  caseId: string;
  preconditions: string;
  steps: InlineEditStep[];
  expectedResult: string;
};

const filterLabels: Record<ReviewFilter, string> = {
  all: "全部",
  ready_for_review: "待评审",
  approved: "已采纳",
  rejected: "未采纳",
};

const visibleReviewFilters: Exclude<ReviewFilter, "all">[] = ["ready_for_review", "approved", "rejected"];

function priorityTone(priority: string) {
  return testCasePriorityVisual(priority).tone;
}

function moduleSegments(moduleName: string) {
  return moduleName
    .split("-")
    .map((segment) => segment.trim())
    .filter(Boolean);
}

function getNextPendingCase(cases: ApiTestCase[], currentCaseId: string) {
  const currentIndex = cases.findIndex((item) => item.id === currentCaseId);
  const ordered = [...cases.slice(currentIndex + 1), ...cases.slice(0, Math.max(currentIndex, 0))];
  return ordered.find((item) => item.status === "ready_for_review") ?? null;
}

type ReviewStatusTone = {
  bar: string;
  text: string;
  ring: string;
  bg: string;
  iconBg: string;
};

const REVIEW_TONE: Record<string, ReviewStatusTone> = {
  ready_for_review: {
    bar: "bg-amber-500",
    text: "text-amber-700 dark:text-amber-300",
    ring: "ring-1 ring-amber-200/60 dark:ring-amber-500/30",
    bg: "bg-amber-50 dark:bg-amber-500/15",
    iconBg: "bg-amber-500/20 text-amber-700 dark:text-amber-300",
  },
  approved: {
    bar: "bg-emerald-500",
    text: "text-emerald-700 dark:text-emerald-300",
    ring: "ring-1 ring-emerald-200/60 dark:ring-emerald-500/30",
    bg: "bg-emerald-50 dark:bg-emerald-500/15",
    iconBg: "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300",
  },
  rejected: {
    bar: "bg-rose-500",
    text: "text-rose-700 dark:text-rose-300",
    ring: "ring-1 ring-rose-200/60 dark:ring-rose-500/30",
    bg: "bg-rose-50 dark:bg-rose-500/15",
    iconBg: "bg-rose-500/20 text-rose-700 dark:text-rose-300",
  },
  draft: {
    bar: "bg-slate-400",
    text: "text-slate-700 dark:text-slate-300",
    ring: "ring-1 ring-slate-200 dark:ring-slate-500/30",
    bg: "bg-slate-100 dark:bg-slate-500/20",
    iconBg: "bg-slate-500/20 text-slate-700 dark:text-slate-300",
  },
};

const REVIEW_STATUS_LABEL: Record<string, string> = {
  ready_for_review: "待评审",
  approved: "已采纳",
  rejected: "未采纳",
  draft: "草稿",
};

function reviewTone(status: string): ReviewStatusTone {
  return REVIEW_TONE[status] ?? REVIEW_TONE.draft;
}

function reviewStatusLabel(status: string): string {
  return REVIEW_STATUS_LABEL[status] ?? status;
}

export default function TestCaseReviewPage() {
  const params = useParams<{ setId: string }>();
  const searchParams = useSearchParams();
  const { scope: projectScope, currentProjectId, hydrate, hasHydrated } = useProjectContextStore();
  const setId = params.setId;
  const queryProjectId = searchParams.get("project") ?? "";
  const projectId = queryProjectId || (projectScope === "project" ? (currentProjectId ?? "") : "");

  const [testCaseSet, setTestCaseSet] = useState<ApiTestCaseSet | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [filter, setFilter] = useState<ReviewFilter>("ready_for_review");
  const [viewMode, setViewMode] = useState<"list" | "mindmap">("list");
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [savingCaseId, setSavingCaseId] = useState("");
  const [rejectDialog, setRejectDialog] = useState<RejectDialogState>({ open: false, caseId: "", feedback: "" });
  const [inlineEdit, setInlineEdit] = useState<InlineEditState>({
    caseId: "",
    preconditions: "",
    steps: [],
    expectedResult: "",
  });

  useEffect(() => {
    if (!hasHydrated) {
      hydrate();
    }
  }, [hasHydrated, hydrate]);

  const loadDetail = useCallback(async () => {
    if (!projectId || !setId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const detail = await apiRequest<ApiTestCaseSet>(`/projects/${projectId}/test-case-sets/${setId}`);
      setTestCaseSet(detail);
      setSelectedCaseId((current) => current || detail.cases[0]?.id || "");
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "测试用例评审数据加载失败");
    } finally {
      setLoading(false);
    }
  }, [projectId, setId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const stats: ApiTestCaseReviewStats = testCaseSet?.review_stats ?? {
    case_count: 0,
    approved_count: 0,
    rejected_count: 0,
    pending_count: 0,
    reviewed_count: 0,
    adoption_rate: 0,
    review_progress: 0,
  };
  const filterCounts: Record<ReviewFilter, number> = {
    all: stats.case_count,
    ready_for_review: stats.pending_count,
    approved: stats.approved_count,
    rejected: stats.rejected_count,
  };

  const filteredCases = useMemo(() => {
    const keyword = searchText.trim().toLowerCase();
    return (testCaseSet?.cases ?? []).filter((item) => {
      const statusMatched = filter === "all" || item.status === filter;
      const keywordMatched =
        !keyword ||
        [item.title, item.module, item.priority, item.expected_result, item.review_feedback].some((value) =>
          value.toLowerCase().includes(keyword),
        );
      return statusMatched && keywordMatched;
    });
  }, [filter, searchText, testCaseSet?.cases]);

  const selectedCase =
    (testCaseSet?.cases ?? []).find((item) => item.id === selectedCaseId) ?? filteredCases[0] ?? null;

  async function updateReview(
    caseId: string,
    payload: ApiTestCaseReviewUpdate,
    options?: { moveNext?: boolean; successMessage?: string },
  ) {
    if (!testCaseSet) return false;
    setSavingCaseId(caseId);
    try {
      const result = await apiRequest<ApiTestCaseReviewResult>(
        `/projects/${testCaseSet.project_id}/test-case-sets/${testCaseSet.id}/cases/${caseId}/review`,
        {
          method: "PATCH",
          body: JSON.stringify(payload),
        },
      );
      setTestCaseSet((current) => {
        if (!current) return current;
        const nextCases = current.cases.map((item) => (item.id === result.case.id ? result.case : item));
        if (options?.moveNext) {
          const nextPending = getNextPendingCase(nextCases, result.case.id);
          if (nextPending) {
            setSelectedCaseId(nextPending.id);
          }
        }
        return { ...current, cases: nextCases, review_stats: result.review_stats };
      });
      toast.success(
        options?.successMessage ??
          (payload.status === "approved"
            ? "已采纳测试用例"
            : payload.status === "rejected"
              ? "已标记不采纳"
              : "评审状态已保存"),
      );
      return true;
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "测试用例评审保存失败");
      return false;
    } finally {
      setSavingCaseId("");
    }
  }

  function openRejectDialog(testCase: ApiTestCase) {
    setRejectDialog({ open: true, caseId: testCase.id, feedback: testCase.review_feedback });
  }

  function startInlineEdit(testCase: ApiTestCase) {
    setInlineEdit({
      caseId: testCase.id,
      preconditions: testCase.preconditions,
      steps:
        testCase.steps.length > 0
          ? testCase.steps.map((step, index) => ({
              action: stepActionText(step),
              expected_result: step.expected_result || testCase.expected_result,
              editKey: `${testCase.id}-${index}-${stepActionText(step)}`,
            }))
          : [{ action: "", expected_result: "", editKey: `${testCase.id}-new-step` }],
      expectedResult: testCase.expected_result,
    });
  }

  async function rejectCurrent(feedback: string) {
    const caseId = rejectDialog.caseId;
    const reason = feedback.trim();
    if (!reason) {
      toast.error("请填写不采纳原因");
      return;
    }
    const saved = await updateReview(caseId, { status: "rejected", review_feedback: reason }, { moveNext: true });
    if (saved) {
      setRejectDialog({ open: false, caseId: "", feedback: "" });
    }
  }

  async function saveCaseContent() {
    const currentCase = (testCaseSet?.cases ?? []).find((item) => item.id === inlineEdit.caseId);
    if (!currentCase) return;
    const steps = inlineEdit.steps
      .map(({ action, expected_result }) => ({ action: action.trim(), expected_result: expected_result.trim() }))
      .filter((step) => step.action);
    if (steps.length === 0) {
      toast.error("测试步骤不能为空");
      return;
    }
    const saved = await updateReview(
      currentCase.id,
      {
        status: currentCase.status as ApiTestCaseReviewUpdate["status"],
        review_feedback: currentCase.review_feedback,
        preconditions: inlineEdit.preconditions,
        steps,
        expected_result: steps[steps.length - 1]?.expected_result || inlineEdit.expectedResult,
      },
      { successMessage: "测试用例已修改" },
    );
    if (saved) {
      setInlineEdit({ caseId: "", preconditions: "", steps: [], expectedResult: "" });
    }
  }

  async function exportTestCases() {
    if (!testCaseSet || !projectId) return;
    setExporting(true);
    try {
      const blob = await apiBlobRequest(`/projects/${projectId}/test-case-sets/${testCaseSet.id}/export/xmind`);
      downloadBlob(blob, `${safeDownloadName(testCaseSet.name)}.xmind`);
      toast.success("测试用例已导出");
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "测试用例导出失败");
    } finally {
      setExporting(false);
    }
  }

  const selectedCaseIsEditing = selectedCase?.id === inlineEdit.caseId;

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("testCases", ...(testCaseSet ? [{ label: testCaseSet.name }] : []))}
      description="逐条采纳或不采纳生成用例，并沉淀后续生成需要参考的反馈。"
      fillViewport
      title={testCaseSet?.name ?? "测试用例评审"}
    >
      <ReviewSummaryStrip
        actions={
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <fieldset aria-label="评审视图" className="flex h-8 rounded-lg border bg-slate-50 p-0.5 dark:bg-muted/50">
              <Button
                className="h-full gap-1.5 px-3 text-sm"
                onClick={() => setViewMode("list")}
                size="sm"
                variant={viewMode === "list" ? "secondary" : "ghost"}
              >
                <List className="size-4" />
                列表
              </Button>
              <Button
                className="h-full gap-1.5 px-3 text-sm"
                onClick={() => setViewMode("mindmap")}
                size="sm"
                variant={viewMode === "mindmap" ? "secondary" : "ghost"}
              >
                <Network className="size-4" />
                脑图
              </Button>
            </fieldset>
            <Button disabled={exporting || !testCaseSet || !projectId} onClick={exportTestCases} variant="outline">
              {exporting ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
              导出测试用例
            </Button>
          </div>
        }
        stats={stats}
      />

      <ShellSection className="flex min-h-0 flex-1 bg-[#F7F8FA] p-0 dark:bg-background">
        {loading ? (
          <div className="flex h-80 items-center justify-center gap-2 text-muted-foreground text-sm">
            <Loader2 className="size-4 animate-spin" />
            正在加载评审台
          </div>
        ) : !testCaseSet || !projectId ? (
          <div className="flex h-80 items-center justify-center text-muted-foreground text-sm">
            未找到测试用例集或缺少项目上下文。
          </div>
        ) : (
          <div className="grid min-h-0 flex-1 grid-cols-1 overflow-hidden rounded-xl lg:grid-cols-[360px_minmax(0,1fr)]">
            <aside
              className={cn(
                "min-h-0 flex-col border-b bg-white lg:border-r lg:border-b-0 dark:bg-card",
                viewMode === "mindmap" ? "hidden" : "flex",
              )}
            >
              <div className="flex flex-col gap-3 border-b p-4">
                <div className="relative">
                  <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    className="pl-9"
                    onChange={(event) => setSearchText(event.target.value)}
                    placeholder="搜索标题、模块、预期结果"
                    value={searchText}
                  />
                </div>
                <Tabs onValueChange={(value) => setFilter(value as ReviewFilter)} value={filter}>
                  <TabsList className="grid h-auto w-full grid-cols-3">
                    {visibleReviewFilters.map((item) => {
                      const isActive = item === filter;
                      return (
                        <TabsTrigger className="min-w-0 gap-1 px-2 text-xs" key={item} value={item}>
                          <span className="truncate">{filterLabels[item]}</span>
                          <span
                            className={cn(
                              "shrink-0 rounded-full px-1.5 font-mono text-[10px] tabular-nums ring-1 ring-inset",
                              filterChipTone(item, isActive),
                            )}
                          >
                            {filterCounts[item]}
                          </span>
                        </TabsTrigger>
                      );
                    })}
                  </TabsList>
                </Tabs>
              </div>
              <div className="min-h-0 flex-1 overflow-auto p-3">
                {filteredCases.map((item) => (
                  <CaseListCard
                    active={selectedCase?.id === item.id}
                    key={item.id}
                    testCase={item}
                    onClick={() => setSelectedCaseId(item.id)}
                  />
                ))}
                {filteredCases.length === 0 ? (
                  <div className="rounded-lg border border-dashed bg-white p-6 text-center text-muted-foreground text-sm dark:bg-card">
                    没有匹配的测试用例。
                  </div>
                ) : null}
              </div>
            </aside>

            <main
              className={cn(
                "relative flex min-h-0 min-w-0 flex-col bg-white dark:bg-card",
                viewMode === "mindmap" && "lg:col-span-2",
              )}
            >
              <div
                className={cn(
                  "relative flex min-h-0 flex-1",
                  viewMode !== "mindmap" && "pointer-events-none invisible absolute inset-0",
                )}
              >
                <TestCaseMindMap
                  active={viewMode === "mindmap"}
                  cases={filteredCases}
                  onSelectCase={(caseId) => {
                    setSelectedCaseId(caseId);
                    setViewMode("list");
                  }}
                  selectedCaseId={selectedCaseId}
                  setName={testCaseSet.name}
                />
              </div>
              <div className={cn("flex min-h-0 flex-1 flex-col", viewMode !== "list" && "hidden")}>
                {selectedCase ? (
                  <>
                    <CaseDetailHeader
                      onApprove={() =>
                        updateReview(
                          selectedCase.id,
                          { status: "approved", review_feedback: "" },
                          { moveNext: true },
                        )
                      }
                      onCancelEdit={() =>
                        setInlineEdit({ caseId: "", preconditions: "", steps: [], expectedResult: "" })
                      }
                      onEdit={() => startInlineEdit(selectedCase)}
                      onReject={() => openRejectDialog(selectedCase)}
                      onSaveEdit={saveCaseContent}
                      saving={savingCaseId === selectedCase.id}
                      selectedCase={selectedCase}
                      selectedCaseIsEditing={selectedCaseIsEditing}
                    />

                    <div className="flex-1 overflow-auto p-5">
                      {selectedCaseIsEditing ? (
                        <InlineCaseEditor editState={inlineEdit} onChange={setInlineEdit} />
                      ) : (
                        <div className="space-y-4">
                          <ReviewBlock icon={FileText} title="前置条件">
                            {selectedCase.preconditions || (
                              <span className="text-muted-foreground/70 italic">未填写前置条件</span>
                            )}
                          </ReviewBlock>
                          <ReviewBlock
                            icon={ListChecks}
                            subtitle={`共 ${selectedCase.steps.length} 步`}
                            title="测试步骤与预期结果"
                          >
                            <StepList testCase={selectedCase} />
                          </ReviewBlock>
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
                    请选择一个测试用例开始评审。
                  </div>
                )}
              </div>
            </main>
          </div>
        )}
      </ShellSection>

      <Dialog
        open={rejectDialog.open}
        onOpenChange={(open) => {
          if (!open) setRejectDialog({ open: false, caseId: "", feedback: "" });
        }}
      >
        <DialogContent className="gap-6 p-6 sm:max-w-lg" showCloseButton={false}>
          <DialogHeader className="items-center gap-4 text-center">
            <div
              aria-hidden="true"
              className="flex size-12 shrink-0 items-center justify-center rounded-full bg-red-50 text-red-600 ring-1 ring-red-100 dark:bg-red-500/15 dark:text-red-300 dark:ring-red-500/30"
            >
              <CircleX className="size-5" />
            </div>
            <div className="flex flex-col gap-2">
              <DialogTitle className="font-semibold text-lg leading-none">不采纳此用例</DialogTitle>
              <DialogDescription className="mx-auto max-w-md text-balance leading-6">
                原因将沉淀到不采纳用例库，后续生成会检索并参考。
              </DialogDescription>
            </div>
          </DialogHeader>
          <Field className="gap-2">
            <FieldLabel htmlFor="reject-feedback">不采纳原因</FieldLabel>
            <Textarea
              className="min-h-32 resize-y"
              id="reject-feedback"
              maxLength={1000}
              onChange={(event) => setRejectDialog((current) => ({ ...current, feedback: event.target.value }))}
              placeholder="例如：步骤缺少异常分支、预期结果不可验证、与需求不一致"
              value={rejectDialog.feedback}
            />
          </Field>
          <DialogFooter className="-mx-0 -mb-0 flex-col-reverse items-stretch gap-2 rounded-none border-0 bg-transparent p-0 sm:flex-row sm:items-center sm:justify-center">
            <Button
              className="sm:w-auto"
              onClick={() => setRejectDialog({ open: false, caseId: "", feedback: "" })}
              variant="outline"
            >
              取消
            </Button>
            <Button
              className="sm:w-auto"
              disabled={!rejectDialog.feedback.trim() || savingCaseId === rejectDialog.caseId}
              onClick={() => rejectCurrent(rejectDialog.feedback)}
            >
              {savingCaseId === rejectDialog.caseId ? <Loader2 className="size-4 animate-spin" /> : null}
              保存并沉淀知识
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}

function filterChipTone(item: ReviewFilter, isActive: boolean) {
  const activeRing = "ring-black/10 dark:ring-white/30";
  if (item === "rejected") return "bg-rose-500 text-white ring-rose-600/50";
  if (item === "approved") return "bg-emerald-500 text-white ring-emerald-600/50";
  if (item === "ready_for_review") return "bg-amber-500 text-white ring-amber-600/50";
  return "bg-slate-500 text-white ring-slate-600/50";
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function safeDownloadName(value: string) {
  return value.trim().replace(/[\\/:*?"<>|]+/g, "_") || "test-cases";
}

function ReviewSummaryStrip({ actions, stats }: { actions: ReactNode; stats: ApiTestCaseReviewStats }) {
  const adoptionRate = stats.reviewed_count === 0 ? 0 : Number((stats.adoption_rate * 100).toFixed(1));
  const reviewProgress = Number((stats.review_progress * 100).toFixed(1));

  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-stretch lg:justify-between">
      <div className="grid min-w-0 flex-1 gap-2 sm:grid-cols-3">
        <SummaryStatCard accent="emerald" icon={CheckCircle2} label="采纳率" suffix="%" value={adoptionRate} />
        <SummaryStatCard accent="amber" icon={Clock} label="评审进度" suffix="%" value={reviewProgress} />
        <SummaryStatCard accent="blue" icon={Sparkles} label="用例数量" value={stats.case_count} />
      </div>
      <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 lg:self-center">
        {actions}
      </div>
    </div>
  );
}

type SummaryAccent = "emerald" | "amber" | "blue";

function SummaryStatCard({
  label,
  value,
  icon: Icon,
  suffix = "",
  accent,
}: {
  label: string;
  value: number;
  icon: typeof Sparkles;
  suffix?: string;
  accent: SummaryAccent;
}) {
  const tone: Record<SummaryAccent, { ring: string; iconBg: string; iconFg: string; numFg: string }> = {
    emerald: {
      ring: "ring-emerald-200/60 dark:ring-emerald-500/30",
      iconBg: "bg-emerald-500/15",
      iconFg: "text-emerald-600 dark:text-emerald-300",
      numFg: "text-emerald-700 dark:text-emerald-300",
    },
    amber: {
      ring: "ring-amber-200/60 dark:ring-amber-500/30",
      iconBg: "bg-amber-500/15",
      iconFg: "text-amber-600 dark:text-amber-300",
      numFg: "text-amber-700 dark:text-amber-300",
    },
    blue: {
      ring: "ring-blue-200/60 dark:ring-blue-500/30",
      iconBg: "bg-blue-500/15",
      iconFg: "text-blue-600 dark:text-blue-300",
      numFg: "text-blue-700 dark:text-blue-300",
    },
  };
  const t = tone[accent];
  return (
    <div
      className={cn(
        "relative flex items-center gap-3 overflow-hidden rounded-lg border bg-card px-3 py-2.5 shadow-[0_1px_2px_rgba(15,23,42,0.03)] ring-1 ring-inset",
        t.ring,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "flex size-7 shrink-0 items-center justify-center rounded-md",
          t.iconBg,
          t.iconFg,
        )}
      >
        <Icon className="size-3.5" />
      </span>
      <span className="truncate font-medium text-muted-foreground text-xs">{label}</span>
      <span
        className={cn(
          "ml-auto flex items-baseline font-mono font-semibold text-lg leading-none tabular-nums",
          t.numFg,
        )}
      >
        <SlidingNumber value={value} />
        {suffix ? <span className="ml-0.5 text-xs">{suffix}</span> : null}
      </span>
    </div>
  );
}

function CaseListCard({
  testCase,
  active,
  onClick,
}: {
  testCase: ApiTestCase;
  active: boolean;
  onClick: () => void;
}) {
  const tone = reviewTone(testCase.status);
  return (
    <button
      className={cn(
        "group relative mb-2 w-full overflow-hidden rounded-lg border bg-white p-3 text-left transition dark:bg-card",
        "hover:border-foreground/15 hover:shadow-[0_2px_10px_rgba(15,23,42,0.04)]",
        active
          ? "border-primary/40 bg-primary/[0.03] shadow-[0_2px_10px_rgba(15,23,42,0.04)] ring-1 ring-primary/15 dark:bg-primary/10"
          : "border-slate-200/70 dark:border-border",
      )}
      key={testCase.id}
      onClick={onClick}
      type="button"
    >
      <span aria-hidden="true" className={cn("absolute inset-y-0 left-0 w-[3px]", tone.bar)} />
      <div className="flex min-w-0 flex-col gap-1 pl-1.5">
        <div className="flex min-w-0 items-start gap-1.5">
          {testCase.priority ? (
            <Badge
              className={cn("shrink-0 border px-1.5 py-0 font-mono text-[10px]", priorityTone(testCase.priority))}
              variant="outline"
            >
              {testCase.priority}
            </Badge>
          ) : null}
          <div className="line-clamp-2 min-w-0 font-medium text-[#101828] text-sm leading-snug dark:text-foreground">
            {testCase.title}
          </div>
        </div>
      </div>
    </button>
  );
}

function CaseDetailHeader({
  selectedCase,
  selectedCaseIsEditing,
  saving,
  onApprove,
  onReject,
  onEdit,
  onSaveEdit,
  onCancelEdit,
}: {
  selectedCase: ApiTestCase;
  selectedCaseIsEditing: boolean;
  saving: boolean;
  onApprove: () => void;
  onReject: () => void;
  onEdit: () => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
}) {
  const tone = reviewTone(selectedCase.status);
  const StatusIcon =
    selectedCase.status === "approved"
      ? CheckCircle2
      : selectedCase.status === "rejected"
        ? AlertCircle
        : Clock;

  return (
    <div className="border-b bg-white px-6 py-5 dark:bg-card">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <span
            aria-hidden="true"
            className={cn(
              "mt-1 flex size-9 shrink-0 items-center justify-center rounded-md",
              tone.iconBg,
            )}
          >
            <StatusIcon className="size-4" />
          </span>
          <div className="min-w-0 flex-1 space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-medium text-xs",
                  tone.bg,
                  tone.text,
                  tone.ring,
                )}
              >
                <span className={cn("size-1.5 rounded-full", tone.bar)} />
                {reviewStatusLabel(selectedCase.status)}
              </span>
              {selectedCase.priority ? (
                <Badge
                  className={cn("border px-1.5 py-0 font-mono text-[10px]", priorityTone(selectedCase.priority))}
                  variant="outline"
                >
                  {selectedCase.priority}
                </Badge>
              ) : null}
              <span className="text-muted-foreground text-xs">
                <ModulePathInline moduleName={selectedCase.module} />
              </span>
            </div>
            <h2 className="min-w-0 max-w-full font-semibold text-[#101828] text-xl leading-snug dark:text-foreground">
              {selectedCase.title}
            </h2>
            {selectedCase.status === "rejected" && selectedCase.review_feedback ? (
              <p className="flex items-start gap-1.5 rounded-md bg-rose-50 px-2 py-1 text-rose-700 text-xs ring-1 ring-rose-200/60 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/30">
                <CircleX className="mt-0.5 size-3 shrink-0" />
                <span className="line-clamp-2">{selectedCase.review_feedback}</span>
              </p>
            ) : null}
          </div>
        </div>
        <ReviewActions
          disabled={saving}
          editing={selectedCaseIsEditing}
          onApprove={onApprove}
          onCancelEdit={onCancelEdit}
          onEdit={onEdit}
          onReject={onReject}
          onSaveEdit={onSaveEdit}
          saving={saving}
          status={selectedCase.status}
        />
      </div>
    </div>
  );
}

function ModulePathInline({ moduleName }: { moduleName: string }) {
  const segments = moduleSegments(moduleName || "未分模块");
  if (segments.length === 0) return null;
  return (
    <span className="inline-flex items-center gap-1">
      {segments.map((segment, index) => (
        <span className="inline-flex items-center gap-1" key={`${segment}-${index}`}>
          {index > 0 ? <ChevronRight className="size-3 text-muted-foreground/60" /> : null}
          <span className={index === segments.length - 1 ? "text-foreground" : "text-muted-foreground"}>
            {segment}
          </span>
        </span>
      ))}
    </span>
  );
}

function ReviewActions({
  status,
  disabled,
  saving,
  editing,
  onApprove,
  onReject,
  onEdit,
  onSaveEdit,
  onCancelEdit,
}: {
  status: string;
  disabled: boolean;
  saving: boolean;
  editing: boolean;
  onApprove: () => void;
  onReject: () => void;
  onEdit: () => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
}) {
  if (editing) {
    return (
      <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
        <Button disabled={disabled} onClick={onSaveEdit}>
          {saving ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
          保存修改
        </Button>
        <Button disabled={disabled} onClick={onCancelEdit} variant="outline">
          <X className="size-4" />
          取消
        </Button>
      </div>
    );
  }

  return (
    <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
      {status !== "approved" ? (
        <Button disabled={disabled} onClick={onApprove}>
          {saving ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
          采纳
        </Button>
      ) : null}
      {status !== "rejected" ? (
        <Button
          className="border-rose-200 text-rose-700 hover:bg-rose-50 dark:border-rose-500/40 dark:text-rose-300 dark:hover:bg-rose-500/15"
          disabled={disabled}
          onClick={onReject}
          variant="outline"
        >
          <CircleX className="size-4" />
          不采纳
        </Button>
      ) : null}
      <Button disabled={disabled} onClick={onEdit} variant="outline">
        <Pencil className="size-4" />
        修改
      </Button>
    </div>
  );
}

function ReviewBlock({
  title,
  subtitle,
  icon: Icon,
  children,
}: {
  title: string;
  subtitle?: string;
  icon?: typeof FileText;
  children: ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-lg border bg-white shadow-[0_1px_2px_rgba(15,23,42,0.03)] dark:bg-card">
      <header className="flex items-center justify-between gap-3 border-b bg-muted/30 px-4 py-2.5 dark:bg-muted/20">
        <div className="flex items-center gap-2">
          {Icon ? (
            <span className="flex size-6 items-center justify-center rounded-md bg-primary/10 text-primary">
              <Icon className="size-3.5" />
            </span>
          ) : null}
          <h3 className="font-medium text-[#101828] text-sm dark:text-foreground">{title}</h3>
        </div>
        {subtitle ? (
          <span className="rounded-full bg-muted px-2 py-0.5 font-mono text-[11px] text-muted-foreground tabular-nums">
            {subtitle}
          </span>
        ) : null}
      </header>
      <div className="whitespace-pre-wrap px-4 py-3 text-[#101828] text-sm leading-6 dark:text-foreground">
        {children}
      </div>
    </section>
  );
}

function StepList({ testCase }: { testCase: ApiTestCase }) {
  if (testCase.steps.length === 0) {
    return <span className="text-muted-foreground/70 italic">未填写测试步骤</span>;
  }

  const stepKeyCounts = new Map<string, number>();
  const keyedSteps = testCase.steps.map((step) => {
    const keyBase = `${testCase.id}-${stepActionText(step)}-${step.expected_result ?? ""}`;
    const keyCount = (stepKeyCounts.get(keyBase) ?? 0) + 1;
    stepKeyCounts.set(keyBase, keyCount);
    return { rowKey: `${keyBase}-${keyCount}`, step };
  });

  return (
    <div className="flex flex-col gap-2">
      <div className="hidden items-center gap-4 px-3.5 text-muted-foreground text-xs md:grid md:grid-cols-[2.25rem_minmax(0,1fr)_minmax(0,1fr)]">
        <span aria-hidden="true" />
        <span>步骤</span>
        <span>预期结果</span>
      </div>
      <ol className="flex flex-col gap-2">
        {keyedSteps.map(({ rowKey, step }, index) => (
          <li
            className="overflow-hidden rounded-md border bg-white dark:bg-card"
            key={rowKey}
          >
            <div className="flex flex-col gap-3 p-3 md:grid md:grid-cols-[2.25rem_minmax(0,1fr)_minmax(0,1fr)] md:items-start md:gap-4 md:p-3.5">
              <span
                aria-hidden="true"
                className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 font-mono font-semibold text-primary text-xs tabular-nums"
              >
                {index + 1}
              </span>
              <div className="flex min-w-0 items-start gap-2 md:border-r md:border-slate-200/70 md:pr-4 md:dark:border-border">
                <p className="min-w-0 flex-1 text-[#101828] text-sm leading-relaxed dark:text-foreground">
                  {stepActionText(step) || (
                    <span className="text-muted-foreground/70 italic">未填写操作步骤</span>
                  )}
                </p>
              </div>
              <div className="flex min-w-0 items-start gap-2 rounded-md bg-emerald-50/70 px-2.5 py-1.5 text-emerald-800 text-xs ring-1 ring-emerald-200/50 md:leading-relaxed md:dark:bg-emerald-500/10 md:dark:ring-emerald-500/20">
                <span className="min-w-0 flex-1">
                  {step.expected_result || testCase.expected_result || (
                    <span className="italic text-muted-foreground/80">未填写预期结果</span>
                  )}
                </span>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function InlineCaseEditor({
  editState,
  onChange,
}: {
  editState: InlineEditState;
  onChange: (next: InlineEditState) => void;
}) {
  return (
    <div className="space-y-4">
      <ReviewBlock icon={FileText} title="前置条件">
        <Textarea
          className="min-h-[72px] resize-y bg-white py-2 leading-5 dark:bg-input/30"
          onChange={(event) => onChange({ ...editState, preconditions: event.target.value })}
          value={editState.preconditions}
        />
      </ReviewBlock>
      <ReviewBlock
        icon={ListChecks}
        subtitle={`${editState.steps.length} 步`}
        title="测试步骤"
      >
        <EditableStepList editState={editState} onChange={onChange} />
      </ReviewBlock>
    </div>
  );
}

function EditableStepList({
  editState,
  onChange,
}: {
  editState: InlineEditState;
  onChange: (next: InlineEditState) => void;
}) {
  function updateStep(index: number, patch: Partial<ApiTestCaseStep>) {
    onChange({
      ...editState,
      steps: editState.steps.map((step, stepIndex) => (stepIndex === index ? { ...step, ...patch } : step)),
    });
  }

  function addStep() {
    onChange({
      ...editState,
      steps: [
        ...editState.steps,
        { action: "", expected_result: "", editKey: `${editState.caseId}-new-${Date.now()}` },
      ],
    });
  }

  function removeStep(index: number) {
    const steps = editState.steps.filter((_, stepIndex) => stepIndex !== index);
    onChange({
      ...editState,
      steps: steps.length > 0 ? steps : [{ action: "", expected_result: "", editKey: `${editState.caseId}-new-step` }],
    });
  }

  return (
    <div className="flex flex-col gap-2">
      <ol className="flex flex-col gap-2">
        {editState.steps.map((step, index) => (
          <li
            className="flex items-stretch gap-3 overflow-hidden rounded-md border bg-white p-3 dark:bg-card"
            key={step.editKey}
          >
            <span
              aria-hidden="true"
              className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 font-mono font-semibold text-primary text-xs tabular-nums"
            >
              {index + 1}
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <Textarea
                className="min-h-[44px] resize-y bg-white py-1.5 text-sm leading-5 dark:bg-input/30"
                onChange={(event) => updateStep(index, { action: event.target.value })}
                placeholder="操作步骤"
                value={step.action}
              />
              <Textarea
                className="min-h-[44px] resize-y bg-white py-1.5 text-sm leading-5 dark:bg-input/30"
                onChange={(event) => updateStep(index, { expected_result: event.target.value })}
                placeholder="预期结果"
                value={step.expected_result}
              />
            </div>
            <button
              aria-label={`删除第 ${index + 1} 步`}
              className="flex size-7 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-500/10"
              onClick={() => removeStep(index)}
              type="button"
            >
              <X className="size-4" />
            </button>
          </li>
        ))}
      </ol>
      <div>
        <Button onClick={addStep} size="sm" variant="outline">
          <Sparkles className="size-3.5" />
          新增步骤
        </Button>
      </div>
    </div>
  );
}

function stepActionText(step: ApiTestCaseStep | string) {
  if (typeof step === "string") return step;
  return step.action || step.step || step.description || "";
}
