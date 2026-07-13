import {
  Bot,
  BrainCircuit,
  ClipboardCheck,
  ClipboardList,
  DatabaseZap,
  FileSearch,
  FileText,
  Gauge,
  LayoutDashboard,
  ListChecks,
  ListTodo,
  type LucideIcon,
  NotebookTabs,
  PlaySquare,
  TestTubeDiagonal,
  Users,
} from "lucide-react";

interface NavSubItem {
  title: string;
  url: string;
  icon?: LucideIcon;
  comingSoon?: boolean;
  projectScoped?: boolean;
  newTab?: boolean;
  isNew?: boolean;
}

export interface NavMainItem {
  title: string;
  url: string;
  icon?: LucideIcon;
  subItems?: NavSubItem[];
  comingSoon?: boolean;
  disabled?: boolean;
  projectScoped?: boolean;
  requiredRole?: "admin" | "tester" | "guest";
  newTab?: boolean;
  isNew?: boolean;
}

export interface NavGroup {
  id: number;
  label?: string;
  items: NavMainItem[];
}

export const sidebarItems: NavGroup[] = [
  {
    id: 1,
    label: "工作台",
    items: [
      {
        title: "控制台",
        url: "/dashboard",
        icon: LayoutDashboard,
      },
      {
        title: "任务中心",
        url: "/tasks",
        icon: ListTodo,
      },
    ],
  },
  {
    id: 2,
    label: "项目工作区",
    items: [
      {
        title: "项目",
        url: "/projects",
        icon: NotebookTabs,
      },
      {
        title: "需求",
        url: "/requirements",
        icon: FileText,
      },
      {
        title: "探索",
        url: "/exploration",
        icon: FileSearch,
      },
      {
        title: "知识库",
        url: "/knowledge",
        icon: DatabaseZap,
      },
    ],
  },
  {
    id: 3,
    label: "测试资产",
    items: [
      {
        title: "测试用例",
        url: "/test-cases",
        icon: ClipboardCheck,
      },
      {
        title: "UI 自动化",
        url: "/automation/ui",
        icon: PlaySquare,
        comingSoon: true,
        disabled: true,
      },
      {
        title: "接口自动化",
        url: "/automation/api",
        icon: TestTubeDiagonal,
      },
      {
        title: "性能测试",
        url: "/projects/:projectId/performance-tests",
        icon: Gauge,
        projectScoped: true,
      },
      {
        title: "模型评测",
        url: "/projects/:projectId/model-evaluations",
        icon: BrainCircuit,
        comingSoon: true,
        disabled: true,
        projectScoped: true,
      },
      {
        title: "报告中心",
        url: "/reports",
        icon: ClipboardList,
      },
    ],
  },
  {
    id: 4,
    label: "系统管理",
    items: [
      {
        title: "模型配置",
        url: "/settings/models",
        icon: Bot,
        requiredRole: "admin",
      },
      {
        title: "用户与权限",
        url: "/settings/users",
        icon: Users,
        requiredRole: "admin",
      },
      {
        title: "系统日志",
        url: "/settings/logs",
        icon: ListChecks,
        requiredRole: "admin",
      },
    ],
  },
];
