import assert from "node:assert/strict";
import { test } from "node:test";

import { moduleBreadcrumbs } from "../src/navigation/breadcrumbs.ts";

test("module breadcrumb builder owns navigation group and module links", () => {
  assert.deepEqual(moduleBreadcrumbs("requirements"), [
    { label: "项目工作区" },
    { label: "需求" },
  ]);
  assert.deepEqual(moduleBreadcrumbs("requirements", { label: "新建需求" }), [
    { label: "项目工作区" },
    { label: "需求", href: "/requirements" },
    { label: "新建需求" },
  ]);
  assert.deepEqual(moduleBreadcrumbs("systemLogs", { label: "日志详情" }), [
    { label: "系统管理" },
    { label: "系统日志", href: "/settings/logs" },
    { label: "日志详情" },
  ]);
});

test("exploration breadcrumbs use the shared module builder", () => {
  assert.deepEqual(moduleBreadcrumbs("exploration"), [{ label: "项目工作区" }, { label: "探索" }]);
  assert.deepEqual(moduleBreadcrumbs("exploration", { label: "新建探索任务" }), [
    { label: "项目工作区" },
    { label: "探索", href: "/exploration" },
    { label: "新建探索任务" },
  ]);
  assert.deepEqual(moduleBreadcrumbs("exploration", { label: "工作台页面探索" }), [
    { label: "项目工作区" },
    { label: "探索", href: "/exploration" },
    { label: "工作台页面探索" },
  ]);
});
