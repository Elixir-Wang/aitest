import {
  Bot,
  ClipboardCheck,
  ClipboardList,
  DatabaseZap,
  FileSearch,
  FileText,
  LayoutDashboard,
  ListTodo,
  NotebookTabs,
  PlaySquare,
  Settings,
  TestTubeDiagonal,
  type LucideIcon,
  Users,
} from "lucide-react";

export interface NavSubItem {
  title: string;
  url: string;
  icon?: LucideIcon;
  comingSoon?: boolean;
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
        url: "/projects/zhiliao/requirements",
        icon: FileText,
        projectScoped: true,
      },
      {
        title: "探索",
        url: "/projects/zhiliao/exploration",
        icon: FileSearch,
        projectScoped: true,
      },
      {
        title: "知识库",
        url: "/projects/zhiliao/knowledge",
        icon: DatabaseZap,
        projectScoped: true,
      },
    ],
  },
  {
    id: 3,
    label: "测试资产",
    items: [
      {
        title: "测试用例",
        url: "/projects/zhiliao/test-cases",
        icon: ClipboardCheck,
        projectScoped: true,
      },
      {
        title: "UI 自动化",
        url: "/projects/zhiliao/automation/ui",
        icon: PlaySquare,
        projectScoped: true,
      },
      {
        title: "接口自动化",
        url: "/projects/zhiliao/automation/api",
        icon: TestTubeDiagonal,
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
        title: "系统设置",
        url: "/settings/system",
        icon: Settings,
        requiredRole: "admin",
      },
    ],
  },
];
