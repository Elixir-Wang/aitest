"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

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
  getFileLabel?: (filename: string) => string;
};

export function RequirementFileSwitcher({
  files,
  selectedFileId,
  onSelect,
  getFileLabel = displayFilename,
}: RequirementFileSwitcherProps) {
  const selectedFile = files.find((file) => file.id === selectedFileId) ?? files[0];
  const selectedFilename = selectedFile ? getFileLabel(selectedFile.original_filename) : "";

  if (files.length === 0) {
    return <div className="text-muted-foreground text-sm">暂无文件</div>;
  }

  return (
    <Select onValueChange={onSelect} value={selectedFile?.id}>
      <SelectTrigger aria-label="切换文件" className="h-9 w-fit min-w-0 max-w-full gap-2" title={selectedFilename}>
        <SelectValue placeholder="选择文件" />
      </SelectTrigger>
      <SelectContent
        align="center"
        className="w-max min-w-(--radix-select-trigger-width)"
        position="popper"
        viewportClassName="w-max"
      >
        {files.map((file) => (
          <SelectItem className="whitespace-nowrap" key={file.id} value={file.id}>
            {getFileLabel(file.original_filename)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function displayFilename(filename: string) {
  return filename.split(/[\\/]/).filter(Boolean).pop() ?? filename;
}
