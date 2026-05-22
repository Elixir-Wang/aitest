"use client";

import { useRouter } from "next/navigation";

import { LogOut } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { getInitials } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";

const roleLabels: Record<string, string> = {
  admin: "管理员",
  guest: "访客",
  tester: "测试工程师",
};

export function AccountSwitcher() {
  const router = useRouter();
  const logout = useAuthStore((state) => state.logout);
  const storedUser = useAuthStore((state) => state.user);
  const displayUser = {
    avatar: "",
    email: storedUser?.email ?? "",
    id: "current",
    name: storedUser?.name ?? "",
    role: storedUser?.role ?? "guest",
  };

  if (!displayUser.name) {
    return null;
  }

  return (
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
  );
}
