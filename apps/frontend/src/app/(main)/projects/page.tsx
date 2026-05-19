"use client";

import { useState } from "react";

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
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";

const projects = [
  {
    id: "zhiliao",
    name: "知了平台",
    description: "承载需求、探索、知识库和测试资产链路。",
    status: "活跃",
    updated: "2026-05-19 14:30:00",
  },
  {
    id: "hawk",
    name: "鹰眼平台",
    description: "用于验证跨项目任务、报告和自动化执行流程。",
    status: "活跃",
    updated: "2026-05-18 10:15:00",
  },
  {
    id: "atlas",
    name: "Atlas 内测",
    description: "归档项目，保留历史需求和用例资产。",
    status: "归档",
    updated: "2026-05-11 09:00:00",
  },
];

type ProjectRow = (typeof projects)[number];
const statusOptions = ["活跃", "归档"];

const emptyForm = {
  description: "",
  name: "",
  status: "活跃",
};

function nowText() {
  const now = new Date();
  const pad = (value: number) => value.toString().padStart(2, "0");

  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}

function projectIdFromName(name: string) {
  return `project-${Date.now()}-${
    name
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "new"
  }`;
}

export default function Page() {
  const {
    addRow,
    allSelected,
    deleteOne,
    deleteSelected,
    partiallySelected,
    rows,
    selectedCount,
    selectedIds,
    toggleAll,
    toggleOne,
    updateRow,
  } = useLocalTableSelection(projects);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<ProjectRow | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((project) =>
    [project.name, project.description, project.status, project.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

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
      status: project.status,
    });
    setDialogOpen(true);
  }

  function submitProject() {
    const name = form.name.trim();

    if (!name) {
      return;
    }

    const row = {
      description: form.description.trim(),
      id: editingProject?.id ?? projectIdFromName(name),
      name,
      status: form.status,
      updated: nowText(),
    };

    if (editingProject) {
      updateRow(row);
    } else {
      addRow(row);
    }

    setDialogOpen(false);
  }

  return (
    <PageShell
      breadcrumbs={["项目工作区", "项目"]}
      description="管理项目、成员、环境配置和测试资产健康度。"
      projectScope="all"
      title="项目"
    >
      <ShellSection>
        <ListToolbar
          createLabel="新建项目"
          onBatchDelete={deleteSelected}
          onCreate={openCreateDialog}
          onSearch={setSearchText}
          placeholder="搜索项目名称、编码或负责人"
          selectedCount={selectedCount}
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
                    <Badge variant={project.status === "归档" ? "outline" : "secondary"}>{project.status}</Badge>
                  </TableCell>
                  <TableCell>{project.updated}</TableCell>
                  <TableCell>
                    <RowActions
                      actions={[
                        { label: "概览", href: `/projects/${project.id}`, icon: Eye },
                        { label: "编辑", icon: Pencil, onSelect: () => openEditDialog(project) },
                        { label: "删除", destructive: true, icon: Trash2, onSelect: () => deleteOne(project.id) },
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
