"use client";

import { useEffect, useMemo, useState } from "react";

import { useRouter } from "next/navigation";

import { ArrowLeft, Loader2, Upload } from "lucide-react";
import { toast } from "sonner";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import FileUpload1 from "@/components/ui/file-upload-1";
import { Input } from "@/components/ui/input";
import type { ApiProject } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";

type RequirementUploadPageProps = {
  title: string;
  breadcrumbs: string[];
  description: string;
  defaultProjectId: string;
  projects: ApiProject[];
  backHref: string;
  projectScope: "all" | "project";
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export function RequirementUploadPage({
  title,
  breadcrumbs,
  description,
  defaultProjectId,
  projects,
  backHref,
  projectScope,
}: RequirementUploadPageProps) {
  const router = useRouter();
  const token = useAuthStore((state) => state.token);
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState("");
  const [projectId, setProjectId] = useState(defaultProjectId);
  const [submitting, setSubmitting] = useState(false);
  const [uploadStates, setUploadStates] = useState<
    Record<string, { progress: number; status: "idle" | "uploading" | "completed" | "error" }>
  >({});
  const selectedProjectName = projects.find((project) => project.id === projectId)?.name ?? "";

  useEffect(() => {
    setProjectId(defaultProjectId);
  }, [defaultProjectId]);

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
    const unsupportedFile = files.find((file) => !isSupportedRequirementFile(file));
    if (unsupportedFile) {
      toast.error(`仅支持 PDF、Word、TXT、MD 文件：${unsupportedFile.name}`);
      return;
    }
    if (files.length === 0) {
      toast.error("请选择至少一个需求文件");
      return;
    }
    if (!inferredName) {
      toast.error("请填写需求名称");
      return;
    }
    if (!projectId) {
      toast.error("请选择关联项目");
      return;
    }

    setSubmitting(true);
    try {
      for (const file of files) {
        const fileKey = getFileKey(file);
        setUploadStates((current) => ({
          ...current,
          [fileKey]: { progress: 1, status: "uploading" },
        }));
        await new Promise<void>((resolve) => {
          window.requestAnimationFrame(() => resolve());
        });
        await uploadSingleFile(file, inferredName, token, (nextProgress) => {
          setUploadStates((current) => ({
            ...current,
            [fileKey]: { progress: nextProgress, status: nextProgress >= 100 ? "completed" : "uploading" },
          }));
        });
        setUploadStates((current) => ({
          ...current,
          [fileKey]: { progress: 100, status: "completed" },
        }));
      }
      toast.success("需求文件已上传并进入解析");
      router.push(backHref);
      router.refresh();
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "需求上传失败");
      if (requestError instanceof Error) {
        const failedKey = files.find((file) => requestError.message.includes(file.name));
        if (failedKey) {
          setUploadStates((current) => ({
            ...current,
            [getFileKey(failedKey)]: { progress: currentProgress(current, failedKey), status: "error" },
          }));
        }
      }
    } finally {
      setSubmitting(false);
    }
  }

  function uploadSingleFile(
    file: File,
    requirementName: string,
    accessToken: string | null,
    onProgress: (progress: number) => void,
  ) {
    return new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${apiBase}/projects/${projectId}/requirements`);
      if (accessToken) {
        xhr.setRequestHeader("Authorization", `Bearer ${accessToken}`);
      }
      xhr.upload.onprogress = (event) => {
        if (!event.lengthComputable) {
          return;
        }
        onProgress(Math.min(99, Math.round((event.loaded / event.total) * 100)));
      };
      xhr.onloadstart = () => onProgress(1);
      xhr.onload = () => {
        const payload = tryParseJson(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) {
          onProgress(100);
          resolve();
          return;
        }
        reject(new Error(`${file.name}: ${payload?.detail?.message ?? payload?.detail ?? "需求上传失败"}`));
      };
      xhr.onerror = () => reject(new Error("网络异常，需求上传失败"));
      const formData = new FormData();
      formData.append("files", file);
      formData.append("name", requirementName);
      formData.append("document_type", "PRD");
      formData.append("change_summary", "上传需求文件");
      xhr.send(formData);
    });
  }

  function tryParseJson(value: string) {
    try {
      return JSON.parse(value);
    } catch {
      return null;
    }
  }

  return (
    <PageShell breadcrumbs={breadcrumbs} description={description} projectScope={projectScope} tabs={[]} title={title}>
      <ShellSection className="space-y-6">
        <div className="flex max-w-4xl flex-col gap-5">
          <Field>
            <FieldLabel htmlFor="requirement-project">关联项目</FieldLabel>
            <Select id="requirement-project" placeholder="请选择关联项目" setValue={setProjectId} value={projectId}>
              {projects.map((project) => (
                <SelectOption key={project.id} value={project.id}>
                  {project.name}
                </SelectOption>
              ))}
            </Select>
            <FieldDescription>
              {selectedProjectName ? `需求将上传到：${selectedProjectName}` : "请选择本次需求所属项目。"}
            </FieldDescription>
          </Field>

          <Field>
            <FieldLabel htmlFor="requirement-name">需求名称</FieldLabel>
            <Input
              id="requirement-name"
              placeholder="请输入需求名称"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <FieldDescription>单文件上传时不填会使用文件名。</FieldDescription>
          </Field>

          <div className="space-y-2">
            <FieldLabel>上传文件</FieldLabel>
            <FileUpload1
              accept={{
                "application/pdf": [".pdf"],
                "application/msword": [".doc"],
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
                "text/markdown": [".md", ".markdown"],
                "text/plain": [".txt"],
              }}
              files={files}
              hint="仅支持 PDF、Word（doc/docx）、TXT 文件；MD 将直接保存为 Markdown，不再解析"
              maxFiles={10}
              uploadStates={uploadStates}
              onFilesChange={setFiles}
            />
          </div>

          <div className="flex items-center justify-center gap-2 border-t pt-5">
            <Button disabled={submitting} type="button" variant="outline" onClick={() => router.push(backHref)}>
              <ArrowLeft className="size-4" />
              返回列表
            </Button>
            <Button disabled={submitting || files.length === 0 || !projectId} type="button" onClick={submitUpload}>
              {submitting ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
              {submitting ? "上传并解析中" : "上传并解析"}
            </Button>
          </div>
        </div>
      </ShellSection>
    </PageShell>
  );
}

function isSupportedRequirementFile(file: File) {
  return /\.(pdf|doc|docx|txt|md|markdown)$/i.test(file.name);
}

function getFileKey(file: File) {
  return `${file.name}-${file.lastModified}-${file.size}`;
}

function currentProgress(
  states: Record<string, { progress: number; status: "idle" | "uploading" | "completed" | "error" }>,
  file: File,
) {
  return states[getFileKey(file)]?.progress ?? 0;
}
