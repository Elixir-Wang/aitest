"use client";

import { useEffect, useMemo, useState } from "react";

import { Check, Layers3, LoaderCircle, Search, X } from "lucide-react";

import { Select, SelectOption } from "@/components/ui/animated-select-1";
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
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  type ApiAutomationEnvironment,
  type ApiAutomationScenario,
  type ApiAutomationScenarioSuite,
  createApiAutomationScenarioSuite,
  updateApiAutomationScenarioSuite,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";

type ApiScenarioSuiteDialogProps = {
  environments: ApiAutomationEnvironment[];
  onOpenChange: (open: boolean) => void;
  onSaved: (suite: ApiAutomationScenarioSuite) => Promise<void> | void;
  open: boolean;
  projectId: string;
  scenarios: ApiAutomationScenario[];
  suite?: ApiAutomationScenarioSuite | null;
};

export function ApiScenarioSuiteDialog({
  environments,
  onOpenChange,
  onSaved,
  open,
  projectId,
  scenarios,
  suite,
}: ApiScenarioSuiteDialogProps) {
  const [busy, setBusy] = useState(false);
  const [suiteName, setSuiteName] = useState("");
  const [suiteDescription, setSuiteDescription] = useState("");
  const [environmentId, setEnvironmentId] = useState("");
  const [selectedScenarioIds, setSelectedScenarioIds] = useState<string[]>([]);
  const [scenarioSearchText, setScenarioSearchText] = useState("");

  useEffect(() => {
    if (!open) return;
    setSuiteName(suite?.name ?? "");
    setSuiteDescription(suite?.description ?? "");
    setEnvironmentId(suite?.api_environment_id ?? environments[0]?.id ?? "");
    setSelectedScenarioIds(suite?.scenarios.map((scenario) => scenario.id) ?? []);
    setScenarioSearchText("");
  }, [environments, open, suite]);

  const filteredScenarios = useMemo(() => {
    const keyword = scenarioSearchText.trim().toLowerCase();
    if (!keyword) return scenarios;
    return scenarios.filter((scenario) => `${scenario.name} ${scenario.description}`.toLowerCase().includes(keyword));
  }, [scenarioSearchText, scenarios]);
  const runnableScenarioCount = useMemo(() => scenarios.filter(isRunnableScenario).length, [scenarios]);

  function toggleScenario(scenarioId: string, checked: boolean) {
    setSelectedScenarioIds((current) =>
      checked ? [...new Set([...current, scenarioId])] : current.filter((id) => id !== scenarioId),
    );
  }

  async function saveSuite() {
    if (!suiteName.trim() || !environmentId || selectedScenarioIds.length === 0) return;
    setBusy(true);
    try {
      const payload = {
        name: suiteName.trim(),
        description: suiteDescription.trim(),
        api_environment_id: environmentId,
        scenario_ids: selectedScenarioIds,
      };
      const savedSuite = suite
        ? await updateApiAutomationScenarioSuite(projectId, suite.id, payload)
        : await createApiAutomationScenarioSuite(projectId, payload);
      toast.success(suite ? "测试集已更新" : "测试集已创建");
      onOpenChange(false);
      await onSaved(savedSuite);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "测试集保存失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog onOpenChange={(nextOpen) => !busy && onOpenChange(nextOpen)} open={open}>
      <DialogContent className="grid h-[min(760px,calc(100dvh-2rem))] w-[calc(100vw-2rem)] max-w-none grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:max-w-5xl">
        <DialogHeader className="border-b px-5 py-4 pr-12 sm:px-6 sm:py-5">
          <div className="flex items-start gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/15">
              <Layers3 className="size-[18px]" />
            </div>
            <div className="min-w-0 pt-0.5">
              <DialogTitle className="font-semibold text-lg leading-6">
                {suite ? "编辑测试集" : "新建测试集"}
              </DialogTitle>
              <DialogDescription className="mt-1 max-w-3xl text-pretty leading-5">
                配置运行环境并选择接口场景。同一场景只能加入一次，运行时使用当前已保存的内容。
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="grid min-h-0 overflow-y-auto md:grid-cols-[20rem_minmax(0,1fr)] md:overflow-hidden">
          <FieldGroup className="min-h-0 gap-5 border-b bg-muted/20 p-5 sm:p-6 md:overflow-y-auto md:border-r md:border-b-0">
            <Field>
              <FieldLabel className="font-medium" htmlFor="suite-name">
                测试集名称 <span className="text-destructive">*</span>
              </FieldLabel>
              <Input
                autoFocus
                className="h-10 bg-background px-3"
                disabled={busy}
                id="suite-name"
                maxLength={100}
                onChange={(event) => setSuiteName(event.target.value)}
                placeholder="例如：核心接口冒烟"
                value={suiteName}
              />
            </Field>
            <Field>
              <FieldLabel className="font-medium" htmlFor="suite-environment">
                运行环境 <span className="text-destructive">*</span>
              </FieldLabel>
              <Select
                className="h-10 bg-background px-3"
                disabled={busy}
                id="suite-environment"
                placeholder="请选择运行环境"
                setValue={setEnvironmentId}
                value={environmentId}
              >
                {environments.map((environment) => (
                  <SelectOption key={environment.id} value={environment.id}>
                    {environment.name}
                  </SelectOption>
                ))}
              </Select>
            </Field>
            <Field>
              <div className="flex items-center justify-between gap-3">
                <FieldLabel className="font-medium" htmlFor="suite-description">
                  测试集描述
                </FieldLabel>
                <span className="text-[11px] text-muted-foreground tabular-nums">{suiteDescription.length}/500</span>
              </div>
              <Textarea
                className="min-h-28 resize-none bg-background px-3 py-2.5 leading-6"
                disabled={busy}
                id="suite-description"
                maxLength={500}
                onChange={(event) => setSuiteDescription(event.target.value)}
                placeholder="请输入测试集描述（选填）"
                value={suiteDescription}
              />
            </Field>
          </FieldGroup>

          <section
            className="flex min-h-[30rem] min-w-0 flex-col bg-background md:min-h-0"
            aria-labelledby="suite-scenarios-heading"
          >
            <div className="border-b px-5 py-4 sm:px-6">
              <div className="mb-3 flex items-end justify-between gap-4">
                <div>
                  <h3 className="font-semibold text-sm" id="suite-scenarios-heading">
                    接口场景
                  </h3>
                  <p className="mt-0.5 text-muted-foreground text-xs">{runnableScenarioCount} 个可运行场景</p>
                </div>
                <div className="shrink-0 text-right">
                  <span className="font-semibold text-primary text-sm tabular-nums">{selectedScenarioIds.length}</span>
                  <span className="ml-1 text-muted-foreground text-xs">已选择</span>
                </div>
              </div>
              <div className="relative">
                <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="h-9 bg-muted/20 pr-9 pl-9"
                  disabled={busy}
                  id="suite-scenario-search"
                  onChange={(event) => setScenarioSearchText(event.target.value)}
                  placeholder="搜索场景名称或描述"
                  value={scenarioSearchText}
                />
                {scenarioSearchText ? (
                  <Button
                    aria-label="清除场景搜索"
                    className="absolute top-1/2 right-1.5 -translate-y-1/2 text-muted-foreground"
                    disabled={busy}
                    onClick={() => setScenarioSearchText("")}
                    size="icon-xs"
                    title="清除搜索"
                    type="button"
                    variant="ghost"
                  >
                    <X />
                  </Button>
                ) : null}
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto bg-muted/10 p-3 sm:p-4">
              <div className="space-y-2">
                {filteredScenarios.map((scenario) => {
                  const runnable = isRunnableScenario(scenario);
                  const checked = selectedScenarioIds.includes(scenario.id);
                  const selectedIndex = selectedScenarioIds.indexOf(scenario.id);
                  return (
                    <div
                      className={cn(
                        "group flex items-center gap-3 rounded-lg border px-3 py-3 transition-all duration-200",
                        checked
                          ? "border-primary/35 bg-primary/[0.055] shadow-[0_8px_24px_color-mix(in_srgb,var(--primary),transparent_92%)]"
                          : "border-border/70 bg-background hover:border-primary/25 hover:bg-primary/[0.025]",
                        !runnable && "bg-muted/25 opacity-65 hover:border-border/70 hover:bg-muted/25",
                      )}
                      data-state={checked ? "selected" : undefined}
                      key={scenario.id}
                    >
                      <Checkbox
                        aria-label={`选择场景 ${scenario.name}`}
                        checked={checked}
                        className="after:inset-0"
                        disabled={busy || !runnable}
                        onCheckedChange={(value) => toggleScenario(scenario.id, value === true)}
                      />
                      <button
                        className="flex min-w-0 flex-1 items-center gap-3 rounded-sm text-left outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                        disabled={busy || !runnable}
                        onClick={() => toggleScenario(scenario.id, !checked)}
                        type="button"
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium text-sm">{scenario.name}</span>
                          <span className="mt-1 block truncate text-muted-foreground text-xs">
                            {scenario.description || "暂无场景描述"}
                          </span>
                        </span>
                        <span className="flex shrink-0 items-center gap-2">
                          {runnable ? (
                            <span className="rounded-md border border-border/70 bg-muted/30 px-2 py-1 font-mono text-[11px] text-muted-foreground tabular-nums">
                              v{scenario.revision}
                            </span>
                          ) : (
                            <span className="rounded-md bg-muted px-2 py-1 text-[11px] text-muted-foreground">
                              未保存
                            </span>
                          )}
                          <span
                            className={cn(
                              "flex size-7 items-center justify-center rounded-md font-mono font-semibold text-[11px] tabular-nums transition-colors",
                              checked ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
                            )}
                            title={checked ? `执行顺序 ${selectedIndex + 1}` : "尚未选择"}
                          >
                            {checked ? String(selectedIndex + 1).padStart(2, "0") : "--"}
                          </span>
                        </span>
                      </button>
                    </div>
                  );
                })}
              </div>

              {filteredScenarios.length === 0 ? (
                <div className="flex min-h-64 flex-col items-center justify-center px-6 text-center">
                  <div className="flex size-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                    <Search className="size-[18px]" />
                  </div>
                  <p className="mt-3 font-medium text-sm">
                    {scenarios.length === 0 ? "暂无接口场景" : "未找到匹配场景"}
                  </p>
                  <p className="mt-1 text-muted-foreground text-xs">
                    {scenarios.length === 0 ? "请先创建并保存接口场景。" : "请尝试其他名称或描述。"}
                  </p>
                </div>
              ) : null}
            </div>
          </section>
        </div>

        <DialogFooter className="mx-0 mb-0 flex-row items-center justify-between rounded-none border-t bg-background px-5 py-3 sm:justify-between sm:px-6">
          <p className="min-w-0 truncate text-muted-foreground text-xs">
            已选择 <span className="font-semibold text-foreground tabular-nums">{selectedScenarioIds.length}</span>{" "}
            个场景
          </p>
          <div className="flex shrink-0 items-center gap-2">
            <Button disabled={busy} onClick={() => onOpenChange(false)} type="button" variant="outline">
              取消
            </Button>
            <Button
              className="min-w-28"
              disabled={busy || !suiteName.trim() || !environmentId || selectedScenarioIds.length === 0}
              onClick={saveSuite}
              type="button"
            >
              {busy ? <LoaderCircle className="animate-spin" /> : <Check />}
              {busy ? "保存中" : "保存测试集"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function isRunnableScenario(scenario: ApiAutomationScenario) {
  return scenario.revision > 0 && Boolean(scenario.published_hash);
}
