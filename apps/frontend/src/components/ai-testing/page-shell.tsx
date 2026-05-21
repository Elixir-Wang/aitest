import type { ReactNode } from "react";

import Link from "next/link";

import type { LucideIcon } from "lucide-react";
import { CircleAlert, Ellipsis, Plus, Search, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

type ProjectScope = "all" | "project" | "none";
type ModuleTab = string | { label: string; href: string };
type RowAction = {
  label: string;
  icon: LucideIcon;
  href?: string;
  destructive?: boolean;
  disabled?: boolean;
  onSelect?: () => void;
};

interface PageShellProps {
  title: string;
  description: string;
  breadcrumbs: string[];
  projectScope?: ProjectScope;
  tabs?: ModuleTab[];
  activeTab?: string;
  primaryAction?: string;
  onPrimaryAction?: () => void;
  children: ReactNode;
}

interface MetricCardProps {
  label: string;
  value: string;
  helper: string;
  icon: LucideIcon;
}

export function PageShell({
  title,
  description,
  breadcrumbs,
  tabs = [],
  activeTab,
  primaryAction,
  onPrimaryAction,
  children,
}: PageShellProps) {
  return (
    <div className="@container/main flex flex-col gap-4 md:gap-6">
      <PageHeader
        breadcrumbs={breadcrumbs}
        description={description}
        onPrimaryAction={onPrimaryAction}
        primaryAction={primaryAction}
        title={title}
      />
      {tabs.length > 0 && <ModuleTabs activeTab={activeTab} tabs={tabs} />}
      {children}
    </div>
  );
}

export function PageHeader({
  title,
  primaryAction,
  onPrimaryAction,
}: {
  title: string;
  description: string;
  breadcrumbs: string[];
  primaryAction?: string;
  onPrimaryAction?: () => void;
}) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0 space-y-2">
        <div className="space-y-1">
          <h1 className="font-heading font-semibold text-2xl tracking-normal">{title}</h1>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {primaryAction && <Button onClick={onPrimaryAction}>{primaryAction}</Button>}
      </div>
    </div>
  );
}

export function ModuleTabs({ tabs, activeTab }: { tabs: ModuleTab[]; activeTab?: string }) {
  const firstTab = tabs[0];
  const defaultValue = activeTab ?? (typeof firstTab === "string" ? firstTab : firstTab.label);

  return (
    <Tabs defaultValue={defaultValue} className="w-full">
      <TabsList className="flex h-auto flex-wrap justify-start">
        {tabs.map((tab) => (
          <TabsTrigger
            key={typeof tab === "string" ? tab : tab.label}
            value={typeof tab === "string" ? tab : tab.label}
          >
            {typeof tab === "string" ? tab : <Link href={tab.href}>{tab.label}</Link>}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}

export function MetricCard({ label, value, helper, icon: Icon }: MetricCardProps) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-2xl">{value}</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center justify-between gap-3 text-muted-foreground text-sm">
        <span>{helper}</span>
        <Icon className="size-4" />
      </CardContent>
    </Card>
  );
}

export function PageToolbar({ placeholder = "搜索名称、状态或负责人" }: { placeholder?: string }) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border bg-card p-3 sm:flex-row sm:items-center sm:justify-between">
      <Input className="sm:max-w-xs" placeholder={placeholder} />
      <div className="flex flex-wrap gap-2">
        <Button variant="outline">全部状态</Button>
        <Button variant="outline">负责人</Button>
      </div>
    </div>
  );
}

export function ListToolbar({
  title,
  description = "",
  placeholder = "搜索名称、状态或负责人",
  createLabel = "新建",
  selectedCount = 0,
  onBatchDelete,
  onCreate,
  onSearch,
}: {
  title: string;
  description?: string;
  placeholder?: string;
  createLabel?: string;
  selectedCount?: number;
  onBatchDelete?: () => void;
  onCreate?: () => void;
  onSearch?: (value: string) => void;
}) {
  const hasSelection = selectedCount > 0;

  return (
    <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="min-w-0">
        <h2 className="font-medium text-sm">{title}</h2>
        {description ? <p className="text-muted-foreground text-xs">{description}</p> : null}
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
        <div className="relative h-8 w-20 font-medium text-sm">
          <div className="group/search absolute top-0 right-0 h-8 w-20 transition-all duration-200 focus-within:w-56">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-foreground" />
            <Input
              aria-label={placeholder}
              className="h-8 w-full rounded-lg border-border bg-background pr-2 pl-8 font-medium text-foreground text-sm transition-all duration-200 placeholder:text-foreground hover:bg-muted hover:text-foreground focus-visible:border-border focus-visible:ring-0 dark:border-input dark:bg-input/30 dark:hover:bg-input/50"
              onChange={(event) => onSearch?.(event.target.value)}
              placeholder="搜索"
            />
          </div>
        </div>
        <Button
          className="border-red-200 bg-red-50 text-red-700 hover:border-red-300 hover:bg-red-100 hover:text-red-800 disabled:border-red-100 disabled:bg-red-50 disabled:text-red-300 dark:border-red-900/40 dark:bg-red-950/20 dark:text-red-300 dark:disabled:text-red-900/70 dark:hover:bg-red-950/30"
          disabled={!hasSelection}
          onClick={onBatchDelete}
          variant="outline"
        >
          <Trash2 className="size-4" />
          批量删除{hasSelection ? ` (${selectedCount})` : ""}
        </Button>
        <Button onClick={onCreate}>
          <Plus className="size-4" />
          {createLabel}
        </Button>
      </div>
    </div>
  );
}

export function StatusBadge({ children, tone = "default" }: { children: ReactNode; tone?: "default" | "muted" }) {
  return (
    <Badge className={cn(tone === "muted" && "bg-muted text-muted-foreground")} variant="secondary">
      {children}
    </Badge>
  );
}

export function RowActions({ label, actions }: { label: string; actions: RowAction[] }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button aria-label={label} size="icon" variant="ghost">
          <Ellipsis className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-max">
        {actions.map((action, index) => (
          <div key={`${action.label}-${action.href ?? "action"}`}>
            {action.destructive && index > 0 && <DropdownMenuSeparator />}
            <DropdownMenuItem
              className="gap-2 whitespace-nowrap pr-3"
              asChild={Boolean(action.href)}
              disabled={action.disabled}
              onClick={action.onSelect}
              variant={action.destructive ? "destructive" : undefined}
            >
              {action.href ? (
                <Link href={action.href}>
                  <action.icon className="size-4" />
                  {action.label}
                </Link>
              ) : (
                <>
                  <action.icon className="size-4" />
                  {action.label}
                </>
              )}
            </DropdownMenuItem>
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function EmptyState({
  title,
  description,
  status = "骨架已接入",
}: {
  title: string;
  description: string;
  status?: string;
}) {
  return (
    <Empty className="min-h-72 border bg-card">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <CircleAlert />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <StatusBadge tone={status === "Soon" ? "muted" : "default"}>{status}</StatusBadge>
      </EmptyContent>
    </Empty>
  );
}

export function SoonPage({ title, description }: { title: string; description: string }) {
  return <EmptyState description={description} status="Soon" title={title} />;
}

export function ShellSection({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("rounded-xl border bg-card p-4", className)}>{children}</div>;
}
