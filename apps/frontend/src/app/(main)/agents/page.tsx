"use client";

import { useState } from "react";

import { Bot, Sparkles } from "lucide-react";

import { PageShell } from "@/components/ai-testing/page-shell";
import { SiliconOfficeDashboard } from "@/components/ai-testing/silicon-office/office-dashboard";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function SiliconEmployeesPage() {
  const [open, setOpen] = useState(true);

  return (
    <>
      <PageShell breadcrumbs={moduleBreadcrumbs("agents")} fillViewport projectScope="all" title="硅基员工">
        <SiliconOfficeDashboard embedded />
      </PageShell>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="overflow-hidden border-primary/20 p-0 shadow-[0_24px_70px_rgba(15,23,42,0.22)] sm:max-w-md [&_[data-slot=dialog-close]]:top-4 [&_[data-slot=dialog-close]]:right-4 [&_[data-slot=dialog-close]]:rounded-full [&_[data-slot=dialog-close]]:text-muted-foreground [&_[data-slot=dialog-close]]:hover:bg-primary/10 [&_[data-slot=dialog-close]]:hover:text-primary">
          <div aria-hidden="true" className="h-1 bg-primary" />
          <DialogHeader className="gap-0 px-6 pt-6 pb-7">
            <div className="mb-5 flex items-start gap-4 pr-8">
              <div className="relative flex size-12 shrink-0 items-center justify-center rounded-lg border border-primary/15 bg-primary/10 text-primary shadow-sm">
                <Bot className="size-6" strokeWidth={1.8} />
                <span className="absolute -right-1 -bottom-1 flex size-4 items-center justify-center rounded-full border-2 border-popover bg-emerald-500 text-white">
                  <Sparkles className="size-2.5" strokeWidth={2.5} />
                </span>
              </div>

              <div className="min-w-0 pt-0.5">
                <div className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-primary/15 bg-primary/5 px-2.5 py-1 font-medium text-[11px] text-primary leading-none">
                  <span className="size-1.5 rounded-full bg-emerald-500" />
                  功能接入中
                </div>
                <DialogTitle className="font-semibold text-lg leading-7">硅基员工即将上线</DialogTitle>
              </div>
            </div>

            <DialogDescription className="border-border/70 border-t pt-4 text-muted-foreground text-sm leading-6">
              当前功能正在接入中，敬请期待。关闭提示后可预览硅基员工界面。
            </DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    </>
  );
}
