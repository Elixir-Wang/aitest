"use client";

import { useState } from "react";

import { Ellipsis, Eye, EyeOff } from "lucide-react";

import { ListToolbar, PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type DemoUser, type DemoUserStatus, getDemoUsers, saveDemoUsers } from "@/lib/demo-users.client";

type UserRow = DemoUser;

const emptyForm = {
  description: "",
  email: "",
  project: "全部项目",
  role: "测试工程师",
  status: "启用" as DemoUserStatus,
  password: "",
  username: "",
};

const roleOptions = ["管理员", "测试工程师", "访客"];
const projectOptions = ["全部项目", "知了平台", "鹰眼平台"];
const statusOptions = ["启用", "禁用"];

function nowText() {
  const now = new Date();
  const pad = (value: number) => value.toString().padStart(2, "0");

  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
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
  } = useLocalTableSelection(getDemoUsers());
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserRow | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((user) =>
    [user.username, user.email, user.role, user.project, user.status, user.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

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
      project: user.project,
      password: user.password,
      role: user.role,
      status: user.status,
      username: user.username,
    });
    setPasswordVisible(false);
    setDialogOpen(true);
  }

  function submitUser() {
    const username = form.username.trim();

    if (!username) {
      return;
    }

    const row: UserRow = {
      description: form.description.trim(),
      email: form.email.trim(),
      id: editingUser?.id ?? `u-${Date.now()}`,
      project: form.project.trim(),
      password: form.password,
      role: form.role.trim(),
      status: form.status,
      updated: nowText(),
      username,
    };

    if (editingUser) {
      updateRow(row);
      saveDemoUsers(rows.map((item) => (item.id === row.id ? row : item)));
    } else {
      addRow(row);
      saveDemoUsers([row, ...rows]);
    }

    setDialogOpen(false);
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
          onBatchDelete={() => {
            deleteSelected();
            saveDemoUsers(rows.filter((row) => !selectedIds.includes(row.id)));
          }}
          onCreate={openCreateDialog}
          onDelete={() => {
            deleteSelected();
            saveDemoUsers(rows.filter((row) => !selectedIds.includes(row.id)));
          }}
          onSearch={setSearchText}
          placeholder="搜索用户、角色或项目"
          selectedCount={selectedCount}
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
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>用户名</TableHead>
                <TableHead>邮箱</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>项目范围</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>更新时间</TableHead>
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
                      onCheckedChange={(checked) => toggleOne(item.id, Boolean(checked))}
                    />
                  </TableCell>
                  <TableCell className="font-medium">{item.username}</TableCell>
                  <TableCell>{item.email}</TableCell>
                  <TableCell>{item.role}</TableCell>
                  <TableCell>{item.project}</TableCell>
                  <TableCell>
                    <Badge variant={item.status === "禁用" ? "outline" : "secondary"}>{item.status}</Badge>
                  </TableCell>
                  <TableCell>{item.updated}</TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button aria-label={`打开 ${item.username} 操作菜单`} size="icon" variant="ghost">
                          <Ellipsis className="size-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => openEditDialog(item)}>编辑</DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() => {
                            deleteOne(item.id);
                            saveDemoUsers(rows.filter((row) => row.id !== item.id));
                          }}
                          variant="destructive"
                        >
                          删除
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
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
            <DialogTitle>{editingUser ? "编辑用户" : "新增用户"}</DialogTitle>
            <DialogDescription>本地维护用户名、邮箱、描述、角色、项目范围和状态。</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="user-username">用户名</FieldLabel>
              <Input
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
                  placeholder="请输入密码"
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
                setValue={(value) => setForm((current) => ({ ...current, project: value }))}
                value={form.project}
              >
                {projectOptions.map((project) => (
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
                setValue={(value) => setForm((current) => ({ ...current, status: value as DemoUserStatus }))}
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
            <Button disabled={!form.username.trim() || !form.password.trim()} onClick={submitUser} type="button">
              {editingUser ? "保存" : "新增"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
