import { Suspense } from "react";

import { Globe } from "lucide-react";

import { APP_CONFIG } from "@/config/app-config";

import { LoginForm } from "../../_components/login-form";

export default function LoginV2() {
  return (
    <>
      <div className="mx-auto flex w-full flex-col justify-center space-y-8 sm:w-[350px]">
        <div className="space-y-2 text-center">
          <h1 className="font-medium text-3xl">登录 AI 测试系统</h1>
          <p className="text-muted-foreground text-sm">请输入管理员分配的账号和密码。</p>
        </div>
        <div className="space-y-4">
          <Suspense>
            <LoginForm />
          </Suspense>
        </div>
      </div>

      <div className="absolute bottom-5 flex w-full justify-between px-10">
        <div className="text-sm">{APP_CONFIG.copyright}</div>
        <div className="flex items-center gap-1 text-sm">
          <Globe className="size-4 text-muted-foreground" />
          ENG
        </div>
      </div>
    </>
  );
}
