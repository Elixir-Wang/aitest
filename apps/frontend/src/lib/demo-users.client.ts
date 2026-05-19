"use client";

import { getLocalStorageValue, setLocalStorageValue } from "@/lib/local-storage.client";

export const DEMO_USERS_STORAGE_KEY = "ai-testing.demo.users";

export type DemoUserStatus = "启用" | "禁用";

export type DemoUser = {
  description: string;
  email: string;
  id: string;
  password: string;
  project: string;
  role: string;
  status: DemoUserStatus;
  updated: string;
  username: string;
};

export const defaultDemoUsers: DemoUser[] = [
  {
    description: "平台管理员，负责用户、模型和项目权限维护。",
    email: "admin@example.com",
    id: "u-001",
    password: "admin",
    project: "全部项目",
    role: "管理员",
    status: "启用",
    updated: "2026-05-19 12:30:00",
    username: "admin",
  },
  {
    description: "负责知了平台测试资产维护。",
    email: "liqiang@example.com",
    id: "u-002",
    password: "admin",
    project: "知了平台",
    role: "测试工程师",
    status: "启用",
    updated: "2026-05-19 08:30:00",
    username: "liqiang",
  },
  {
    description: "只读查看鹰眼平台测试报告。",
    email: "wanglei@example.com",
    id: "u-003",
    password: "admin",
    project: "鹰眼平台",
    role: "访客",
    status: "禁用",
    updated: "2026-05-18 10:15:00",
    username: "wanglei",
  },
];

function normalizeUser(user: Partial<DemoUser>): DemoUser {
  return {
    description: user.description ?? "",
    email: user.email ?? "",
    id: user.id ?? `u-${Date.now()}`,
    password: user.password || "admin",
    project: user.project ?? "全部项目",
    role: user.role ?? "测试工程师",
    status: user.status === "禁用" ? "禁用" : "启用",
    updated: user.updated ?? "",
    username: user.username ?? "",
  };
}

export function getDemoUsers(): DemoUser[] {
  const rawUsers = getLocalStorageValue(DEMO_USERS_STORAGE_KEY);

  if (!rawUsers) {
    return defaultDemoUsers;
  }

  try {
    const parsedUsers = JSON.parse(rawUsers);

    if (!Array.isArray(parsedUsers)) {
      return defaultDemoUsers;
    }

    return parsedUsers.map((user) => normalizeUser(user));
  } catch {
    return defaultDemoUsers;
  }
}

export function saveDemoUsers(users: DemoUser[]) {
  setLocalStorageValue(DEMO_USERS_STORAGE_KEY, JSON.stringify(users.map((user) => normalizeUser(user))));
}

export function findDemoUser(loginName: string) {
  const normalizedLoginName = loginName.trim().toLowerCase();

  return getDemoUsers().find(
    (user) => user.username.toLowerCase() === normalizedLoginName || user.email.toLowerCase() === normalizedLoginName,
  );
}
