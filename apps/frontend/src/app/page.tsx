"use client";

import { useEffect } from "react";

import { useRouter } from "next/navigation";

import { Spinner } from "@/components/ui/spinner";
import { useAuthStore } from "@/stores/auth-store";

export default function Home() {
  const router = useRouter();
  const { hasHydrated, hydrate, token } = useAuthStore();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (!hasHydrated) {
      return;
    }

    router.replace(token ? "/dashboard" : "/auth/v1/login");
  }, [hasHydrated, router, token]);

  return (
    <div className="flex min-h-dvh items-center justify-center text-muted-foreground text-sm">
      <Spinner className="mr-2 size-4" />
      正在进入 AI 测试系统
    </div>
  );
}
