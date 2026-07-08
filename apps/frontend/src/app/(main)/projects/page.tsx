"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import Link from "next/link";

import { Eye, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";

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
import { projectStatusTone, StatusBadge } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { type ApiProject, apiRequest, formatDateTime } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectContextStore } from "@/stores/project-context-store";

type ProjectRow = ApiProject;
const PROJECT_LIST_CHANGED_EVENT = "ai-testing:project-list-changed";
const statusOptions = ["活跃", "归档"];
const statusToLabel = (status: ProjectRow["status"]) => (status === "archived" ? "归档" : "活跃");
const labelToStatus = (label: string): ProjectRow["status"] => (label === "归档" ? "archived" : "active");

const emptyForm = {
  description: "",
  name: "",
  status: "活跃",
};

export default function Page() {
  const currentUser = useAuthStore((state) => state.user);
  const { currentProjectId, hydrate, hasHydrated, scope } = useProjectContextStore();
  const { clearSelection, rows, selectedIds, setRows, toggleAll, toggleOne } = useLocalTableSelection<ProjectRow>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<ProjectRow | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState("");
  const visibleRows =
    scope === "project" && currentProjectId && hasHydrated
      ? rows.filter((project) => project.id === currentProjectId)
      : rows;
  const visibleRowIds = visibleRows.map((project) => project.id);
  const visibleSelectedIds = selectedIds.filter((id) => visibleRowIds.includes(id));
  const visibleSelectedCount = visibleSelectedIds.length;
  const allSelected = visibleRowIds.length > 0 && visibleSelectedCount === visibleRowIds.length;
  const partiallySelected = visibleSelectedCount > 0 && visibleSelectedCount < visibleRowIds.length;
  const filteredRows = visibleRows.filter((project) =>
    [project.name, project.description, statusToLabel(project.status), project.updated_at].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );
  const canWrite = currentUser?.role === "admin";

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRows(await apiRequest<ProjectRow[]>("/projects"));
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "项目列表加载失败",
        actionLabel: "加载项目列表",
        method: "GET",
        path: "/projects",
      });
      setError(requestError instanceof Error ? requestError.message : "项目列表加载失败");
    } finally {
      setLoading(false);
    }
  }, [setRows]);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    void currentProjectId;
    void scope;
    clearSelection();
  }, [clearSelection, currentProjectId, scope]);

  function openCreateDialog() {
    setEditingProject(null);
    setForm(emptyForm);
    setDialogOpen(true);
  }

  function openEditDialog(project: ProjectRow) {
    setEditingProject(project);
    setForm({
      description: project.description,
      name: project.name,
      status: statusToLabel(project.status),
    });
    setDialogOpen(true);
  }

  async function submitProject() {
    const name = form.name.trim();

    if (!name) {
      return;
    }

    const payload = {
      description: form.description.trim(),
      name,
      status: labelToStatus(form.status),
    };

    try {
      if (editingProject) {
        await apiRequest<ProjectRow>(`/projects/${editingProject.id}`, {
          body: JSON.stringify(payload),
          method: "PATCH",
        });
      } else {
        await apiRequest<ProjectRow>("/projects", {
          body: JSON.stringify(payload),
          method: "POST",
        });
      }
      await loadProjects();
      window.dispatchEvent(new Event(PROJECT_LIST_CHANGED_EVENT));
      setDialogOpen(false);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "项目保存失败",
        actionLabel: editingProject ? "编辑项目" : "新建项目",
        method: editingProject ? "PATCH" : "POST",
        path: editingProject ? `/projects/${editingProject.id}` : "/projects",
      });
      setError(requestError instanceof Error ? requestError.message : "项目保存失败");
    }
  }

  async function deleteProjects(ids: string[]) {
    setError("");
    try {
      await Promise.all(ids.map((id) => apiRequest(`/projects/${id}`, { method: "DELETE" })));
      clearSelection();
      await loadProjects();
      window.dispatchEvent(new Event(PROJECT_LIST_CHANGED_EVENT));
      toast.success(`已删除 ${ids.length} 个项目`);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "项目删除失败",
        actionLabel: "删除项目",
        method: "DELETE",
        path: "/projects/{id}",
      });
    }
  }

  return (
    <PageShell
      breadcrumbs={[{ label: "项目工作区" }, { label: "项目" }]}
      description="管理项目、成员、环境配置和测试资产健康度。"
      projectScope="all"
      title="项目"
    >
      <ShellSection>
        {error ? (
          <div className="mb-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">
            {error}
          </div>
        ) : null}
        <ListToolbar
          createLabel="新建项目"
          onBatchDelete={canWrite ? () => deleteProjects(visibleSelectedIds) : undefined}
          onCreate={canWrite ? openCreateDialog : undefined}
          onSearch={setSearchText}
          placeholder="搜索项目名称、编码或描述"
          selectedCount={canWrite ? visibleSelectedCount : 0}
          title="项目列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table className="table-fixed">
            <TableHeader>
              <TableRow>
                <TableHead className="w-[6%]">
                  <Checkbox
                    aria-label="选择全部项目"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    disabled={!canWrite || loading}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead className="w-[20%]">项目名称</TableHead>
                <TableHead className="w-[30%]">项目描述</TableHead>
                <TableHead className="w-[10%]">状态</TableHead>
                <TableHead className="w-[26%]">更新时间</TableHead>
                <TableHead className="w-[8%]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRows.map((project) => (
                <TableRow data-state={selectedIds.includes(project.id) ? "selected" : undefined} key={project.id}>
                  <TableCell>
                    <Checkbox
                      aria-label={`选择 ${project.name}`}
                      checked={selectedIds.includes(project.id)}
                      disabled={!canWrite}
                      onCheckedChange={(checked) => toggleOne(project.id, Boolean(checked))}
                    />
                  </TableCell>
                  <TableCell className="font-medium">
                    <Link
                      className="block truncate hover:underline"
                      href={`/projects/${project.id}`}
                      title={project.name}
                    >
                      {project.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    <OverflowTooltipText value={project.description} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge tone={projectStatusTone(project.status)}>{statusToLabel(project.status)}</StatusBadge>
                  </TableCell>
                  <TableCell>{formatDateTime(project.updated_at)}</TableCell>
                  <TableCell>
                    <RowActions
                      actions={[
                        { label: "概览", href: `/projects/${project.id}`, icon: Eye },
                        {
                          label: "编辑",
                          disabled: !project.available_actions.includes("update"),
                          icon: Pencil,
                          onSelect: project.available_actions.includes("update")
                            ? () => openEditDialog(project)
                            : undefined,
                        },
                        {
                          label: "删除",
                          destructive: true,
                          disabled: !canWrite,
                          icon: Trash2,
                          onSelect: canWrite ? () => deleteProjects([project.id]) : undefined,
                        },
                      ]}
                      label={`打开 ${project.name} 操作菜单`}
                    />
                  </TableCell>
                </TableRow>
              ))}
              {loading && filteredRows.length === 0 ? <TableLoadingRow colSpan={6} label="项目列表加载中" /> : null}
              {!loading && filteredRows.length === 0 ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
                    暂无项目。新建项目后，可在项目工作区维护需求、探索和测试资产。
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </ShellSection>
      <Dialog onOpenChange={setDialogOpen} open={dialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingProject ? "编辑项目" : "新建项目"}</DialogTitle>
            <DialogDescription>本地维护项目名称、状态和描述信息。</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="project-name">项目名称</FieldLabel>
              <Input
                id="project-name"
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="请输入项目名称"
                value={form.name}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="project-status">项目状态</FieldLabel>
              <Select
                id="project-status"
                placeholder="选择项目状态"
                setValue={(value) => setForm((current) => ({ ...current, status: value }))}
                value={form.status}
              >
                {statusOptions.map((status) => (
                  <SelectOption key={status} value={status}>
                    {status}
                  </SelectOption>
                ))}
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="project-description">项目描述</FieldLabel>
              <Textarea
                id="project-description"
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="请输入项目描述"
                value={form.description}
              />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button onClick={() => setDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={!form.name.trim()} onClick={submitProject} type="button">
              {editingProject ? "保存" : "新建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}

function OverflowTooltipText({ value }: { value: string }) {
  const textRef = useRef<HTMLSpanElement>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);

  useEffect(() => {
    const node = textRef.current;
    if (!node) {
      return;
    }

    const updateOverflowState = () => {
      setIsOverflowing(node.scrollWidth > node.clientWidth);
    };

    updateOverflowState();
    const resizeObserver = new ResizeObserver(updateOverflowState);
    resizeObserver.observe(node);
    return () => resizeObserver.disconnect();
  });

  const content = (
    <span ref={textRef} className="block truncate">
      {value}
    </span>
  );

  if (!value || !isOverflowing) {
    return content;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{content}</TooltipTrigger>
      <TooltipContent className="max-w-sm whitespace-normal break-words leading-relaxed">{value}</TooltipContent>
    </Tooltip>
  );
}
