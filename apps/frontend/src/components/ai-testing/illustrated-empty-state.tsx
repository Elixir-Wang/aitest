import type { ReactElement } from "react";

import Image from "next/image";

import { cn } from "@/lib/utils";

type IllustratedEmptyStateProps = {
  title: string;
  description: string;
  action?: ReactElement | null;
  className?: string;
};

export function IllustratedEmptyState({ title, description, action, className }: IllustratedEmptyStateProps) {
  return (
    <div className={cn("flex min-h-72 items-center justify-center px-6 py-8 text-center", className)}>
      <div className="flex max-w-md flex-col items-center">
        <Image
          alt=""
          aria-hidden="true"
          className="h-36 w-48 object-contain"
          height={180}
          loading="eager"
          src="/illustrations/api-cases-empty-right.svg"
          width={240}
        />
        <div className="mt-3 font-medium text-foreground text-sm">{title}</div>
        <p className="mt-1 text-muted-foreground text-sm">{description}</p>
        {action ? <div className="mt-5">{action}</div> : null}
      </div>
    </div>
  );
}
