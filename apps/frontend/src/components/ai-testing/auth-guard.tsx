"use client";

import { type ReactNode, useEffect } from "react";

import { usePathname, useRouter } from "next/navigation";

import { Spinner } from "@/components/ui/spinner";
import { useAuthStore } from "@/stores/auth-store";

export function AuthGuard({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { hasHydrated, hydrate, token } = useAuthStore();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (hasHydrated && !token) {
      router.replace(`/auth/v1/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [hasHydrated, pathname, router, token]);

  if (!hasHydrated || !token) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-muted-foreground text-sm">
        <Spinner className="mr-2 size-4" />
        正在检查登录状态
      </div>
    );
  }

  return children;
}
