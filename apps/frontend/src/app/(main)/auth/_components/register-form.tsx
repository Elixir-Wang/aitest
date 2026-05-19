import { EmptyState } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";

export function RegisterForm() {
  return (
    <div className="space-y-4">
      <EmptyState
        description="第一版不开放自助注册。账号由管理员在“用户与权限”中创建并分配项目。"
        status="管理员创建"
        title="请联系管理员创建账号"
      />
      <Button asChild className="w-full" variant="outline">
        <a href="/auth/v1/login">返回登录</a>
      </Button>
    </div>
  );
}
