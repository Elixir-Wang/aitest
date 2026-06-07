"use client";

import { useRouter, useSearchParams } from "next/navigation";

import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldContent, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { type ApiUser, apiRequest, roleToLabel } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";
import { useAuthStore } from "@/stores/auth-store";

const formSchema = z.object({
  email: z.string().min(1, { message: "请输入用户名或邮箱。" }),
  password: z.string().min(1, { message: "请输入密码。" }),
  remember: z.boolean().optional(),
});

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const login = useAuthStore((state) => state.login);
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: "admin",
      password: "admin",
      remember: false,
    },
  });

  const onSubmit = async (data: z.infer<typeof formSchema>) => {
    try {
      const result = await apiRequest<{ access_token: string; current_user: ApiUser }>("/auth/login", {
        body: JSON.stringify({ password: data.password, username: data.email }),
        method: "POST",
      });
      login({
        token: result.access_token,
        remember: data.remember,
        user: {
          email: result.current_user.email,
          name: result.current_user.username,
          role: result.current_user.role,
        },
      });
      toast.success("登录成功", {
        description: `已以${roleToLabel(result.current_user.role)}身份进入 AI 测试系统。`,
      });
      router.replace(searchParams.get("next") || "/dashboard");
    } catch (error) {
      reportError(error, {
        fallbackMessage: "登录失败，请检查账号和密码。",
        actionLabel: "用户登录",
        method: "POST",
        path: "/auth/login",
      });
    }
  };

  return (
    <form noValidate onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <FieldGroup className="gap-4">
        <Controller
          control={form.control}
          name="email"
          render={({ field, fieldState }) => (
            <Field className="gap-1.5" data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="login-email">用户名或邮箱</FieldLabel>
              <Input
                {...field}
                id="login-email"
                type="text"
                placeholder="admin@example.com"
                autoComplete="username"
                aria-invalid={fieldState.invalid}
              />
              {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
            </Field>
          )}
        />
        <Controller
          control={form.control}
          name="password"
          render={({ field, fieldState }) => (
            <Field className="gap-1.5" data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="login-password">密码</FieldLabel>
              <Input
                {...field}
                id="login-password"
                type="password"
                placeholder="••••••••"
                autoComplete="current-password"
                aria-invalid={fieldState.invalid}
              />
              {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
            </Field>
          )}
        />
        <Controller
          control={form.control}
          name="remember"
          render={({ field, fieldState }) => (
            <Field orientation="horizontal" data-invalid={fieldState.invalid}>
              <Checkbox
                id="login-remember"
                name={field.name}
                checked={field.value}
                onCheckedChange={(checked) => field.onChange(Boolean(checked))}
                aria-invalid={fieldState.invalid}
              />
              <FieldContent>
                <FieldLabel htmlFor="login-remember" className="font-normal">
                  记住登录状态
                </FieldLabel>
                {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
              </FieldContent>
            </Field>
          )}
        />
      </FieldGroup>
      <Button className="w-full" type="submit">
        登录
      </Button>
    </form>
  );
}
