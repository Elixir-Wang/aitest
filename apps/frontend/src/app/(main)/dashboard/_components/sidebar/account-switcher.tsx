"use client";

import { useState } from "react";

import { useRouter } from "next/navigation";

import { LogOut, Pencil } from "lucide-react";
import { toast } from "sonner";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
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
import { getInitials } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";

const roleLabels: Record<string, string> = {
  admin: "管理员",
  guest: "访客",
  tester: "测试工程师",
};

export function AccountSwitcher({
  users,
}: {
  readonly users: ReadonlyArray<{
    readonly id: string;
    readonly name: string;
    readonly email: string;
    readonly avatar: string;
    readonly role: string;
  }>;
}) {
  const router = useRouter();
  const logout = useAuthStore((state) => state.logout);
  const storedUser = useAuthStore((state) => state.user);
  const updateUser = useAuthStore((state) => state.updateUser);
  const [activeUser, setActiveUser] = useState(users[0]);
  const displayUser = {
    avatar: activeUser?.avatar ?? "",
    email: storedUser?.email || activeUser?.email || "",
    id: activeUser?.id ?? "current",
    name: storedUser?.name || activeUser?.name || "",
    role: storedUser?.role || activeUser?.role || "guest",
  };
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({
    email: displayUser.email,
    name: displayUser.name,
  });

  if (!displayUser.name) {
    return null;
  }

  function openEditDialog() {
    setForm({
      email: displayUser.email,
      name: displayUser.name,
    });
    setDialogOpen(true);
  }

  function submitUserInfo() {
    const name = form.name.trim();
    const email = form.email.trim();

    if (!name || !email) {
      return;
    }

    updateUser({
      email,
      name,
      role: displayUser.role as "admin" | "tester" | "guest",
    });
    setActiveUser((current) => (current ? { ...current, email, name } : current));
    setDialogOpen(false);
    toast.success("用户信息已更新");
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button aria-label="打开用户菜单" size="icon">
            <Avatar className="size-5 rounded-md after:hidden">
              <AvatarImage src={displayUser.avatar || undefined} alt={displayUser.name} />
              <AvatarFallback className="rounded-md bg-transparent text-current text-xs">
                {getInitials(displayUser.name)}
              </AvatarFallback>
            </Avatar>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-max min-w-0 space-y-1 rounded-lg p-1" side="bottom" align="end" sideOffset={4}>
          <DropdownMenuItem className="p-0" aria-current="true">
            <div className="flex w-max max-w-64 items-center gap-2 px-1 py-1.5">
              <Avatar className="size-9 rounded-lg">
                <AvatarImage src={displayUser.avatar || undefined} alt={displayUser.name} />
                <AvatarFallback>{getInitials(displayUser.name)}</AvatarFallback>
              </Avatar>
              <div className="grid min-w-0 max-w-48 text-left text-sm leading-tight">
                <span className="truncate font-semibold">{displayUser.name}</span>
                <span className="truncate text-xs">{roleLabels[displayUser.role] ?? displayUser.role}</span>
              </div>
            </div>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="justify-center gap-2 text-center" onClick={openEditDialog}>
            <Pencil />
            编辑
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="justify-center gap-2 text-center"
            onClick={() => {
              logout();
              router.replace("/auth/v1/login");
            }}
          >
            <LogOut />
            登出
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <Dialog onOpenChange={setDialogOpen} open={dialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>编辑用户信息</DialogTitle>
            <DialogDescription>维护右上角展示的用户名和邮箱。</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="account-name">用户名</FieldLabel>
              <Input
                id="account-name"
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="请输入用户名"
                value={form.name}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="account-email">邮箱</FieldLabel>
              <Input
                id="account-email"
                onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
                placeholder="请输入邮箱"
                value={form.email}
              />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button onClick={() => setDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={!form.name.trim() || !form.email.trim()} onClick={submitUserInfo} type="button">
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
