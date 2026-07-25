"use client";

import { useCallback, useEffect, useState } from "react";

import Link from "next/link";

import { ClipboardCheck, Loader2, Pencil, Plus, X } from "lucide-react";
import { toast } from "@/lib/toast";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
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
  type ApiAutomationCaseSet,
  type ApiProject,
  apiRequest,
  createApiAutomationCaseSet,
  formatDateTime,
  listApiAutomationCaseSets,
  updateApiAutomationCaseSet,
} from "@/lib/api-client";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

type ApiCaseSetForm = {
  name: string;
  projectId: string;
  notes: string;
};

const emptyForm: ApiCaseSetForm = {
  name: "",
  projectId: "",
  notes: "",
};

export default function Page() {
  const selection = useLocalTableSelection<ApiAutomationCaseSet>([]);
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingSet, setEditingSet] = useState<ApiAutomationCaseSet | null>(null);
  const [form, setForm] = useState<ApiCaseSetForm>({ ...emptyForm });

  const activeProjects = projects.filter((project) => project.status === "active");

  const filteredRows = selection.rows.filter((item) =>
    [item.name, item.notes].some((value) => value.toLowerCase().includes(searchText.trim().toLowerCase())),
  );
  const loadCaseSets = useCallback(
    async (nextProjects: ApiProject[]) => {
      const projectIds = nextProjects.filter((project) => project.status === "active").map((project) => project.id);
      if (projectIds.length === 0) {
        selection.setRows([]);
        return;
      }
      const data = await Promise.all(projectIds.map((projectId) => listApiAutomationCaseSets(projectId)));
      selection.setRows(data.flat().sort((first, second) => second.updated_at.localeCompare(first.updated_at)));
    },
    [selection.setRows],
  );

  useEffect(() => {
    async function loadInitialData() {
      setLoading(true);
      try {
        const nextProjects = await apiRequest<ApiProject[]>("/projects");
        setProjects(nextProjects);
        await loadCaseSets(nextProjects);
      } catch (requestError) {
        toast.error(requestError instanceof Error ? requestError.message : "接口自动化数据加载失败");
      } finally {
        setLoading(false);
      }
    }

    void loadInitialData();
  }, [loadCaseSets]);

  function openCreateDialog() {
    setEditingSet(null);
    setForm({ ...emptyForm, projectId: activeProjects[0]?.id ?? "" });
    setDialogOpen(true);
  }

  function openEditDialog(item: ApiAutomationCaseSet) {
    setEditingSet(item);
    setForm({ name: item.name, projectId: item.project_id, notes: item.notes });
    setDialogOpen(true);
  }

  async function saveApiCaseSet() {
    if (!form.name.trim()) {
      toast.error("请填写接口集名称");
      return;
    }
    if (!form.projectId) {
      toast.error("请选择项目");
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        notes: form.notes.trim(),
      };
      const saved = editingSet
        ? await updateApiAutomationCaseSet(editingSet.project_id, editingSet.id, payload)
        : await createApiAutomationCaseSet(form.projectId, payload);
      selection.setRows((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      setDialogOpen(false);
      setEditingSet(null);
      toast.success(editingSet ? "接口集已修改" : "接口集已创建");
    } catch (requestError) {
      toast.error(
        requestError instanceof Error ? requestError.message : editingSet ? "接口集修改失败" : "接口集创建失败",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageShell breadcrumbs={moduleBreadcrumbs("apiAutomation")} description="查看和维护接口集。" title="接口自动化">
      <ShellSection>
        <ListToolbar
          createLabel="新建接口集"
          onCreate={openCreateDialog}
          onSearch={setSearchText}
          placeholder="搜索接口集或备注"
          selectedCount={selection.selectedCount}
          title="接口集列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部接口用例集"
                    checked={selection.allSelected || (selection.partiallySelected ? "indeterminate" : false)}
                    disabled={loading}
                    onCheckedChange={(checked) => selection.toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>接口集名称</TableHead>
                <TableHead>备注</TableHead>
                <TableHead>接口数量</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? <TableLoadingRow colSpan={6} label="接口集加载中" /> : null}
              {!loading
                ? filteredRows.map((item) => (
                    <TableRow
                      data-state={selection.selectedIds.includes(item.id) ? "selected" : undefined}
                      key={item.id}
                    >
                      <TableCell>
                        <Checkbox
                          aria-label={`选择 ${item.name}`}
                          checked={selection.selectedIds.includes(item.id)}
                          onCheckedChange={(checked) => selection.toggleOne(item.id, Boolean(checked))}
                        />
                      </TableCell>
                      <TableCell className="font-medium">
                        <Link
                          className="block truncate hover:underline"
                          href={`/projects/${item.project_id}/automation/api?set=${item.id}`}
                          title={item.name}
                        >
                          {item.name}
                        </Link>
                      </TableCell>
                      <TableCell className="max-w-80 truncate text-muted-foreground">{item.notes || "-"}</TableCell>
                      <TableCell>{item.endpoint_count}</TableCell>
                      <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                      <TableCell>
                        <RowActions
                          actions={[
                            {
                              label: "查看",
                              icon: ClipboardCheck,
                              href: `/projects/${item.project_id}/automation/api?set=${item.id}`,
                            },
                            {
                              label: "修改",
                              icon: Pencil,
                              onSelect: () => openEditDialog(item),
                            },
                          ]}
                          label={`打开 ${item.name} 操作菜单`}
                        />
                      </TableCell>
                    </TableRow>
                  ))
                : null}
              {!loading && filteredRows.length === 0 ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
                    暂无接口集。可新建接口集后进入详情维护接口资产。
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </ShellSection>
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:max-w-3xl">
          <DialogHeader className="shrink-0 gap-3 px-6 pt-6">
            <DialogTitle>{editingSet ? "修改接口集" : "新建接口集"}</DialogTitle>
            <DialogDescription>填写名称、选择所属项目并补充备注。</DialogDescription>
          </DialogHeader>
          <FieldGroup className="grid min-h-0 gap-x-6 gap-y-5 overflow-y-auto px-6 py-5 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="api-case-set-name">接口集名称</FieldLabel>
              <Input
                id="api-case-set-name"
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                value={form.name}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="api-case-set-project">项目</FieldLabel>
              <Select
                disabled={Boolean(editingSet)}
                placeholder="选择项目"
                setValue={(value) => setForm((current) => ({ ...current, projectId: value }))}
                value={form.projectId}
              >
                {activeProjects.map((project) => (
                  <SelectOption key={project.id} value={project.id}>
                    {project.name}
                  </SelectOption>
                ))}
              </Select>
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="api-case-set-notes">备注</FieldLabel>
              <Textarea
                className="min-h-20"
                id="api-case-set-notes"
                onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                placeholder="补充说明接口集的范围、目标或维护约定"
                value={form.notes}
              />
            </Field>
          </FieldGroup>
          <DialogFooter className="m-0 shrink-0 px-6 py-4">
            <Button onClick={() => setDialogOpen(false)} type="button" variant="outline">
              <X className="size-4" />
              取消
            </Button>
            <Button disabled={saving} onClick={saveApiCaseSet} type="button">
              {saving ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
              {editingSet ? "保存" : "创建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
