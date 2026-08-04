"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Pencil, Trash2 } from "lucide-react";

import { ListToolbar, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  type ApiAutomationEnvironment,
  type ApiAutomationScenario,
  createApiAutomationScenario,
  deleteApiAutomationScenario,
  formatDateTime,
  listApiAutomationEnvironments,
  listApiAutomationScenarios,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";

type ApiScenarioListProps = {
  projectId: string;
};

export function ApiScenarioList({ projectId }: ApiScenarioListProps) {
  const router = useRouter();
  const [scenarios, setScenarios] = useState<ApiAutomationScenario[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [loadingEnvironments, setLoadingEnvironments] = useState(false);
  const [environments, setEnvironments] = useState<ApiAutomationEnvironment[]>([]);
  const [scenarioName, setScenarioName] = useState("");
  const [scenarioDescription, setScenarioDescription] = useState("");
  const [environmentId, setEnvironmentId] = useState("");

  const loadScenarios = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await listApiAutomationScenarios(projectId);
      setScenarios(rows);
      setSelectedIds((current) => current.filter((id) => rows.some((scenario) => scenario.id === id)));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "场景列表加载失败");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void loadScenarios();
  }, [loadScenarios]);

  useEffect(() => {
    if (!createDialogOpen) return;

    let cancelled = false;
    setLoadingEnvironments(true);
    listApiAutomationEnvironments(projectId)
      .then((rows) => {
        if (cancelled) return;
        setEnvironments(rows);
        setEnvironmentId(rows[0]?.id ?? "");
      })
      .catch((error) => toast.error(error instanceof Error ? error.message : "环境加载失败"))
      .finally(() => {
        if (!cancelled) setLoadingEnvironments(false);
      });

    return () => {
      cancelled = true;
    };
  }, [createDialogOpen, projectId]);

  const filteredRows = useMemo(() => {
    const keyword = searchText.trim().toLowerCase();
    if (!keyword) return scenarios;
    return scenarios.filter((scenario) => `${scenario.name} ${scenario.description}`.toLowerCase().includes(keyword));
  }, [scenarios, searchText]);

  const visibleIds = filteredRows.map((scenario) => scenario.id);
  const visibleSelectedIds = visibleIds.filter((id) => selectedIds.includes(id));
  const allSelected = visibleIds.length > 0 && visibleSelectedIds.length === visibleIds.length;
  const partiallySelected = visibleSelectedIds.length > 0 && !allSelected;

  function toggleOne(scenarioId: string, checked: boolean) {
    setSelectedIds((current) =>
      checked ? [...new Set([...current, scenarioId])] : current.filter((id) => id !== scenarioId),
    );
  }

  function toggleAll(checked: boolean) {
    setSelectedIds((current) =>
      checked ? [...new Set([...current, ...visibleIds])] : current.filter((id) => !visibleIds.includes(id)),
    );
  }

  function openCreateDialog() {
    setScenarioName("");
    setScenarioDescription("");
    setEnvironmentId("");
    setEnvironments([]);
    setCreateDialogOpen(true);
  }

  async function createScenario() {
    const name = scenarioName.trim();
    if (!name || !environmentId) return;

    setCreating(true);
    try {
      const scenario = await createApiAutomationScenario(projectId, {
        name,
        description: scenarioDescription.trim(),
      });
      setCreateDialogOpen(false);
      router.push(
        `/projects/${projectId}/automation/api/scenarios/${scenario.id}?environmentId=${encodeURIComponent(environmentId)}`,
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "场景创建失败");
    } finally {
      setCreating(false);
    }
  }

  async function deleteScenarios(ids: string[]) {
    if (ids.length === 0) return;
    setBusy(true);
    try {
      await Promise.all(ids.map((scenarioId) => deleteApiAutomationScenario(projectId, scenarioId)));
      setSelectedIds([]);
      await loadScenarios();
      toast.success(`已删除 ${ids.length} 个场景`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "场景删除失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ShellSection>
      <ListToolbar
        createDisabled={busy || creating}
        createLabel="新建场景"
        onBatchDelete={busy ? undefined : () => deleteScenarios(visibleSelectedIds)}
        onCreate={openCreateDialog}
        onSearch={setSearchText}
        placeholder="搜索场景名称或描述"
        selectedCount={visibleSelectedIds.length}
        title="场景列表"
      />
      <div className="overflow-hidden rounded-lg border">
        <Table className="table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead className="w-[6%]">
                <Checkbox
                  aria-label="选择全部场景"
                  checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                  disabled={busy || loading}
                  onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                />
              </TableHead>
              <TableHead className="w-[22%]">场景名称</TableHead>
              <TableHead className="w-[31%]">描述</TableHead>
              <TableHead className="w-[12%]">步骤数</TableHead>
              <TableHead className="w-[21%]">更新时间</TableHead>
              <TableHead className="w-[8%]">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredRows.map((scenario) => {
              const editorHref = `/projects/${projectId}/automation/api/scenarios/${scenario.id}`;
              return (
                <TableRow data-state={selectedIds.includes(scenario.id) ? "selected" : undefined} key={scenario.id}>
                  <TableCell>
                    <Checkbox
                      aria-label={`选择 ${scenario.name}`}
                      checked={selectedIds.includes(scenario.id)}
                      disabled={busy}
                      onCheckedChange={(checked) => toggleOne(scenario.id, Boolean(checked))}
                    />
                  </TableCell>
                  <TableCell className="font-medium">
                    <Link className="block truncate hover:underline" href={editorHref} title={scenario.name}>
                      {scenario.name}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <span className="block truncate text-muted-foreground" title={scenario.description}>
                      {scenario.description || "-"}
                    </span>
                  </TableCell>
                  <TableCell>{scenario.steps.length}</TableCell>
                  <TableCell>{formatDateTime(scenario.updated_at)}</TableCell>
                  <TableCell>
                    <RowActions
                      actions={[
                        { label: "编辑", href: editorHref, icon: Pencil },
                        {
                          label: "删除",
                          destructive: true,
                          disabled: busy,
                          icon: Trash2,
                          onSelect: busy ? undefined : () => deleteScenarios([scenario.id]),
                        },
                      ]}
                      label={`打开 ${scenario.name} 操作菜单`}
                    />
                  </TableCell>
                </TableRow>
              );
            })}
            {loading && filteredRows.length === 0 ? <TableLoadingRow colSpan={6} label="场景列表加载中" /> : null}
            {!loading && filteredRows.length === 0 ? (
              <TableRow>
                <TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
                  暂无场景。新建场景后，可组合接口并保存版本运行。
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>
      <Dialog
        onOpenChange={(open) => {
          if (!creating) setCreateDialogOpen(open);
        }}
        open={createDialogOpen}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>新建场景</DialogTitle>
            <DialogDescription>填写场景基本信息，创建后进入画布编排步骤。</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="scenario-name">场景名称</FieldLabel>
              <Input
                autoFocus
                disabled={creating}
                id="scenario-name"
                maxLength={100}
                onChange={(event) => setScenarioName(event.target.value)}
                placeholder="请输入场景名称"
                value={scenarioName}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="scenario-environment">运行环境</FieldLabel>
              <Select
                disabled={loadingEnvironments || creating}
                id="scenario-environment"
                placeholder={loadingEnvironments ? "加载环境中..." : "请选择运行环境"}
                setValue={setEnvironmentId}
                value={environmentId}
              >
                {environments.map((environment) => (
                  <SelectOption key={environment.id} value={environment.id}>
                    {environment.name}
                  </SelectOption>
                ))}
              </Select>
              {!loadingEnvironments && environments.length === 0 ? (
                <p className="text-muted-foreground text-xs">暂无可用环境，请先在接口环境中创建环境。</p>
              ) : null}
            </Field>
            <Field>
              <FieldLabel htmlFor="scenario-description">场景描述</FieldLabel>
              <Textarea
                disabled={creating}
                id="scenario-description"
                maxLength={500}
                onChange={(event) => setScenarioDescription(event.target.value)}
                placeholder="请输入场景描述（选填）"
                value={scenarioDescription}
              />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button disabled={creating} onClick={() => setCreateDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button
              disabled={creating || loadingEnvironments || !scenarioName.trim() || !environmentId}
              onClick={createScenario}
              type="button"
            >
              {creating ? "创建中..." : "新建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ShellSection>
  );
}
