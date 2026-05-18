import type { ReactNode } from "react";

import type { LucideIcon } from "lucide-react";
import { CircleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { ProjectSwitcher } from "@/components/ai-testing/project-switcher";

type ProjectScope = "all" | "project" | "none";

interface PageShellProps {
  title: string;
  description: string;
  breadcrumbs: string[];
  projectScope?: ProjectScope;
  tabs?: string[];
  primaryAction?: string;
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
  projectScope = "all",
  tabs = [],
  primaryAction,
  children,
}: PageShellProps) {
  return (
    <div className="@container/main flex flex-col gap-4 md:gap-6">
      <PageHeader
        breadcrumbs={breadcrumbs}
        description={description}
        primaryAction={primaryAction}
        projectScope={projectScope}
        title={title}
      />
      {tabs.length > 0 && <ModuleTabs tabs={tabs} />}
      {children}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  breadcrumbs,
  projectScope,
  primaryAction,
}: {
  title: string;
  description: string;
  breadcrumbs: string[];
  projectScope: ProjectScope;
  primaryAction?: string;
}) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0 space-y-2">
        <div className="flex flex-wrap items-center gap-1 text-muted-foreground text-xs">
          {breadcrumbs.map((item, index) => (
            <span key={breadcrumbs.slice(0, index + 1).join("/")} className="flex items-center gap-1">
              {index > 0 && <span>/</span>}
              <span>{item}</span>
            </span>
          ))}
        </div>
        <div className="space-y-1">
          <h1 className="font-heading font-semibold text-2xl tracking-normal">{title}</h1>
          <p className="max-w-3xl text-muted-foreground text-sm">{description}</p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {projectScope !== "none" && <ProjectSwitcher scope={projectScope} />}
        {primaryAction && <Button>{primaryAction}</Button>}
      </div>
    </div>
  );
}

export function ModuleTabs({ tabs }: { tabs: string[] }) {
  return (
    <Tabs defaultValue={tabs[0]} className="w-full">
      <TabsList className="flex h-auto flex-wrap justify-start">
        {tabs.map((tab) => (
          <TabsTrigger key={tab} value={tab}>
            {tab}
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

export function StatusBadge({ children, tone = "default" }: { children: ReactNode; tone?: "default" | "muted" }) {
  return (
    <Badge className={cn(tone === "muted" && "bg-muted text-muted-foreground")} variant="secondary">
      {children}
    </Badge>
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
