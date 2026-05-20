"use client";

import { useMemo, useState } from "react";

import { useRouter } from "next/navigation";

import { ArrowLeft, Upload } from "lucide-react";
import { toast } from "sonner";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import FileUpload1 from "@/components/ui/file-upload-1";
import { Input } from "@/components/ui/input";
import { useAuthStore } from "@/stores/auth-store";

type RequirementUploadPageProps = {
  title: string;
  breadcrumbs: string[];
  description: string;
  projectId: string;
  backHref: string;
  projectScope: "all" | "project";
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export function RequirementUploadPage({ title, breadcrumbs, description, projectId, backHref, projectScope }: RequirementUploadPageProps) {
  const router = useRouter();
  const token = useAuthStore((state) => state.token);
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const inferredName = useMemo(() => {
    if (name.trim()) {
      return name.trim();
    }
    if (files.length === 1) {
      return files[0].name.replace(/\.[^.]+$/, "");
    }
    return "";
  }, [files, name]);

  async function submitUpload() {
    if (files.length === 0) {
      toast.error("请选择至少一个需求文件");
      return;
    }

    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    formData.append("name", inferredName);
    formData.append("document_type", "PRD");
    formData.append("change_summary", "上传需求文件");

    setSubmitting(true);
    try {
      const response = await fetch(`${apiBase}/projects/${projectId}/documents`, {
        body: formData,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        method: "POST",
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail?.message ?? "需求上传失败");
      }
      toast.success("需求文件已上传，正在解析");
      router.push(backHref);
      router.refresh();
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "需求上传失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PageShell
      breadcrumbs={breadcrumbs}
      description={description}
      projectScope={projectScope}
      tabs={[]}
      title={title}
    >
      <ShellSection>
        <div className="mb-5 flex items-center justify-between gap-3">
          <Button disabled={submitting} size="sm" type="button" variant="outline" onClick={() => router.push(backHref)}>
            <ArrowLeft className="size-4" />
            返回列表
          </Button>
        </div>
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
          <div className="rounded-lg border bg-muted/30 p-3 text-muted-foreground text-sm">
            上传文件会按 PRD 需求文档处理，原始文件会保存到项目需求目录，并生成 Markdown 工作稿后进入解析中状态。
          </div>
          <FileUpload1 files={files} onFilesChange={setFiles} />
          <Field>
            <FieldLabel htmlFor="requirement-name">需求名称</FieldLabel>
            <Input id="requirement-name" placeholder="不填则使用文件名" value={name} onChange={(event) => setName(event.target.value)} />
            <FieldDescription>多文件上传时建议填写一个批次名称。</FieldDescription>
          </Field>
          <Button className="w-fit" disabled={submitting || files.length === 0} type="button" onClick={submitUpload}>
            <Upload className="size-4" />
            {submitting ? "上传中" : "上传并解析"}
          </Button>
        </div>
      </ShellSection>
    </PageShell>
  );
}
