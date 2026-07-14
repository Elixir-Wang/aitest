"use client";

import { useMemo, useState } from "react";

import { ChevronDown, ChevronRight, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { ApiAutomationEndpoint } from "@/lib/api-client";
import { cn } from "@/lib/utils";

type ApiScenarioAssetPickerProps = {
  endpoints: ApiAutomationEndpoint[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (endpointIds: string[]) => void;
};

const methodTone: Record<string, string> = {
  GET: "border-blue-200 bg-blue-50 text-blue-700",
  POST: "border-emerald-200 bg-emerald-50 text-emerald-700",
  PUT: "border-amber-200 bg-amber-50 text-amber-700",
  PATCH: "border-violet-200 bg-violet-50 text-violet-700",
  DELETE: "border-red-200 bg-red-50 text-red-700",
};

export function ApiScenarioAssetPicker({ endpoints, open, onOpenChange, onConfirm }: ApiScenarioAssetPickerProps) {
  const [query, setQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [expandedGroups, setExpandedGroups] = useState<string[]>([]);
  const groupedEndpoints = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    const visibleEndpoints = keyword
      ? endpoints.filter((endpoint) =>
          [endpoint.method, endpoint.path, endpoint.summary, endpoint.description, ...endpoint.tags]
            .join(" ")
            .toLowerCase()
            .includes(keyword),
        )
      : endpoints;

    return visibleEndpoints.reduce<Record<string, ApiAutomationEndpoint[]>>((groups, endpoint) => {
      const group = endpoint.tags[0]?.trim() || "未分组";
      groups[group] = [...(groups[group] ?? []), endpoint];
      return groups;
    }, {});
  }, [endpoints, query]);
  const groupEntries = Object.entries(groupedEndpoints);
  const searching = query.trim().length > 0;

  function resetPicker() {
    setQuery("");
    setSelectedIds([]);
    setExpandedGroups([]);
  }

  function closePicker() {
    resetPicker();
    onOpenChange(false);
  }

  function handleOpenChange(nextOpen: boolean) {
    if (nextOpen) {
      onOpenChange(true);
      return;
    }
    closePicker();
  }

  function toggleEndpoint(endpointId: string, checked: boolean) {
    setSelectedIds((current) =>
      checked
        ? current.includes(endpointId)
          ? current
          : [...current, endpointId]
        : current.filter((id) => id !== endpointId),
    );
  }

  function toggleGroup(endpointIds: string[], checked: boolean) {
    setSelectedIds((current) =>
      checked
        ? [...current, ...endpointIds.filter((endpointId) => !current.includes(endpointId))]
        : current.filter((endpointId) => !endpointIds.includes(endpointId)),
    );
  }

  function toggleExpandedGroup(group: string) {
    setExpandedGroups((current) =>
      current.includes(group) ? current.filter((item) => item !== group) : [...current, group],
    );
  }

  return (
    <Dialog onOpenChange={handleOpenChange} open={open}>
      <DialogContent className="grid h-[min(720px,85vh)] grid-rows-[auto_auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:max-w-2xl">
        <DialogHeader className="border-b px-5 py-4 pr-12">
          <DialogTitle>选择接口</DialogTitle>
          <DialogDescription>从接口资产中选择一个或多个接口，按选择顺序添加到执行链路。</DialogDescription>
        </DialogHeader>

        <div className="border-b bg-background px-4 py-3">
          <div className="relative">
            <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="h-9 bg-muted/25 pl-9"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索接口名称或路径"
              value={query}
            />
          </div>
        </div>

        <div className="min-h-0 overflow-y-auto bg-muted/15 p-3">
          {groupEntries.map(([group, rows]) => {
            const endpointIds = rows.map((endpoint) => endpoint.id);
            const selectedCount = endpointIds.filter((endpointId) => selectedIds.includes(endpointId)).length;
            const collapsed = searching ? false : !expandedGroups.includes(group);

            return (
              <div className="mb-2.5 last:mb-0" key={group}>
                <div
                  className={cn(
                    "flex w-full items-center gap-2 rounded-lg border px-3 py-2.5 text-left transition-colors",
                    selectedCount > 0
                      ? "border-sky-200 bg-sky-50/85 text-sky-800"
                      : "border-transparent bg-slate-100/80 text-slate-600 hover:border-slate-200 hover:bg-slate-100",
                  )}
                >
                  <Checkbox
                    aria-label={`选择分组 ${group} 的全部接口`}
                    checked={selectedCount === endpointIds.length ? true : selectedCount > 0 ? "indeterminate" : false}
                    className="after:inset-0"
                    onCheckedChange={(checked) => toggleGroup(endpointIds, checked === true)}
                  />
                  <button
                    aria-expanded={!collapsed}
                    className="-my-2.5 -mr-3 flex min-w-0 flex-1 items-center gap-2 rounded-r-lg py-2.5 pr-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
                    onClick={() => toggleExpandedGroup(group)}
                    type="button"
                  >
                    {collapsed ? (
                      <ChevronRight className="size-4 shrink-0" />
                    ) : (
                      <ChevronDown className="size-4 shrink-0" />
                    )}
                    <span className="min-w-0 flex-1 truncate font-medium text-sm">{group}</span>
                    <span className="rounded-full bg-sky-100 px-2.5 py-0.5 font-semibold text-sky-700 text-xs tabular-nums">
                      {rows.length}
                    </span>
                  </button>
                </div>

                {collapsed ? null : (
                  <div className="mt-1.5 space-y-1 pl-2">
                    {rows.map((endpoint) => {
                      const checked = selectedIds.includes(endpoint.id);
                      const name = endpoint.summary || endpoint.path;

                      return (
                        <div
                          className={cn(
                            "flex items-center gap-3 rounded-lg border border-transparent px-3 py-2.5 transition-colors",
                            checked
                              ? "border-sky-200 bg-background shadow-xs"
                              : "hover:border-border/70 hover:bg-background/80",
                          )}
                          key={endpoint.id}
                        >
                          <Checkbox
                            aria-label={`选择接口 ${name}`}
                            checked={checked}
                            onCheckedChange={(value) => toggleEndpoint(endpoint.id, value === true)}
                          />
                          <button
                            className="flex min-w-0 flex-1 items-center gap-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                            onClick={() => toggleEndpoint(endpoint.id, !checked)}
                            title={`${name} ${endpoint.path}`}
                            type="button"
                          >
                            <Badge
                              className={cn(
                                "h-6 w-14 shrink-0 justify-center font-mono text-[10px]",
                                methodTone[endpoint.method],
                              )}
                              variant="outline"
                            >
                              {endpoint.method}
                            </Badge>
                            <span className="min-w-0 flex-1">
                              <span className="block truncate font-medium text-foreground text-sm">{name}</span>
                              <span className="mt-0.5 block truncate font-mono text-[11px] text-muted-foreground">
                                {endpoint.path}
                              </span>
                            </span>
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}

          {groupEntries.length === 0 ? (
            <div className="flex h-full min-h-64 flex-col items-center justify-center px-6 text-center">
              <div className="font-medium text-sm">
                {endpoints.length === 0 ? "暂无可选接口资产" : "未找到匹配接口"}
              </div>
              <div className="mt-1 text-muted-foreground text-xs">
                {endpoints.length === 0 ? "请先在接口资产中导入接口。" : "请尝试其他名称、路径或标签。"}
              </div>
            </div>
          ) : null}
        </div>

        <DialogFooter className="mx-0 mb-0 items-center justify-between rounded-none border-t bg-background px-5 py-3 sm:justify-between">
          <span className="text-muted-foreground text-sm">已选择 {selectedIds.length} 个接口</span>
          <div className="flex gap-2">
            <Button onClick={closePicker} variant="outline">
              取消
            </Button>
            <Button
              disabled={selectedIds.length === 0}
              onClick={() => {
                onConfirm(selectedIds);
                closePicker();
              }}
            >
              添加到链路
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
