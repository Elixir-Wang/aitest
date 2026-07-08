"use client";

import { createContext, type ReactNode, useContext, useMemo, useState } from "react";

import Link from "next/link";

import { ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

export type BreadcrumbItem = {
  label: string;
  href?: string;
};

type BreadcrumbContextValue = {
  breadcrumbs: BreadcrumbItem[];
  setBreadcrumbs: (items: BreadcrumbItem[]) => void;
};

const BreadcrumbContext = createContext<BreadcrumbContextValue | null>(null);

export function WorkspaceBreadcrumbProvider({ children }: { children: ReactNode }) {
  const [breadcrumbs, setBreadcrumbs] = useState<BreadcrumbItem[]>([]);
  const value = useMemo(() => ({ breadcrumbs, setBreadcrumbs }), [breadcrumbs]);

  return <BreadcrumbContext.Provider value={value}>{children}</BreadcrumbContext.Provider>;
}

export function useWorkspaceBreadcrumbs() {
  const context = useContext(BreadcrumbContext);

  if (!context) {
    throw new Error("useWorkspaceBreadcrumbs must be used within WorkspaceBreadcrumbProvider.");
  }

  return context;
}

export function WorkspaceBreadcrumbs() {
  const { breadcrumbs } = useWorkspaceBreadcrumbs();
  const visibleItems = breadcrumbs.filter((item) => item.label.trim().length > 0);

  if (visibleItems.length === 0) {
    return null;
  }

  return (
    <nav aria-label="页面路径" className="min-w-0 flex-1 overflow-hidden">
      <ol className="flex min-w-0 items-center gap-1 text-sm">
        {visibleItems.map((item, index) => {
          const isCurrent = index === visibleItems.length - 1;
          const content = (
            <span
              className={cn(
                "block max-w-28 truncate sm:max-w-40 lg:max-w-56",
                isCurrent ? "font-medium text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
              title={item.label}
            >
              {item.label}
            </span>
          );

          return (
            <li className="flex min-w-0 items-center gap-1" key={`${item.href ?? item.label}-${item.label}`}>
              {index > 0 ? <ChevronRight className="size-3.5 shrink-0 text-muted-foreground/70" /> : null}
              {!isCurrent && item.href ? (
                <Link
                  className="min-w-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  href={item.href}
                >
                  {content}
                </Link>
              ) : (
                content
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
