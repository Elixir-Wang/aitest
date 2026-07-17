type AppBreadcrumb = {
  label: string;
  href?: string;
};

type BreadcrumbModuleKey = keyof typeof breadcrumbModules;

const breadcrumbModules = {
  dashboard: { section: "工作台", label: "控制台", href: "/dashboard" },
  tasks: { section: "工作台", label: "任务中心", href: "/tasks" },
  projects: { section: "项目工作区", label: "项目", href: "/projects" },
  requirements: { section: "项目工作区", label: "需求", href: "/requirements" },
  exploration: { section: "项目工作区", label: "探索", href: "/exploration" },
  knowledge: { section: "项目工作区", label: "知识库", href: "/knowledge" },
  testCases: { section: "测试资产", label: "测试用例", href: "/test-cases" },
  uiAutomation: { section: "测试资产", label: "UI 自动化", href: "/automation/ui" },
  apiAutomation: { section: "测试资产", label: "接口自动化", href: "/automation/api" },
  performanceTests: { section: "测试资产", label: "性能测试", href: "/performance-tests" },
  reports: { section: "测试资产", label: "报告中心", href: "/reports" },
  models: { section: "系统管理", label: "模型配置", href: "/settings/models" },
  users: { section: "系统管理", label: "用户与权限", href: "/settings/users" },
  systemLogs: { section: "系统管理", label: "系统日志", href: "/settings/logs" },
  systemSettings: { section: "系统管理", label: "系统设置", href: "/settings/system" },
} as const;

export function moduleBreadcrumbs(moduleKey: BreadcrumbModuleKey, ...items: AppBreadcrumb[]): AppBreadcrumb[] {
  const module = breadcrumbModules[moduleKey];
  return [
    { label: module.section },
    items.length > 0 ? { label: module.label, href: module.href } : { label: module.label },
    ...items,
  ];
}
