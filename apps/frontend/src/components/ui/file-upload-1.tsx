"use client";

import { FileUpload } from "@ark-ui/react/file-upload";
import { File as FileIcon, FileArchive, FileSpreadsheet, FileText, Headphones, Image, Video, X } from "lucide-react";

import { cn } from "@/lib/utils";

function getFileIcon(file: File) {
  const fileType = file.type;
  const fileName = file.name.toLowerCase();

  if (fileType.includes("pdf") || fileName.endsWith(".pdf") || fileType.includes("word") || fileName.endsWith(".doc") || fileName.endsWith(".docx")) {
    return <FileText className="size-4 opacity-60" />;
  }
  if (fileType.includes("zip") || fileType.includes("archive") || fileName.endsWith(".zip") || fileName.endsWith(".rar")) {
    return <FileArchive className="size-4 opacity-60" />;
  }
  if (fileType.includes("excel") || fileName.endsWith(".xls") || fileName.endsWith(".xlsx")) {
    return <FileSpreadsheet className="size-4 opacity-60" />;
  }
  if (fileType.includes("video/")) {
    return <Video className="size-4 opacity-60" />;
  }
  if (fileType.includes("audio/")) {
    return <Headphones className="size-4 opacity-60" />;
  }
  if (fileType.startsWith("image/")) {
    return <Image className="size-4 opacity-60" />;
  }
  return <FileIcon className="size-4 opacity-60" />;
}

type FileUpload1Props = {
  files: File[];
  onFilesChange: (files: File[]) => void;
  className?: string;
  maxFiles?: number;
  maxFileSize?: number;
  accept?: string | string[] | Record<string, string[]>;
};

export default function FileUpload1({
  files,
  onFilesChange,
  className,
  maxFiles = 10,
  maxFileSize = 100 * 1024 * 1024,
  accept,
}: FileUpload1Props) {
  return (
    <FileUpload.Root
      acceptedFiles={files}
      accept={accept}
      className={cn("w-full space-y-4", className)}
      maxFileSize={maxFileSize}
      maxFiles={maxFiles}
      onFileChange={({ acceptedFiles }) => onFilesChange(acceptedFiles)}
    >
      <FileUpload.Context>
        {({ acceptedFiles }) => (
          <>
            <FileUpload.Dropzone className="flex min-h-56 w-full cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-border bg-muted/30 px-6 py-12 transition-colors hover:bg-muted/50">
              <div className="mb-4 flex size-12 items-center justify-center rounded-full border bg-background">
                <FileText className="size-5 text-muted-foreground" />
              </div>
              <div className="space-y-2 text-center">
                <h3 className="font-medium text-sm">上传需求文件</h3>
                <p className="text-muted-foreground text-sm">拖拽文件到此处，或点击选择文件</p>
                <p className="text-muted-foreground text-xs">最多 {maxFiles} 个文件，单文件不超过 {Math.round(maxFileSize / 1024 / 1024)}MB</p>
              </div>
            </FileUpload.Dropzone>

            {acceptedFiles.length > 0 ? (
              <div className="space-y-3">
                <FileUpload.ItemGroup>
                  {acceptedFiles.map((file) => (
                    <FileUpload.Item file={file} key={`${file.name}-${file.lastModified}`}>
                      <div className="flex items-center gap-3 rounded-lg border bg-background p-3">
                        <div className="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-lg border bg-muted/40">
                          {file.type.startsWith("image/") ? (
                            <FileUpload.ItemPreview type="image/*">
                              <FileUpload.ItemPreviewImage className="size-full object-cover" />
                            </FileUpload.ItemPreview>
                          ) : (
                            getFileIcon(file)
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
                          <FileUpload.ItemName className="truncate font-medium text-sm" />
                          <FileUpload.ItemSizeText className="text-muted-foreground text-xs" />
                        </div>
                        <FileUpload.ItemDeleteTrigger className="flex size-7 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground">
                          <X className="size-4" />
                        </FileUpload.ItemDeleteTrigger>
                      </div>
                    </FileUpload.Item>
                  ))}
                </FileUpload.ItemGroup>
                <FileUpload.ClearTrigger className="inline-flex h-8 items-center rounded-md border bg-background px-3 font-medium text-xs hover:bg-muted">
                  移除全部文件
                </FileUpload.ClearTrigger>
              </div>
            ) : null}
          </>
        )}
      </FileUpload.Context>
      <FileUpload.HiddenInput />
    </FileUpload.Root>
  );
}
