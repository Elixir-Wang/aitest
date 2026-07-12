"use client";

import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { useParams, useSearchParams } from "next/navigation";

import { Check, ChevronRight, CircleX, Download, List, Loader2, Network, Pencil, Search, X } from "lucide-react";
import { toast } from "sonner";

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

function filterCountTone(item: ReviewFilter, current: ReviewFilter) {
  if (item === current) return "bg-[#101828] text-white dark:bg-slate-100 dark:text-slate-900";
  if (item === "rejected") return "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300";
  if (item === "approved") return "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300";
  if (item === "ready_for_review") return "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300";
  return "bg-slate-100 text-slate-600 dark:bg-slate-500/20 dark:text-slate-300";
}

function getNextPendingCase(cases: ApiTestCase[], currentCaseId: string) {
  const currentIndex = cases.findIndex((item) => item.id === currentCaseId);
  const ordered = [...cases.slice(currentIndex + 1), ...cases.slice(0, Math.max(currentIndex, 0))];
  return ordered.find((item) => item.status === "ready_for_review") ?? null;
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
    setRejectDialog({ open: false, caseId: "", feedback: "" });
    await updateReview(caseId, { status: "rejected", review_feedback: feedback }, { moveNext: true });
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
      breadcrumbs={[
        { label: "测试资产" },
        { label: "测试用例", href: "/test-cases" },
        ...(testCaseSet ? [{ label: testCaseSet.name }] : []),
      ]}
      description="逐条采纳或不采纳生成用例，并沉淀下次重新生成需要避开的反馈。"
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
                    {visibleReviewFilters.map((item) => (
                      <TabsTrigger className="min-w-0 gap-1 px-2 text-xs" key={item} value={item}>
                        <span className="truncate">{filterLabels[item]}</span>
                        <span
                          className={cn(
                            "shrink-0 rounded-full px-1.5 font-mono text-[10px]",
                            filterCountTone(item, filter),
                          )}
                        >
                          {filterCounts[item]}
                        </span>
                      </TabsTrigger>
                    ))}
                  </TabsList>
                </Tabs>
              </div>
              <div className="min-h-0 flex-1 overflow-auto p-3">
                {filteredCases.map((item) => (
                  <button
                    className={cn(
                      "mb-2 w-full rounded-lg border border-slate-200/70 bg-white p-3 text-left transition hover:border-blue-200 hover:bg-blue-50/30 hover:shadow-sm dark:border-border dark:bg-card dark:hover:border-blue-500/50 dark:hover:bg-blue-500/10 dark:hover:shadow-none",
                      selectedCase?.id === item.id &&
                        "border-blue-300 bg-blue-50/70 shadow-sm ring-1 ring-blue-100 dark:border-blue-500/60 dark:bg-blue-500/15 dark:ring-blue-500/25",
                    )}
                    key={item.id}
                    onClick={() => setSelectedCaseId(item.id)}
                    type="button"
                  >
                    <div className="flex items-start gap-2">
                      {item.priority ? (
                        <Badge className={cn("shrink-0 border", priorityTone(item.priority))} variant="outline">
                          {item.priority}
                        </Badge>
                      ) : null}
                      <div className="min-w-0 flex-1">
                        <div className="line-clamp-2 font-medium text-[#101828] text-sm dark:text-foreground">
                          {item.title}
                        </div>
                      </div>
                    </div>
                  </button>
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
                    <div className="border-b p-4">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                        <div className="min-w-0 space-y-1.5">
                          <ModulePath moduleName={selectedCase.module} />
                          <div className="flex min-w-0 flex-wrap items-center gap-2">
                            <h2 className="min-w-0 max-w-full font-semibold text-[#101828] text-lg dark:text-foreground">
                              {selectedCase.title}
                            </h2>
                            {selectedCase.status === "rejected" ? (
                              <RejectedReasonButton
                                feedback={selectedCase.review_feedback}
                                onClick={() => openRejectDialog(selectedCase)}
                              />
                            ) : null}
                          </div>
                        </div>
                        <ReviewActions
                          disabled={savingCaseId === selectedCase.id}
                          onApprove={() =>
                            updateReview(
                              selectedCase.id,
                              { status: "approved", review_feedback: "" },
                              { moveNext: true },
                            )
                          }
                          onReject={() => openRejectDialog(selectedCase)}
                          onEdit={() => startInlineEdit(selectedCase)}
                          onSaveEdit={saveCaseContent}
                          onCancelEdit={() =>
                            setInlineEdit({ caseId: "", preconditions: "", steps: [], expectedResult: "" })
                          }
                          saving={savingCaseId === selectedCase.id}
                          status={selectedCase.status}
                          editing={selectedCaseIsEditing}
                        />
                      </div>
                    </div>

                    <div className="flex-1 overflow-auto p-5">
                      {selectedCaseIsEditing ? (
                        <InlineCaseEditor editState={inlineEdit} onChange={setInlineEdit} />
                      ) : (
                        <div className="space-y-4">
                          <ReviewBlock title="前置条件">{selectedCase.preconditions || "-"}</ReviewBlock>
                          <ReviewBlock title="测试步骤与预期结果">
                            <StepExpectationTable testCase={selectedCase} />
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
                可以补充原因，重新生成时会参考这些信息。也可以不填写。
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
            <Button className="sm:w-auto" onClick={() => rejectCurrent("")} variant="outline">
              <X className="size-4" />
              跳过说明并不采纳
            </Button>
            <Button className="sm:w-auto" onClick={() => rejectCurrent(rejectDialog.feedback)}>
              保存不采纳
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
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
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="grid min-w-0 flex-1 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm sm:h-8 sm:grid-cols-3 lg:max-w-2xl dark:border-border dark:bg-card dark:shadow-none">
        <ReviewSummaryModule accent="blue" label="采纳率" suffix="%" value={adoptionRate} />
        <ReviewSummaryModule accent="slate" label="评审进度" suffix="%" value={reviewProgress} />
        <ReviewSummaryModule accent="green" label="用例数量" value={stats.case_count} />
      </div>
      {actions}
    </div>
  );
}

function ReviewSummaryModule({
  label,
  value,
  accent,
  suffix = "",
}: {
  label: string;
  value: number;
  accent: "blue" | "slate" | "green";
  suffix?: string;
}) {
  const accentClasses = {
    blue: { dot: "bg-blue-500", label: "bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300" },
    slate: { dot: "bg-slate-500", label: "bg-slate-100 text-slate-700 dark:bg-slate-500/20 dark:text-slate-300" },
    green: {
      dot: "bg-emerald-500",
      label: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
    },
  };
  const tone = accentClasses[accent];

  return (
    <div className="flex h-8 min-w-0 items-center justify-center gap-3 border-slate-100 border-t px-3 first:border-t-0 sm:h-full sm:border-t-0 sm:border-l sm:first:border-l-0 dark:border-border">
      <div className={cn("flex shrink-0 items-center gap-1.5 rounded-md px-2 py-0.5", tone.label)}>
        <span className={cn("h-1.5 w-1.5 rounded-full", tone.dot)} />
        <span className="font-medium text-xs">{label}</span>
      </div>
      <div className="flex min-w-0 items-baseline">
        <span className="inline-flex items-baseline font-mono font-semibold text-[#101828] text-xs leading-none dark:text-foreground">
          <SlidingNumber value={value} />
          {suffix ? <span>{suffix}</span> : null}
        </span>
      </div>
    </div>
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
      <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 lg:pt-7">
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
    <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 lg:pt-7">
      {status !== "approved" ? (
        <Button disabled={disabled} onClick={onApprove}>
          {saving ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
          采纳
        </Button>
      ) : null}
      {status !== "rejected" ? (
        <Button
          className="border-red-200 text-red-700 hover:bg-red-50 dark:border-red-500/40 dark:text-red-300 dark:hover:bg-red-500/15"
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

function InlineCaseEditor({
  editState,
  onChange,
}: {
  editState: InlineEditState;
  onChange: (next: InlineEditState) => void;
}) {
  return (
    <div className="space-y-4">
      <ReviewBlock title="前置条件">
        <Textarea
          className="min-h-[72px] resize-y bg-white py-2 leading-5 dark:bg-input/30"
          onChange={(event) => onChange({ ...editState, preconditions: event.target.value })}
          value={editState.preconditions}
        />
      </ReviewBlock>
      <ReviewBlock title="测试步骤">
        <EditableStepTable editState={editState} onChange={onChange} />
      </ReviewBlock>
    </div>
  );
}

function EditableStepTable({
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
    <div className="overflow-hidden rounded-md border bg-white dark:bg-card">
      <table className="w-full border-collapse text-left text-sm">
        <thead className="bg-[#F7F8FA] text-[#475467] dark:bg-muted/40 dark:text-muted-foreground">
          <tr>
            <th className="w-16 border-b px-3 py-2 font-medium">序号</th>
            <th className="border-b px-3 py-2 font-medium">测试步骤</th>
            <th className="w-[36%] border-b px-3 py-2 font-medium">预期结果</th>
            <th className="w-20 border-b px-3 py-2 font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          {editState.steps.map((step, index) => (
            <tr className="border-b last:border-b-0" key={step.editKey}>
              <td className="px-3 py-3 align-top font-mono text-[#667085] dark:text-muted-foreground">{index + 1}</td>
              <td className="px-3 py-3 align-top">
                <Textarea
                  className="min-h-[52px] resize-y bg-white py-2 leading-5 dark:bg-input/30"
                  onChange={(event) => updateStep(index, { action: event.target.value })}
                  value={step.action}
                />
              </td>
              <td className="px-3 py-3 align-top">
                <Textarea
                  className="min-h-[52px] resize-y bg-white py-2 leading-5 dark:bg-input/30"
                  onChange={(event) => updateStep(index, { expected_result: event.target.value })}
                  value={step.expected_result}
                />
              </td>
              <td className="px-3 py-3 align-top">
                <Button onClick={() => removeStep(index)} size="sm" variant="outline">
                  删除
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="border-t bg-[#F7F8FA] p-3 dark:bg-muted/40">
        <Button onClick={addStep} size="sm" variant="outline">
          新增步骤
        </Button>
      </div>
    </div>
  );
}

function StepExpectationTable({ testCase }: { testCase: ApiTestCase }) {
  if (testCase.steps.length === 0) {
    return <span>-</span>;
  }

  const stepKeyCounts = new Map<string, number>();
  const keyedSteps = testCase.steps.map((step) => {
    const keyBase = `${testCase.id}-${stepActionText(step)}-${step.expected_result ?? ""}`;
    const keyCount = (stepKeyCounts.get(keyBase) ?? 0) + 1;
    stepKeyCounts.set(keyBase, keyCount);
    return { rowKey: `${keyBase}-${keyCount}`, step };
  });

  return (
    <div className="overflow-hidden rounded-md border">
      <table className="w-full border-collapse text-left text-sm">
        <thead className="bg-[#F7F8FA] text-[#475467] dark:bg-muted/40 dark:text-muted-foreground">
          <tr>
            <th className="w-16 border-b px-3 py-2 font-medium">序号</th>
            <th className="border-b px-3 py-2 font-medium">测试步骤</th>
            <th className="w-[36%] border-b px-3 py-2 font-medium">预期结果</th>
          </tr>
        </thead>
        <tbody>
          {keyedSteps.map(({ rowKey, step }, index) => (
            <tr className="border-b last:border-b-0" key={rowKey}>
              <td className="px-3 py-3 align-top font-mono text-[#667085] dark:text-muted-foreground">{index + 1}</td>
              <td className="px-3 py-3 align-top text-[#101828] dark:text-foreground">{stepActionText(step) || "-"}</td>
              <td className="px-3 py-3 align-top text-[#101828] dark:text-foreground">
                {step.expected_result || testCase.expected_result || "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function stepActionText(step: ApiTestCaseStep | string) {
  if (typeof step === "string") return step;
  return step.action || step.step || step.description || "";
}

function ModulePath({
  moduleName,
  variant = "default",
  className,
}: {
  moduleName: string;
  variant?: "default" | "compact";
  className?: string;
}) {
  const segments = moduleSegments(moduleName || "未分模块");
  const keyedSegments = segments.map((segment, index) => ({
    segment,
    path: segments.slice(0, index + 1).join("/"),
  }));
  const compact = variant === "compact";

  return (
    <div
      className={cn(
        "flex min-w-0 items-center gap-1 text-[#667085] dark:text-muted-foreground",
        compact ? "overflow-hidden text-[11px]" : "flex-wrap text-xs",
        className,
      )}
    >
      {compact ? null : <span className="font-medium text-[#98A2B3] dark:text-muted-foreground">模块</span>}
      {keyedSegments.map(({ segment, path }, index) => (
        <span className="flex min-w-0 items-center gap-1" key={path}>
          {index > 0 ? <ChevronRight className="size-3 shrink-0 text-slate-300 dark:text-slate-600" /> : null}
          <span
            className={cn(
              "min-w-0 truncate",
              index === segments.length - 1 &&
                (compact ? "text-[#475467] dark:text-slate-300" : "font-medium text-[#344054] dark:text-foreground"),
            )}
          >
            {segment}
          </span>
        </span>
      ))}
    </div>
  );
}

function RejectedReasonButton({ feedback, onClick }: { feedback: string; onClick: () => void }) {
  return (
    <Button
      className="h-7 max-w-[260px] justify-start gap-1.5 border-red-200 bg-red-50 px-2 text-red-700 text-xs hover:bg-red-100 dark:border-red-500/40 dark:bg-red-500/15 dark:text-red-300 dark:hover:bg-red-500/25"
      onClick={onClick}
      type="button"
      variant="outline"
    >
      <CircleX className="size-3.5 shrink-0" />
      <span className="truncate">{feedback || "未填写原因"}</span>
    </Button>
  );
}

function ReviewBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border bg-white p-4 dark:bg-card">
      <h3 className="mb-3 font-medium text-[#101828] text-sm dark:text-foreground">{title}</h3>
      <div className="whitespace-pre-wrap text-[#101828] text-sm leading-6 dark:text-foreground">{children}</div>
    </section>
  );
}
