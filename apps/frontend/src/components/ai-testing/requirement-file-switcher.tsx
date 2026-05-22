"use client";

import { FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type RequirementSwitcherFile = {
  id: string;
  original_filename: string;
  file_format: string;
  conversion_status: string;
  mapping_status: string;
  created_at: string;
};

type RequirementFileSwitcherProps = {
  files: RequirementSwitcherFile[];
  selectedFileId: string;
  onSelect: (fileId: string) => void;
  statusLabel: (status: string) => string;
};

export function RequirementFileSwitcher({
  files,
  selectedFileId,
  onSelect,
  statusLabel,
}: RequirementFileSwitcherProps) {
  if (files.length === 0) {
    return <div className="rounded-lg border border-dashed p-6 text-center text-muted-foreground text-sm">暂无文件</div>;
  }

  return (
    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
      {files.map((file) => (
        <Button
          className={cn(
            "h-auto justify-start gap-3 p-3 text-left",
            selectedFileId === file.id && "border-primary bg-primary/5"
          )}
          key={file.id}
          onClick={() => onSelect(file.id)}
          type="button"
          variant="outline"
        >
          <FileText className="size-4 shrink-0 text-muted-foreground" />
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium text-sm">{file.original_filename}</span>
            <span className="mt-1 flex flex-wrap gap-1">
              <Badge variant="secondary">{file.file_format.toUpperCase()}</Badge>
              <Badge variant={file.conversion_status === "failed" ? "destructive" : "outline"}>
                {statusLabel(file.conversion_status)}
              </Badge>
            </span>
          </span>
        </Button>
      ))}
    </div>
  );
}
