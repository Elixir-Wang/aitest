"use client";

import { useCallback, useEffect, useState } from "react";

import { useParams } from "next/navigation";

import { Pencil, Plus, Star, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
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
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { type ApiProject, type ApiProjectVersion, apiRequest, formatDateTime } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { useAuthStore } from "@/stores/auth-store";

const emptyForm = {
  version: "",
  name: "",
  description: "",
  plannedReleaseAt: "",
  setAsDefault: true,
};

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const currentUser = useAuthStore((state) => state.user);
  const canWrite = currentUser?.role === "admin";
  const [project, setProject] = useState<ApiProject | null>(null);
  const [versions, setVersions] = useState<ApiProjectVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<ApiProjectVersion | null>(null);
  const [pendingDelete, setPendingDelete] = useState<ApiProjectVersion | null>(null);
  const [form, setForm] = useState(emptyForm);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [projects, nextVersions] = await Promise.all([
        apiRequest<ApiProject[]>("/projects"),
        apiRequest<ApiProjectVersion[]>(`/projects/${projectId}/versions`),
      ]);
      setProject(projects.find((item) => item.id === projectId) ?? null);
      setVersions(nextVersions);
    } catch (error) {
      reportError(error, {
        fallbackMessage: "项目版本加载失败",
        actionLabel: "加载项目版本",
        method: "GET",
        path: `/projects/${projectId}/versions`,
      });
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  function openCreate() {
    setEditing(null);
    setForm({ ...emptyForm, version: suggestNextVersion(versions) });
    setDialogOpen(true);
  }

  function openEdit(version: ApiProjectVersion) {
    setEditing(version);
    setForm({
      version: version.version,
      name: version.name,
      description: version.description,
      plannedReleaseAt: version.planned_release_at ?? "",
      setAsDefault: version.is_default,
    });
    setDialogOpen(true);
  }

  async function submit() {
    if (!editing && !/^\d+\.\d+\.\d+$/.test(form.version.trim())) {
      toast.error("版本号必须使用 MAJOR.MINOR.PATCH 格式");
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        await apiRequest(`/projects/${projectId}/versions/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify({
            name: form.name.trim(),
            description: form.description.trim(),
            planned_release_at: form.plannedReleaseAt || null,
          }),
        });
        toast.success("版本信息已更新");
      } else {
        await apiRequest(`/projects/${projectId}/versions`, {
          method: "POST",
          body: JSON.stringify({
            version: form.version.trim(),
            name: form.name.trim(),
            description: form.description.trim(),
            planned_release_at: form.plannedReleaseAt || null,
            set_as_default: form.setAsDefault,
          }),
        });
        toast.success("项目版本已创建");
      }
      setDialogOpen(false);
      await load();
    } catch (error) {
      reportError(error, {
        fallbackMessage: "项目版本保存失败",
        actionLabel: editing ? "编辑项目版本" : "创建项目版本",
        method: editing ? "PATCH" : "POST",
        path: editing ? `/projects/${projectId}/versions/${editing.id}` : `/projects/${projectId}/versions`,
      });
    } finally {
      setSaving(false);
    }
  }

  async function setDefault(version: ApiProjectVersion) {
    try {
      await apiRequest(`/projects/${projectId}/versions/${version.id}/set-default`, { method: "POST" });
      toast.success(`当前版本已切换为 ${version.version}`);
      await load();
    } catch (error) {
      reportError(error, {
        fallbackMessage: "当前版本切换失败",
        actionLabel: "设置当前版本",
        method: "POST",
        path: `/projects/${projectId}/versions/${version.id}/set-default`,
      });
    }
  }

  async function deleteVersion() {
    if (!pendingDelete) return;
    try {
      await apiRequest(`/projects/${projectId}/versions/${pendingDelete.id}`, { method: "DELETE" });
      toast.success(`版本 ${pendingDelete.version} 已删除`);
      setPendingDelete(null);
      await load();
    } catch (error) {
      reportError(error, {
        fallbackMessage: "项目版本删除失败",
        actionLabel: "删除项目版本",
        method: "DELETE",
        path: `/projects/${projectId}/versions/${pendingDelete.id}`,
      });
    }
  }

  const projectName = project?.name ?? "项目";

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs(
        "projects",
        { label: projectName, href: `/projects/${projectId}` },
        { label: "版本管理" },
      )}
      description="维护项目版本及新需求默认归属。"
      projectScope="project"
      activeTab="版本管理"
      tabs={[
        { label: "项目概览", href: `/projects/${projectId}` },
        { label: "版本管理", href: `/projects/${projectId}/versions` },
        { label: "项目设置", href: `/projects/${projectId}/settings` },
      ]}
      title="版本管理"
    >
      <ShellSection>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-medium text-sm">项目版本</h2>
            <p className="text-muted-foreground text-xs">当前版本会作为新需求的默认所属版本。</p>
          </div>
          {canWrite ? (
            <Button onClick={openCreate}>
              <Plus className="size-4" />
              创建版本
            </Button>
          ) : null}
        </div>
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>版本号</TableHead>
                <TableHead>版本名称</TableHead>
                <TableHead>需求数</TableHead>
                <TableHead>计划日期</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {versions.map((version) => (
                <TableRow key={version.id}>
                  <TableCell>
                    <div className="flex items-center gap-2 font-medium">
                      {version.version}
                      {version.is_default ? <Badge variant="secondary">当前</Badge> : null}
                    </div>
                  </TableCell>
                  <TableCell>{version.name || "-"}</TableCell>
                  <TableCell>{version.requirement_count}</TableCell>
                  <TableCell>{version.planned_release_at || "-"}</TableCell>
                  <TableCell>{formatDateTime(version.created_at)}</TableCell>
                  <TableCell>
                    <RowActions
                      actions={[
                        {
                          label: "编辑",
                          icon: Pencil,
                          disabled: !canWrite,
                          onSelect: canWrite ? () => openEdit(version) : undefined,
                        },
                        {
                          label: "设为当前版本",
                          icon: Star,
                          disabled: !canWrite || version.is_default,
                          onSelect: canWrite && !version.is_default ? () => setDefault(version) : undefined,
                        },
                        {
                          label: "删除",
                          icon: Trash2,
                          destructive: true,
                          disabled: !canWrite || version.is_default || version.requirement_count > 0,
                          onSelect:
                            canWrite && !version.is_default && version.requirement_count === 0
                              ? () => setPendingDelete(version)
                              : undefined,
                        },
                      ]}
                      label={`打开 ${version.version} 操作菜单`}
                    />
                  </TableCell>
                </TableRow>
              ))}
              {loading && versions.length === 0 ? <TableLoadingRow colSpan={6} label="项目版本加载中" /> : null}
              {!loading && versions.length === 0 ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
                    当前项目暂无版本。
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </ShellSection>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{editing ? `编辑 ${editing.version}` : "创建项目版本"}</DialogTitle>
            <DialogDescription>版本号创建后不可修改，名称和计划信息可随时维护。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Field>
              <FieldLabel htmlFor="project-version-number">版本号</FieldLabel>
              <Input
                disabled={Boolean(editing)}
                id="project-version-number"
                placeholder="例如 1.1.0"
                value={form.version}
                onChange={(event) => setForm((current) => ({ ...current, version: event.target.value }))}
              />
              <FieldDescription>使用 MAJOR.MINOR.PATCH 三段格式。</FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="project-version-name">版本名称</FieldLabel>
              <Input
                id="project-version-name"
                placeholder="例如 会员能力升级"
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="project-version-date">计划日期</FieldLabel>
              <Input
                id="project-version-date"
                type="date"
                value={form.plannedReleaseAt}
                onChange={(event) => setForm((current) => ({ ...current, plannedReleaseAt: event.target.value }))}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="project-version-description">版本说明</FieldLabel>
              <Textarea
                id="project-version-description"
                rows={4}
                value={form.description}
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
              />
            </Field>
            {!editing ? (
              <label className="flex items-center gap-3 text-sm" htmlFor="project-version-default">
                <Checkbox
                  checked={form.setAsDefault}
                  id="project-version-default"
                  onCheckedChange={(checked) => setForm((current) => ({ ...current, setAsDefault: Boolean(checked) }))}
                />
                创建后设为当前版本
              </label>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              取消
            </Button>
            <Button disabled={saving || !form.version.trim()} onClick={submit}>
              {saving ? "保存中" : "保存"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(pendingDelete)} onOpenChange={(open) => !open && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除版本 {pendingDelete?.version}？</AlertDialogTitle>
            <AlertDialogDescription>删除后无法恢复。只有非当前且未关联需求的版本可以删除。</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive text-destructive-foreground" onClick={deleteVersion}>
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageShell>
  );
}

function suggestNextVersion(versions: ApiProjectVersion[]) {
  const current = versions.find((item) => item.is_default) ?? versions[0];
  if (!current) return "1.0.0";
  const [major, minor] = current.version.split(".").map(Number);
  return `${major}.${minor + 1}.0`;
}
