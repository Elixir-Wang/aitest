"use client";

import { type ComponentPropsWithoutRef, type ReactNode, useEffect } from "react";

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

import { type BreadcrumbItem, useWorkspaceBreadcrumbs } from "./workspace-breadcrumbs";

type ProjectScope = "all" | "project" | "none";
type ModuleTab = string | { label: string; href: string };
type BreadcrumbInput = string | BreadcrumbItem;
export type PageBreadcrumb = BreadcrumbInput;
type RowAction = {
  label: string;
  icon?: LucideIcon;
  href?: string;
  destructive?: boolean;
  disabled?: boolean;
  onSelect?: () => void;
};

interface PageShellProps {
  title: string;
  description?: string;
  breadcrumbs: BreadcrumbInput[];
  projectScope?: ProjectScope;
  tabs?: ModuleTab[];
  activeTab?: string;
  onTabChange?: (value: string) => void;
  primaryAction?: string;
  onPrimaryAction?: () => void;
  actions?: ReactNode;
  tabActions?: ReactNode;
  children: ReactNode;
  fillViewport?: boolean;
}

interface MetricCardProps {
  label: string;
  value: string;
  helper: string;
  icon: LucideIcon;
}

export function PageShell({
  breadcrumbs,
  tabs = [],
  activeTab,
  onTabChange,
  primaryAction,
  onPrimaryAction,
  actions,
  tabActions,
  children,
  fillViewport = false,
}: PageShellProps) {
  const { setBreadcrumbs } = useWorkspaceBreadcrumbs();
  const breadcrumbKey = JSON.stringify(breadcrumbs);

  useEffect(() => {
    setBreadcrumbs(normalizeBreadcrumbs(JSON.parse(breadcrumbKey) as BreadcrumbInput[]));

    return () => setBreadcrumbs([]);
  }, [breadcrumbKey, setBreadcrumbs]);

  useEffect(() => {
    if (!fillViewport) {
      return;
    }

    const previousDocumentOverflow = document.documentElement.style.overflow;
    const previousBodyOverflow = document.body.style.overflow;
    document.documentElement.style.overflow = "hidden";
    document.body.style.overflow = "hidden";

    return () => {
      document.documentElement.style.overflow = previousDocumentOverflow;
      document.body.style.overflow = previousBodyOverflow;
    };
  }, [fillViewport]);

  return (
    <div
      className={cn("@container/main flex flex-col gap-4 md:gap-6", fillViewport && "min-h-0 flex-1 overflow-hidden")}
      style={fillViewport ? { height: "calc(100vh - 6.5rem)", maxHeight: "calc(100vh - 6.5rem)" } : undefined}
    >
      <PageHeader actions={actions} onPrimaryAction={onPrimaryAction} primaryAction={primaryAction} />
      {tabs.length > 0 && (
        <ModuleTabs actions={tabActions} activeTab={activeTab} onTabChange={onTabChange} tabs={tabs} />
      )}
      {children}
    </div>
  );
}

function normalizeBreadcrumbs(items: BreadcrumbInput[]): BreadcrumbItem[] {
  return items.map((item) => (typeof item === "string" ? { label: item } : item));
}

function PageHeader({
  primaryAction,
  onPrimaryAction,
  actions,
}: {
  primaryAction?: string;
  onPrimaryAction?: () => void;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-end">
      <div className="flex flex-wrap items-center gap-2">
        {actions}
        {primaryAction && <Button onClick={onPrimaryAction}>{primaryAction}</Button>}
      </div>
    </div>
  );
}

export function ModuleTabs({
  tabs,
  activeTab,
  onTabChange,
  actions,
}: {
  tabs: ModuleTab[];
  activeTab?: string;
  onTabChange?: (value: string) => void;
  actions?: ReactNode;
}) {
  const firstTab = tabs[0];
  const defaultValue = activeTab ?? (typeof firstTab === "string" ? firstTab : firstTab.label);

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <Tabs value={activeTab} defaultValue={defaultValue} onValueChange={onTabChange} className="w-auto">
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
      <div className="flex flex-wrap items-center gap-2 sm:justify-end">{actions}</div>
    </div>
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

export function ListToolbar({
  title,
  description = "",
  placeholder = "搜索名称、状态或负责人",
  createLabel = "新建",
  createDisabled = false,
  createTitle,
  selectedCount = 0,
  onBatchDelete,
  onCreate,
  onSearch,
  actions,
}: {
  title: string;
  description?: string;
  placeholder?: string;
  createLabel?: string;
  createDisabled?: boolean;
  createTitle?: string;
  selectedCount?: number;
  onBatchDelete?: () => void;
  onCreate?: () => void;
  onSearch?: (value: string) => void;
  actions?: ReactNode;
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
        {hasSelection && onBatchDelete ? (
          <Button
            className="border-red-200 bg-red-50 text-red-700 hover:border-red-300 hover:bg-red-100 hover:text-red-800 dark:border-red-900/40 dark:bg-red-950/20 dark:text-red-300 dark:hover:bg-red-950/30"
            onClick={onBatchDelete}
            variant="outline"
          >
            <Trash2 className="size-4" />
            批量删除 ({selectedCount})
          </Button>
        ) : null}
        {onCreate ? (
          <Button disabled={createDisabled} onClick={onCreate} title={createTitle}>
            <Plus className="size-4" />
            {createLabel}
          </Button>
        ) : null}
        {actions}
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
      <DropdownMenuContent align="center" className="w-max">
        {actions.map((action, index) => (
          <div key={`${action.label}-${action.href ?? "action"}`}>
            {action.destructive && index > 0 && <DropdownMenuSeparator />}
            {action.href ? (
              <DropdownMenuItem asChild>
                <Link
                  className={cn(
                    "gap-2 whitespace-nowrap pr-3",
                    action.destructive && "text-destructive focus:text-destructive",
                  )}
                  href={action.href}
                >
                  {action.icon && <action.icon className="size-4" />}
                  {action.label}
                </Link>
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem
                className={cn(
                  "gap-2 whitespace-nowrap pr-3",
                  action.destructive && "text-destructive focus:text-destructive",
                )}
                disabled={action.disabled}
                onClick={action.onSelect}
              >
                {action.icon && <action.icon className="size-4" />}
                {action.label}
              </DropdownMenuItem>
            )}
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

export function ShellSection({ children, className, ...props }: ComponentPropsWithoutRef<"div">) {
  return (
    <div className={cn("rounded-xl border bg-card p-4", className)} {...props}>
      {children}
    </div>
  );
}
