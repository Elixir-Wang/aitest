import type { ReactNode } from "react";

import { cookies } from "next/headers";

import { AccountSwitcher } from "@/app/(main)/dashboard/_components/sidebar/account-switcher";
import { AppSidebar } from "@/app/(main)/dashboard/_components/sidebar/app-sidebar";
import { LayoutControls } from "@/app/(main)/dashboard/_components/sidebar/layout-controls";
import { ThemeSwitcher } from "@/app/(main)/dashboard/_components/sidebar/theme-switcher";
import { AuthGuard } from "@/components/ai-testing/auth-guard";
import { ProjectSwitcher } from "@/components/ai-testing/project-switcher";
import { TaskRunningIndicator } from "@/components/ai-testing/task-running-indicator";
import { WorkspaceBreadcrumbProvider, WorkspaceBreadcrumbs } from "@/components/ai-testing/workspace-breadcrumbs";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { SIDEBAR_VARIANT_VALUES } from "@/lib/preferences/layout";
import { cn } from "@/lib/utils";
import { getPreference } from "@/server/server-actions";

export async function WorkspaceShell({ children }: Readonly<{ children: ReactNode }>) {
  const cookieStore = await cookies();
  const defaultOpen = cookieStore.get("sidebar_state")?.value !== "false";
  const variant = await getPreference("sidebar_variant", SIDEBAR_VARIANT_VALUES, "inset");

  return (
    <SidebarProvider
      defaultOpen={defaultOpen}
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 64)",
        } as React.CSSProperties
      }
    >
      <WorkspaceBreadcrumbProvider>
        <AppSidebar variant={variant} collapsible="icon" />
        <SidebarInset
          className={cn(
            "[&>*]:mx-auto",
            "[&>*]:w-full",
            "[&>*]:max-w-screen-2xl",
            "peer-data-[variant=inset]:border",
            "min-h-0",
          )}
        >
          <header
            className={cn(
              "flex h-12 shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12",
              "sticky top-0 z-50 overflow-hidden rounded-t-[inherit] bg-background/50 backdrop-blur-md",
            )}
          >
            <div className="flex w-full min-w-0 items-center justify-between gap-3 px-4 lg:px-6">
              <div className="flex min-w-0 flex-1 items-center gap-1 lg:gap-2">
                <SidebarTrigger className="-ml-1" />
                <Separator
                  orientation="vertical"
                  className="mx-2 data-[orientation=vertical]:h-4 data-[orientation=vertical]:self-center"
                />
                <WorkspaceBreadcrumbs />
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <TaskRunningIndicator />
                <ProjectSwitcher scope="project" />
                <LayoutControls />
                <ThemeSwitcher />
                <AccountSwitcher />
              </div>
            </div>
          </header>
          <div className="flex min-h-0 flex-1 flex-col p-4 md:p-6">
            <AuthGuard>{children}</AuthGuard>
          </div>
        </SidebarInset>
      </WorkspaceBreadcrumbProvider>
    </SidebarProvider>
  );
}
