import { Command } from "lucide-react";

import { RegisterForm } from "@/app/(main)/auth/_components/register-form";

export default function RegisterV1() {
  return (
    <div className="flex h-dvh">
      <div className="flex w-full items-center justify-center bg-background p-8 lg:w-2/3">
        <div className="w-full max-w-md space-y-10 py-24 lg:py-32">
          <div className="space-y-4 text-center">
            <div className="font-medium tracking-tight">账号申请</div>
            <div className="mx-auto max-w-xl text-muted-foreground">
              AI 测试系统第一版由管理员创建账号，不开放公开注册。
            </div>
          </div>
          <div className="space-y-4">
            <RegisterForm />
          </div>
        </div>
      </div>

      <div className="hidden bg-primary lg:block lg:w-1/3">
        <div className="flex h-full flex-col items-center justify-center p-12 text-center">
          <div className="space-y-6">
            <Command className="mx-auto size-12 text-primary-foreground" />
            <div className="space-y-2">
              <h1 className="font-light text-5xl text-primary-foreground">AI 测试系统</h1>
              <p className="text-primary-foreground/80 text-xl">请通过管理员分配账号进入工作台。</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
