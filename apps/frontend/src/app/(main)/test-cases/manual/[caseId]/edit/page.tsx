"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useParams, useRouter, useSearchParams } from "next/navigation";

import { ArrowLeft, FilePenLine, Loader2, Plus, Save, Sparkles, Trash2 } from "lucide-react";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
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
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  type ApiManualTestCase,
  type ApiManualTestCaseAiGenerateRequest,
  type ApiManualTestCaseAiGenerateResult,
  type ApiManualTestCaseUpdate,
  apiRequest,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { useProjectContextStore } from "@/stores/project-context-store";

type EditableStep = {
  id: string;
  action: string;
  expected_result: string;
};

type ManualTestCaseEditForm = {
  title: string;
  preconditions: string;
  steps: EditableStep[];
  notes: string;
};

function toPayload(form: ManualTestCaseEditForm): ApiManualTestCaseUpdate {
  return {
    title: form.title.trim(),
    preconditions: form.preconditions.trim(),
    steps: form.steps.map(({ action, expected_result }) => ({
      action: action.trim(),
      expected_result: expected_result.trim(),
    })),
    notes: form.notes.trim(),
  };
}

function toEditForm(testCase: ApiManualTestCase): ManualTestCaseEditForm {
  return {
    title: testCase.title,
    preconditions: testCase.preconditions,
    steps: testCase.steps.map((step, index) => ({
      id: `step-${testCase.id}-${index}`,
      action: step.action,
      expected_result: step.expected_result,
    })),
    notes: testCase.notes,
  };
}

export default function ManualTestCaseEditPage() {
  const params = useParams<{ caseId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { scope: projectScope, currentProjectId, hydrate, hasHydrated } = useProjectContextStore();
  const queryProjectId = searchParams.get("project") ?? "";
  const projectId = queryProjectId || (projectScope === "project" ? (currentProjectId ?? "") : "");
  const detailHref = `/test-cases/manual/${params.caseId}?project=${projectId}`;
  const [testCase, setTestCase] = useState<ApiManualTestCase | null>(null);
  const [form, setForm] = useState<ManualTestCaseEditForm | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const originalPayloadRef = useRef("");
  const [leaveDialogOpen, setLeaveDialogOpen] = useState(false);
  const [aiDialogOpen, setAiDialogOpen] = useState(false);
  const [aiDescription, setAiDescription] = useState("");
  const [includeExplorationArtifacts, setIncludeExplorationArtifacts] = useState(true);
  const [aiGenerating, setAiGenerating] = useState(false);
  const [pendingAiResult, setPendingAiResult] = useState<ApiManualTestCaseAiGenerateResult | null>(null);
  const [overwriteDialogOpen, setOverwriteDialogOpen] = useState(false);

  useEffect(() => {
    if (!hasHydrated) {
      hydrate();
    }
  }, [hasHydrated, hydrate]);

  const loadDetail = useCallback(async () => {
    if (!projectId || !params.caseId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const detail = await apiRequest<ApiManualTestCase>(`/projects/${projectId}/test-cases/${params.caseId}`);
      const nextForm = toEditForm(detail);
      setTestCase(detail);
      setForm(nextForm);
      originalPayloadRef.current = JSON.stringify(toPayload(nextForm));
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "测试用例信息加载失败");
    } finally {
      setLoading(false);
    }
  }, [params.caseId, projectId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const isDirty = useMemo(
    () => Boolean(form && JSON.stringify(toPayload(form)) !== originalPayloadRef.current),
    [form],
  );

  useEffect(() => {
    if (!isDirty) {
      return;
    }
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  function updateStep(index: number, field: "action" | "expected_result", value: string) {
    setForm((current) =>
      current
        ? {
            ...current,
            steps: current.steps.map((step, stepIndex) => (stepIndex === index ? { ...step, [field]: value } : step)),
          }
        : current,
    );
  }

  function addStep() {
    setForm((current) =>
      current
        ? {
            ...current,
            steps: [
              ...current.steps,
              { id: `step-${Date.now()}-${current.steps.length}`, action: "", expected_result: "" },
            ],
          }
        : current,
    );
  }

  function removeStep(index: number) {
    setForm((current) =>
      current && current.steps.length > 1
        ? { ...current, steps: current.steps.filter((_, stepIndex) => stepIndex !== index) }
        : current,
    );
  }

  function applyAiResult(result: ApiManualTestCaseAiGenerateResult) {
    setForm((current) =>
      current
        ? {
            ...current,
            title: result.title,
            preconditions: result.preconditions,
            steps: result.steps.map((step, index) => ({
              id: `step-ai-${Date.now()}-${index}`,
              action: step.action,
              expected_result: step.expected_result,
            })),
          }
        : current,
    );
    setPendingAiResult(null);
    setOverwriteDialogOpen(false);
    toast.success("AI 内容已填入，请检查后保存");
  }

  async function generateWithAi() {
    const description = aiDescription.trim();
    if (description.length < 2) {
      toast.error("请输入测试描述");
      return;
    }
    setAiGenerating(true);
    try {
      const payload: ApiManualTestCaseAiGenerateRequest = {
        description,
        include_exploration_artifacts: includeExplorationArtifacts,
      };
      const result = await apiRequest<ApiManualTestCaseAiGenerateResult>(
        `/projects/${projectId}/test-cases/ai-generate`,
        { method: "POST", body: JSON.stringify(payload) },
      );
      setAiDialogOpen(false);
      setPendingAiResult(result);
      setOverwriteDialogOpen(true);
    } finally {
      setAiGenerating(false);
    }
  }

  async function saveChanges() {
    if (!form || !testCase) {
      return;
    }
    const payload = toPayload(form);
    if (!payload.title) {
      toast.error("请填写用例名称");
      return;
    }
    if (payload.steps.some((step) => !step.action || !step.expected_result)) {
      toast.error("请完整填写每一步的操作步骤和预期结果");
      return;
    }
    setSaving(true);
    try {
      const updated = await apiRequest<ApiManualTestCase>(`/projects/${projectId}/test-cases/${testCase.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      const nextForm = toEditForm(updated);
      setTestCase(updated);
      setForm(nextForm);
      originalPayloadRef.current = JSON.stringify(payload);
      toast.success("测试用例已更新");
    } finally {
      setSaving(false);
    }
  }

  function requestLeave() {
    if (isDirty) {
      setLeaveDialogOpen(true);
      return;
    }
    router.push(detailHref);
  }

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("testCases", { label: "编辑用例" })}
      fillViewport
      projectScope={projectScope}
      title="编辑测试用例"
    >
      <ShellSection className="overflow-hidden p-0">
        {loading ? (
          <div className="flex min-h-72 flex-1 items-center justify-center text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" />
            测试用例加载中
          </div>
        ) : testCase && form ? (
          <div className="flex min-h-0 flex-1 flex-col">
            <header className="flex shrink-0 flex-col gap-4 border-b bg-card px-5 py-4 lg:flex-row lg:items-center lg:justify-between lg:px-7">
              <div className="flex min-w-0 items-start gap-3">
                <Button aria-label="返回用例信息" onClick={requestLeave} size="icon" variant="ghost">
                  <ArrowLeft className="size-4" />
                </Button>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h1 className="truncate font-semibold text-lg">编辑测试用例</h1>
                    {isDirty ? (
                      <span className="inline-flex items-center gap-1.5 text-amber-700 text-xs dark:text-amber-300">
                        <span className="size-1.5 rounded-full bg-amber-500" />
                        存在未保存修改
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 truncate text-muted-foreground text-sm">{testCase.title}</p>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2 pl-11 lg:pl-0">
                <Button onClick={() => setAiDialogOpen(true)} variant="outline">
                  <Sparkles className="size-4" />
                  AI 生成
                </Button>
                <Button onClick={requestLeave} variant="ghost">
                  取消
                </Button>
                <Button disabled={!isDirty || saving} onClick={() => void saveChanges()}>
                  {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
                  保存修改
                </Button>
              </div>
            </header>

            <div className="min-h-0 flex-1 overflow-y-auto scroll-smooth">
              <div className="mx-auto w-full max-w-6xl px-5 py-7 lg:px-8 lg:py-9">
                <section aria-labelledby="basic-information-title" className="border-b pb-9">
                  <div className="mb-6 flex items-start gap-3">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <FilePenLine className="size-4" />
                    </span>
                    <div>
                      <h2 className="font-semibold text-base" id="basic-information-title">
                        基础信息
                      </h2>
                    </div>
                  </div>
                  <div className="grid gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(16rem,0.5fr)]">
                    <label className="grid gap-2 font-medium text-sm" htmlFor="test-case-title">
                      用例名称
                      <Input
                        className="h-10 bg-background px-3"
                        id="test-case-title"
                        onChange={(event) =>
                          setForm((current) => (current ? { ...current, title: event.target.value } : current))
                        }
                        value={form.title}
                      />
                    </label>
                    <div className="grid gap-2 font-medium text-sm">
                      项目
                      <div className="flex h-10 items-center rounded-lg border bg-muted/35 px-3 font-normal text-muted-foreground">
                        {testCase.project_name}
                      </div>
                    </div>
                    <label className="grid gap-2 font-medium text-sm lg:col-span-2" htmlFor="test-case-preconditions">
                      前置条件
                      <Textarea
                        className="min-h-24 resize-y bg-background px-3 py-2.5 leading-6"
                        id="test-case-preconditions"
                        onChange={(event) =>
                          setForm((current) => (current ? { ...current, preconditions: event.target.value } : current))
                        }
                        placeholder="请输入执行该用例前需要满足的条件"
                        value={form.preconditions}
                      />
                    </label>
                  </div>
                </section>

                <section aria-labelledby="test-steps-title" className="py-9">
                  <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="font-semibold text-base" id="test-steps-title">
                          测试步骤
                        </h2>
                        <span className="font-mono text-muted-foreground text-xs tabular-nums">
                          {form.steps.length} 条
                        </span>
                      </div>
                    </div>
                    <Button onClick={addStep} size="sm" variant="outline">
                      <Plus className="size-4" />
                      新增步骤
                    </Button>
                  </div>

                  <div className="overflow-hidden rounded-lg border bg-background">
                    <div className="hidden grid-cols-[3.75rem_minmax(0,1fr)_minmax(0,1fr)_3.5rem] gap-4 border-b bg-muted/35 px-4 py-2.5 font-medium text-muted-foreground text-xs md:grid">
                      <span className="text-center">序号</span>
                      <span>操作步骤</span>
                      <span>预期结果</span>
                      <span className="text-center">操作</span>
                    </div>
                    <div className="divide-y">
                      {form.steps.map((step, index) => (
                        <div
                          className="group grid gap-3 px-4 py-4 transition-colors hover:bg-muted/20 md:grid-cols-[3.75rem_minmax(0,1fr)_minmax(0,1fr)_3.5rem] md:gap-4"
                          key={step.id}
                        >
                          <div className="flex items-center justify-between md:block md:pt-2 md:text-center">
                            <span className="font-medium font-mono text-primary text-sm tabular-nums">
                              {String(index + 1).padStart(2, "0")}
                            </span>
                            <span className="text-muted-foreground text-xs md:hidden">步骤</span>
                          </div>
                          <label
                            className="grid gap-1.5 text-muted-foreground text-xs md:block"
                            htmlFor={`${step.id}-action`}
                          >
                            <span className="md:hidden">操作步骤</span>
                            <Textarea
                              aria-label={`第 ${index + 1} 步操作步骤`}
                              className="min-h-20 resize-y border-transparent bg-muted/30 px-3 py-2.5 leading-6 hover:bg-muted/45 focus-visible:bg-background"
                              id={`${step.id}-action`}
                              onChange={(event) => updateStep(index, "action", event.target.value)}
                              placeholder="输入操作步骤"
                              value={step.action}
                            />
                          </label>
                          <label
                            className="grid gap-1.5 text-muted-foreground text-xs md:block"
                            htmlFor={`${step.id}-expected-result`}
                          >
                            <span className="md:hidden">预期结果</span>
                            <Textarea
                              aria-label={`第 ${index + 1} 步预期结果`}
                              className="min-h-20 resize-y border-transparent bg-muted/30 px-3 py-2.5 leading-6 hover:bg-muted/45 focus-visible:bg-background"
                              id={`${step.id}-expected-result`}
                              onChange={(event) => updateStep(index, "expected_result", event.target.value)}
                              placeholder="输入预期结果"
                              value={step.expected_result}
                            />
                          </label>
                          <div className="flex items-start justify-end md:justify-center md:pt-1">
                            <Button
                              aria-label={`删除第 ${index + 1} 步`}
                              disabled={form.steps.length === 1}
                              onClick={() => removeStep(index)}
                              size="icon"
                              title={form.steps.length === 1 ? "至少保留一个步骤" : "删除步骤"}
                              variant="ghost"
                            >
                              <Trash2 className="size-4" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>

                <section aria-labelledby="notes-title" className="border-t pt-9 pb-4">
                  <h2 className="font-semibold text-base" id="notes-title">
                    备注
                  </h2>
                  <Textarea
                    className="mt-4 min-h-24 resize-y bg-background px-3 py-2.5 leading-6"
                    onChange={(event) =>
                      setForm((current) => (current ? { ...current, notes: event.target.value } : current))
                    }
                    placeholder="请输入补充说明"
                    value={form.notes}
                  />
                </section>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex min-h-72 flex-1 items-center justify-center text-muted-foreground">未找到该测试用例</div>
        )}
      </ShellSection>

      <Dialog open={aiDialogOpen} onOpenChange={setAiDialogOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>AI 生成测试用例</DialogTitle>
          </DialogHeader>
          <div className="grid gap-5">
            <label className="grid gap-2 font-medium text-sm" htmlFor="edit-test-case-ai-description">
              测试描述
              <Textarea
                className="min-h-32"
                id="edit-test-case-ai-description"
                maxLength={4000}
                onChange={(event) => setAiDescription(event.target.value)}
                placeholder="例如：验证用户连续输入错误密码达到限制次数后，账号会被锁定。"
                value={aiDescription}
              />
            </label>
            <div className="flex items-center justify-between gap-4 rounded-lg border bg-muted/25 p-3">
              <div>
                <div className="font-medium text-sm">关联探索产物</div>
              </div>
              <Switch
                aria-label="关联探索产物"
                checked={includeExplorationArtifacts}
                onCheckedChange={setIncludeExplorationArtifacts}
              />
            </div>
          </div>
          <DialogFooter>
            <Button disabled={aiGenerating} onClick={() => setAiDialogOpen(false)} variant="outline">
              取消
            </Button>
            <Button disabled={aiGenerating} onClick={() => void generateWithAi()}>
              {aiGenerating ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              生成并预览
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={overwriteDialogOpen} onOpenChange={setOverwriteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>应用 AI 生成内容？</AlertDialogTitle>
            <AlertDialogDescription>这会替换当前用例名称、前置条件和全部测试步骤，备注会保留。</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={() => pendingAiResult && applyAiResult(pendingAiResult)}>
              替换当前内容
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={leaveDialogOpen} onOpenChange={setLeaveDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>放弃未保存修改？</AlertDialogTitle>
            <AlertDialogDescription>当前修改尚未保存，离开后无法恢复。</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>继续编辑</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => router.push(detailHref)}
            >
              放弃修改
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageShell>
  );
}
