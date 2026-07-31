"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Pencil, Trash2 } from "lucide-react";

import { ListToolbar, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type ApiAutomationScenario,
  deleteApiAutomationScenario,
  formatDateTime,
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
        createDisabled={busy}
        createLabel="新建场景"
        onBatchDelete={busy ? undefined : () => deleteScenarios(visibleSelectedIds)}
        onCreate={() => router.push(`/projects/${projectId}/automation/api/scenarios/new`)}
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
              <TableHead className="w-[20%]">场景名称</TableHead>
              <TableHead className="w-[27%]">描述</TableHead>
              <TableHead className="w-[10%]">步骤数</TableHead>
              <TableHead className="w-[14%]">状态</TableHead>
              <TableHead className="w-[15%]">更新时间</TableHead>
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
                  <TableCell>
                    <Badge variant="outline">{scenarioStatusLabel(scenario)}</Badge>
                  </TableCell>
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
            {loading && filteredRows.length === 0 ? <TableLoadingRow colSpan={7} label="场景列表加载中" /> : null}
            {!loading && filteredRows.length === 0 ? (
              <TableRow>
                <TableCell className="h-24 text-center text-muted-foreground" colSpan={7}>
                  暂无场景。新建场景后，可组合接口并保存版本运行。
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>
    </ShellSection>
  );
}

function scenarioStatusLabel(scenario: ApiAutomationScenario) {
  if (scenario.status === "ready") return `当前 v${scenario.revision}`;
  if (scenario.status === "archived") return "已归档";
  return "尚无版本";
}
