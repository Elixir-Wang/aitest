"use client";

import { useCallback, useEffect, useState } from "react";

import Link from "next/link";

import { Eye, Pencil, Trash2 } from "lucide-react";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
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
import { apiRequest, formatDateTime, type ApiProject } from "@/lib/api-client";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";

type ProjectRow = ApiProject;
const statusOptions = ["活跃", "归档"];
const statusToLabel = (status: ProjectRow["status"]) => (status === "archived" ? "归档" : "活跃");
const labelToStatus = (label: string): ProjectRow["status"] => (label === "归档" ? "archived" : "active");

const emptyForm = {
  description: "",
  name: "",
  status: "活跃",
};

export default function Page() {
  const { allSelected, partiallySelected, rows, selectedCount, selectedIds, setRows, toggleAll, toggleOne } =
    useLocalTableSelection<ProjectRow>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<ProjectRow | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((project) =>
    [project.name, project.description, statusToLabel(project.status), project.updated_at].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );
  const canWrite = rows.some((project) => project.available_actions.includes("create"));

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRows(await apiRequest<ProjectRow[]>("/projects"));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "项目列表加载失败");
    } finally {
      setLoading(false);
    }
  }, [setRows]);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

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
      setDialogOpen(false);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "项目保存失败");
    }
  }

  async function deleteProjects(ids: string[]) {
    setError("");
    try {
      await Promise.all(ids.map((id) => apiRequest(`/projects/${id}`, { method: "DELETE" })));
      await loadProjects();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "项目删除失败");
    }
  }

  return (
    <PageShell
      breadcrumbs={["项目工作区", "项目"]}
      description="管理项目、成员、环境配置和测试资产健康度。"
      projectScope="all"
      title="项目"
    >
      <ShellSection>
        {error ? <div className="mb-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">{error}</div> : null}
        <ListToolbar
          createLabel="新建项目"
          onBatchDelete={canWrite ? () => deleteProjects(selectedIds) : undefined}
          onCreate={canWrite ? openCreateDialog : undefined}
          onSearch={setSearchText}
          placeholder="搜索项目名称、编码或描述"
          selectedCount={canWrite ? selectedCount : 0}
          title="项目列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部项目"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    disabled={!canWrite || loading}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>项目名称</TableHead>
                <TableHead>项目描述</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>最近更新时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRows.map((project) => (
                <TableRow data-state={selectedIds.includes(project.id) ? "selected" : undefined} key={project.id}>
                  <TableCell>
                    <Checkbox
                      aria-label={`选择 ${project.name}`}
                      checked={selectedIds.includes(project.id)}
                      disabled={!project.available_actions.includes("delete")}
                      onCheckedChange={(checked) => toggleOne(project.id, Boolean(checked))}
                    />
                  </TableCell>
                  <TableCell className="font-medium">
                    <Link className="hover:underline" href={`/projects/${project.id}`}>
                      {project.name}
                    </Link>
                  </TableCell>
                  <TableCell className="max-w-md text-muted-foreground">{project.description}</TableCell>
                  <TableCell>
                    <Badge variant={project.status === "archived" ? "outline" : "secondary"}>
                      {statusToLabel(project.status)}
                    </Badge>
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
                          onSelect: project.available_actions.includes("update") ? () => openEditDialog(project) : undefined,
                        },
                        {
                          label: "删除",
                          destructive: true,
                          disabled: !project.available_actions.includes("delete"),
                          icon: Trash2,
                          onSelect: project.available_actions.includes("delete") ? () => deleteProjects([project.id]) : undefined,
                        },
                      ]}
                      label={`打开 ${project.name} 操作菜单`}
                    />
                  </TableCell>
                </TableRow>
              ))}
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
