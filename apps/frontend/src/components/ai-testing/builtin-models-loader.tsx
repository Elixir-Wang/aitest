"use client";

import { useState } from "react";

import { PackagePlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { apiRequest } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";
import { toast } from "@/lib/toast";

type BuiltinModelLoadResult = {
  created: number;
  updated: number;
  unchanged: number;
};

export function BuiltinModelsLoader({ onLoaded }: { onLoaded: () => void | Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function closeDialog(next: boolean) {
    setOpen(next);
    if (!next) {
      setPassword("");
    }
  }

  async function submit() {
    setSubmitting(true);
    try {
      const result = await apiRequest<BuiltinModelLoadResult>("/models/providers/load-builtin", {
        body: JSON.stringify({ password }),
        method: "POST",
      });
      closeDialog(false);
      toast.success("内置模型已加载", {
        description: `新增 ${result.created} 个，更新 ${result.updated} 个，已存在 ${result.unchanged} 个。`,
      });
      await onLoaded();
    } catch (error) {
      reportError(error, {
        fallbackMessage: "内置模型加载失败",
        actionLabel: "加载内置模型",
        method: "POST",
        path: "/models/providers/load-builtin",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Button onClick={() => setOpen(true)} type="button" variant="outline">
        <PackagePlus className="size-4" />
        加载内置模型
      </Button>
      <Dialog onOpenChange={closeDialog} open={open}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>加载内置模型</DialogTitle>
            <DialogDescription>
              输入访问密码后，服务端内置的模型配置会写入模型列表。密码不正确无法加载。
            </DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="builtin-model-password">访问密码</FieldLabel>
              <Input
                autoComplete="off"
                id="builtin-model-password"
                onChange={(event) => setPassword(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && password.trim() && !submitting) {
                    void submit();
                  }
                }}
                placeholder="请输入内置模型访问密码"
                type="password"
                value={password}
              />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button onClick={() => closeDialog(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={!password.trim() || submitting} onClick={submit} type="button">
              {submitting ? "加载中…" : "加载"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
