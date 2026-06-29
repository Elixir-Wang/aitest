"use client";

import { useEffect, useRef, useState } from "react";

import { useRouter, useSearchParams } from "next/navigation";

import { ArrowLeft, Loader2, Upload } from "lucide-react";
import { toast } from "sonner";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import FileUpload1 from "@/components/ui/file-upload-1";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import { API_BASE_URL, type ApiProject, apiErrorFromXhr, apiRequest } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";
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

type RequirementOption = {
  id: string;
  name: string;
  file_count: number;
};

type UploadMode = "new" | "append";

type UploadResponse = {
  document: {
    id: string;
    project_id: string;
    name: string;
  };
  files: Array<{
    id: string;
    original_filename: string;
    conversion_status: string;
    conversion_summary: string;
    created_at: string;
  }>;
};

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
  const searchParams = useSearchParams();
  const token = useAuthStore((state) => state.token);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState("");
  const [projectId, setProjectId] = useState(defaultProjectId);
  const [mode, setMode] = useState<UploadMode>("new");
  const [requirements, setRequirements] = useState<RequirementOption[]>([]);
  const [existingDocumentId, setExistingDocumentId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [uploadStates, setUploadStates] = useState<
    Record<string, { progress: number; status: "idle" | "uploading" | "completed" | "error" }>
  >({});
  const selectedRequirement = requirements.find((item) => item.id === existingDocumentId);

  useEffect(() => {
    setProjectId(defaultProjectId);
  }, [defaultProjectId]);

  useEffect(() => {
    const queryMode = searchParams.get("mode");
    const queryDocumentId = searchParams.get("documentId");
    if (queryMode === "append") {
      setMode("append");
    }
    if (queryDocumentId) {
      setExistingDocumentId(queryDocumentId);
    }
  }, [searchParams]);

  useEffect(() => {
    let ignore = false;

    async function loadRequirements() {
      if (!projectId || mode !== "append") {
        return;
      }
      try {
        const data = await apiRequest<RequirementOption[]>(`/projects/${projectId}/requirements`);
        if (!ignore) {
          setRequirements(data);
        }
      } catch (requestError) {
        if (!ignore) {
          reportError(requestError, {
            fallbackMessage: "需求列表加载失败",
            actionLabel: "加载可追加需求",
            method: "GET",
            path: `/projects/${projectId}/requirements`,
          });
          setRequirements([]);
        }
      }
    }

    void loadRequirements();
    return () => {
      ignore = true;
    };
  }, [mode, projectId]);

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
    if (!projectId) {
      toast.error("请选择关联项目");
      return;
    }
    if (mode === "new") {
      if (!name.trim()) {
        setNameError("请填写需求名称");
        nameInputRef.current?.focus();
        return;
      }
    }
    if (mode === "append" && !existingDocumentId) {
      toast.error("请选择要追加文件的需求");
      return;
    }

    setSubmitting(true);
    const nextUploadStates = Object.fromEntries(
      files.map((file) => [getFileKey(file), { progress: 1, status: "uploading" as const }]),
    );
    setUploadStates(nextUploadStates);
    try {
      const result = await uploadFiles();
      setUploadStates(
        Object.fromEntries(files.map((file) => [getFileKey(file), { progress: 100, status: "completed" as const }])),
      );
      if (mode === "new") {
        toast.success("需求文件已添加，开始进行需求文件标准化");
      } else {
        toast.success("文件已添加，可在原始文件列表中设为主需求");
      }
      notifyAiTaskStarted();
      router.push(`/projects/${result.document.project_id}/requirements/${result.document.id}?tab=original`);
      router.refresh();
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "需求上传失败",
        actionLabel: mode === "new" ? "上传需求文件" : "追加需求文件",
        method: "POST",
        path: `/projects/${projectId}/requirements`,
      });
      setUploadStates(
        Object.fromEntries(files.map((file) => [getFileKey(file), { progress: 0, status: "error" as const }])),
      );
    } finally {
      setSubmitting(false);
    }
  }

  function uploadFiles() {
    return new Promise<UploadResponse>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE_URL}/projects/${projectId}/requirements`);
      if (token) {
        xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      }
      xhr.upload.onprogress = (event) => {
        if (!event.lengthComputable) {
          return;
        }
        const progress = Math.min(99, Math.round((event.loaded / event.total) * 100));
        setUploadStates(
          Object.fromEntries(files.map((file) => [getFileKey(file), { progress, status: "uploading" as const }])),
        );
      };
      xhr.onload = () => {
        const payload = tryParseJson(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(payload?.data ?? payload);
          return;
        }
        reject(apiErrorFromXhr(xhr, "需求上传失败"));
      };
      xhr.onerror = () => reject(apiErrorFromXhr(xhr, "网络异常，需求上传失败"));
      const formData = new FormData();
      formData.append("mode", mode);
      if (mode === "new") {
        formData.append("document_name", name.trim());
      } else {
        formData.append("existing_document_id", existingDocumentId);
      }
      for (const file of files) {
        formData.append("files", file);
      }
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

  function handleFilesChange(nextFiles: File[]) {
    setFiles(nextFiles);
    if (mode !== "new" || nextFiles.length === 0) {
      return;
    }
    setName((current) => {
      if (current.trim()) {
        return current;
      }
      return fileNameWithoutExtension(nextFiles[0].name);
    });
    setNameError("");
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
          </Field>

          <Field>
            <FieldLabel>上传模式</FieldLabel>
            <RadioGroup
              className="grid gap-2 sm:grid-cols-2"
              value={mode}
              onValueChange={(value) => setMode(value as UploadMode)}
            >
              <Label className="flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm">
                <RadioGroupItem value="new" />
                新建需求
              </Label>
              <Label className="flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm">
                <RadioGroupItem value="append" />
                追加到已有需求
              </Label>
            </RadioGroup>
          </Field>

          {mode === "new" ? (
            <Field>
              <FieldLabel htmlFor="requirement-name">需求名称</FieldLabel>
              <Input
                id="requirement-name"
                placeholder="请输入需求名称"
                ref={nameInputRef}
                value={name}
                onChange={(event) => {
                  setName(event.target.value);
                  setNameError("");
                }}
              />
              {nameError ? <div className="text-destructive text-xs">{nameError}</div> : null}
            </Field>
          ) : (
            <Field>
              <FieldLabel htmlFor="requirement-select">选择已有需求</FieldLabel>
              <Select placeholder="请选择需求" setValue={setExistingDocumentId} value={existingDocumentId}>
                {requirements.map((item) => (
                  <SelectOption key={item.id} value={item.id}>
                    {item.name}
                  </SelectOption>
                ))}
              </Select>
              {selectedRequirement ? (
                <FieldDescription>当前已有来源文件：{selectedRequirement.file_count} 个</FieldDescription>
              ) : null}
            </Field>
          )}

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
              hint="仅支持 PDF、Word（doc/docx）、TXT、MD 文件；选择完成后统一提交"
              maxFiles={10}
              uploadStates={uploadStates}
              onFilesChange={handleFilesChange}
            />
          </div>

          <div className="flex items-center justify-center gap-2 border-t pt-5">
            <Button disabled={submitting} type="button" variant="outline" onClick={() => router.push(backHref)}>
              <ArrowLeft className="size-4" />
              返回列表
            </Button>
            <Button disabled={submitting || files.length === 0 || !projectId} type="button" onClick={submitUpload}>
              {submitting ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
              {submitting ? "提交中" : "提交"}
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

function fileNameWithoutExtension(filename: string) {
  const baseName = filename.replace(/\\/g, "/").split("/").pop() ?? filename;
  const dotIndex = baseName.lastIndexOf(".");
  if (dotIndex <= 0) {
    return baseName;
  }
  return baseName.slice(0, dotIndex);
}
