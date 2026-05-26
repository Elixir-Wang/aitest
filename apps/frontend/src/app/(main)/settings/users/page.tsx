"use client";

import { useCallback, useEffect, useState } from "react";

import { Eye, EyeOff, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type ApiProject,
  type ApiUser,
  apiRequest,
  formatDateTime,
  labelToRole,
  labelToStatus,
  roleToLabel,
  statusToLabel,
} from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectContextStore } from "@/stores/project-context-store";

type UserRow = ApiUser;

const emptyForm = {
  description: "",
  email: "",
  project_scope: "全部项目",
  role: "测试工程师",
  status: "启用",
  password: "",
  username: "",
};

const roleOptions = ["管理员", "测试工程师", "访客"];
const statusOptions = ["启用", "禁用"];

export default function Page() {
  const currentUser = useAuthStore((state) => state.user);
  const canWrite = currentUser?.role === "admin";
  const hydrateProjectContext = useProjectContextStore((state) => state.hydrate);
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const projectScopeOptions = ["全部项目", ...projects.map((project) => project.name)];
  const [rows, setRows] = useState<UserRow[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserRow | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(true);
  const filteredRows = rows.filter((user) =>
    [user.username, user.email, roleToLabel(user.role), user.project_scope, statusToLabel(user.status)].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );
  const selectedCount = selectedIds.length;
  const allSelected = filteredRows.length > 0 && filteredRows.every((row) => selectedIds.includes(row.id));
  const partiallySelected = selectedCount > 0 && !allSelected;

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await apiRequest<UserRow[]>("/users"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "用户列表加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    hydrateProjectContext();
  }, [hydrateProjectContext]);

  useEffect(() => {
    let ignore = false;

    async function loadProjects() {
      try {
        const nextProjects = await apiRequest<ApiProject[]>("/projects");
        if (!ignore) {
          setProjects(nextProjects);
        }
      } catch {
        if (!ignore) {
          setProjects([]);
        }
      }
    }

    void loadProjects();

    return () => {
      ignore = true;
    };
  }, []);

  function toggleAll(checked: boolean) {
    setSelectedIds(checked ? filteredRows.map((row) => row.id) : []);
  }

  function toggleOne(id: string, checked: boolean) {
    setSelectedIds((current) => (checked ? [...current, id] : current.filter((item) => item !== id)));
  }

  function openCreateDialog() {
    setEditingUser(null);
    setForm(emptyForm);
    setPasswordVisible(false);
    setDialogOpen(true);
  }

  function openEditDialog(user: UserRow) {
    setEditingUser(user);
    setForm({
      description: user.description,
      email: user.email,
      project_scope: user.project_scope,
      password: "",
      role: roleToLabel(user.role),
      status: statusToLabel(user.status),
      username: user.username,
    });
    setPasswordVisible(false);
    setDialogOpen(true);
  }

  async function submitUser() {
    const payload = {
      description: form.description.trim(),
      email: form.email.trim(),
      password: form.password,
      project_scope: form.project_scope.trim(),
      role: labelToRole(form.role),
      status: labelToStatus(form.status),
      username: form.username.trim(),
    };

    try {
      if (editingUser) {
        const { password: _password, username: _username, ...updatePayload } = payload;
        const nextPayload = form.password.trim() ? updatePayload : { ...updatePayload, password: undefined };
        await apiRequest<UserRow>(`/users/${editingUser.id}`, {
          body: JSON.stringify(nextPayload),
          method: "PATCH",
        });
      } else {
        await apiRequest<UserRow>("/users", {
          body: JSON.stringify(payload),
          method: "POST",
        });
      }
      toast.success(editingUser ? "用户已保存" : "用户已创建");
      setDialogOpen(false);
      await loadUsers();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "用户保存失败");
    }
  }

  async function deleteUsers(ids: string[]) {
    try {
      await Promise.all(ids.map((id) => apiRequest(`/users/${id}`, { method: "DELETE" })));
      setSelectedIds([]);
      toast.success("用户已删除");
      await loadUsers();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "用户删除失败");
    }
  }

  return (
    <PageShell
      breadcrumbs={["系统管理", "用户与权限"]}
      description="管理管理员、测试工程师、访客账号和项目分配。"
      projectScope="none"
      title="用户与权限"
    >
      <ShellSection>
        <ListToolbar
          createLabel="新增用户"
          onBatchDelete={canWrite ? () => deleteUsers(selectedIds) : undefined}
          onCreate={canWrite ? openCreateDialog : undefined}
          onSearch={setSearchText}
          placeholder="搜索用户、角色或项目"
          selectedCount={canWrite ? selectedCount : 0}
          title="用户与权限列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部用户"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    disabled={!canWrite || loading}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>用户名</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>项目范围</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>最近登录</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRows.map((item) => (
                <TableRow data-state={selectedIds.includes(item.id) ? "selected" : undefined} key={item.id}>
                  <TableCell>
                    <Checkbox
                      aria-label={`选择 ${item.id}`}
                      checked={selectedIds.includes(item.id)}
                      disabled={!canWrite}
                      onCheckedChange={(checked) => toggleOne(item.id, Boolean(checked))}
                    />
                  </TableCell>
                  <TableCell className="font-medium">{item.username}</TableCell>
                  <TableCell>{roleToLabel(item.role)}</TableCell>
                  <TableCell>{item.project_scope}</TableCell>
                  <TableCell>
                    <Badge variant={item.status === "disabled" ? "outline" : "secondary"}>
                      {statusToLabel(item.status)}
                    </Badge>
                  </TableCell>
                  <TableCell>{formatDateTime(item.last_login_at)}</TableCell>
                  <TableCell>
                    <RowActions
                      actions={[
                        {
                          label: "编辑",
                          disabled: !canWrite,
                          icon: Pencil,
                          onSelect: canWrite ? () => openEditDialog(item) : undefined,
                        },
                        {
                          label: "删除",
                          disabled: !canWrite,
                          destructive: true,
                          icon: Trash2,
                          onSelect: canWrite ? () => deleteUsers([item.id]) : undefined,
                        },
                      ]}
                      label={`打开 ${item.username} 操作菜单`}
                    />
                  </TableCell>
                </TableRow>
              ))}
              {loading && filteredRows.length === 0 ? <TableLoadingRow colSpan={7} label="用户列表加载中" /> : null}
              {!loading && filteredRows.length === 0 ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={7}>
                    暂无用户。添加用户后，可按角色管理系统访问权限。
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
            <DialogTitle>{editingUser ? "编辑用户" : "新增用户"}</DialogTitle>
            <DialogDescription>账号由管理员创建，后端保存加密密码并校验角色权限。</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="user-username">用户名</FieldLabel>
              <Input
                disabled={Boolean(editingUser)}
                id="user-username"
                onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
                placeholder="请输入非中文用户名"
                value={form.username}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="user-email">邮箱</FieldLabel>
              <Input
                id="user-email"
                onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
                placeholder="请输入邮箱"
                type="email"
                value={form.email}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="user-description">描述</FieldLabel>
              <Input
                id="user-description"
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="请输入描述"
                value={form.description}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="user-password">密码</FieldLabel>
              <div className="relative">
                <Input
                  className="pr-9"
                  id="user-password"
                  onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                  placeholder={editingUser ? "留空则不修改密码" : "请输入密码"}
                  type={passwordVisible ? "text" : "password"}
                  value={form.password}
                />
                <Button
                  aria-label={passwordVisible ? "隐藏密码" : "显示密码"}
                  className="absolute top-0 right-0"
                  onClick={() => setPasswordVisible((value) => !value)}
                  size="icon"
                  type="button"
                  variant="ghost"
                >
                  {passwordVisible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </Button>
              </div>
            </Field>
            <Field>
              <FieldLabel htmlFor="user-role">角色</FieldLabel>
              <Select
                id="user-role"
                placeholder="选择角色"
                setValue={(value) => setForm((current) => ({ ...current, role: value }))}
                value={form.role}
              >
                {roleOptions.map((role) => (
                  <SelectOption key={role} value={role}>
                    {role}
                  </SelectOption>
                ))}
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="user-project">项目范围</FieldLabel>
              <Select
                id="user-project"
                placeholder="选择项目范围"
                setValue={(value) => setForm((current) => ({ ...current, project_scope: value }))}
                value={form.project_scope}
              >
                {projectScopeOptions.map((project) => (
                  <SelectOption key={project} value={project}>
                    {project}
                  </SelectOption>
                ))}
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="user-status">状态</FieldLabel>
              <Select
                id="user-status"
                placeholder="选择状态"
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
          </FieldGroup>
          <DialogFooter>
            <Button onClick={() => setDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button
              disabled={!form.username.trim() || !form.email.trim() || (!editingUser && !form.password.trim())}
              onClick={submitUser}
              type="button"
            >
              {editingUser ? "保存" : "新增"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
