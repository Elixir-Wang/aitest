"use client";

import { useMemo } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { PerformanceDataConfig } from "@/lib/api-client";

export function PerformanceDataEditor({
  value,
  onChange,
}: {
  value: PerformanceDataConfig;
  onChange: (value: PerformanceDataConfig) => void;
}) {
  const jsonText = useMemo(() => JSON.stringify(value.json_rows, null, 2), [value.json_rows]);

  function setSource(source: PerformanceDataConfig["source"]) {
    onChange({ ...value, source, json_rows: source === "fixed" ? [] : value.json_rows });
  }

  async function loadCsv(file: File | undefined) {
    if (!file) return;
    const rows = parseCsv(await file.text());
    onChange({ ...value, source: "csv", csv_file_name: file.name, csv_file_path: "", json_rows: rows });
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="数据来源">
          <select
            className="h-9 w-full rounded-lg border bg-background px-3 text-sm"
            onChange={(event) => setSource(event.target.value as PerformanceDataConfig["source"])}
            value={value.source}
          >
            <option value="fixed">固定请求数据</option>
            <option value="json">JSON 数据列表</option>
            <option value="csv">CSV 文件</option>
          </select>
        </Field>
        <Field label="取值策略">
          <select
            className="h-9 w-full rounded-lg border bg-background px-3 text-sm"
            disabled={value.source === "fixed"}
            onChange={(event) =>
              onChange({
                ...value,
                selection_strategy: event.target.value as PerformanceDataConfig["selection_strategy"],
              })
            }
            value={value.selection_strategy}
          >
            <option value="sequential_loop">顺序循环</option>
            <option value="random">随机选择</option>
          </select>
        </Field>
      </div>
      {value.source === "json" ? (
        <Field label="JSON 数据列表">
          <Textarea
            className="min-h-48 font-mono text-xs"
            onChange={(event) => {
              try {
                const parsed = JSON.parse(event.target.value);
                if (Array.isArray(parsed)) onChange({ ...value, json_rows: parsed });
              } catch {
                return;
              }
            }}
            value={jsonText}
          />
        </Field>
      ) : null}
      {value.source === "csv" ? (
        <Field label="CSV 文件">
          <Input accept=".csv,text/csv" onChange={(event) => void loadCsv(event.target.files?.[0])} type="file" />
          {value.csv_file_name ? (
            <p className="mt-2 text-muted-foreground text-xs">已读取：{value.csv_file_name}</p>
          ) : null}
        </Field>
      ) : null}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Label className="mb-2">{label}</Label>
      {children}
    </div>
  );
}

function parseCsv(content: string): Array<Record<string, string>> {
  const lines = content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map((item) => item.trim());
  return lines.slice(1).map((line) => {
    const values = line.split(",");
    return Object.fromEntries(headers.map((header, index) => [header, values[index]?.trim() ?? ""]));
  });
}
