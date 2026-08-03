"use client";

import { useMemo } from "react";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { OneClipboard } from "@/components/ui/one-clipboard";
import type { PerformanceTest } from "@/lib/api-client";

type PerformanceTestParamsDialogProps = {
  item: PerformanceTest | null;
  onOpenChange: (open: boolean) => void;
};

export function PerformanceTestParamsDialog({ item, onOpenChange }: PerformanceTestParamsDialogProps) {
  const payload = useMemo(() => {
    if (!item) return "";
    return JSON.stringify(
      {
        target_type: item.target_type,
        endpoint_id: item.endpoint_id,
        scenario_id: item.scenario_id,
        request_config: item.request_config,
        load_config: item.load_config,
        data_config: item.data_config,
        circuit_breaker: item.circuit_breaker,
        performance_goal: item.performance_goal,
        success_rules: item.success_rules,
      },
      null,
      2,
    );
  }, [item]);

  return (
    <Dialog onOpenChange={onOpenChange} open={Boolean(item)}>
      <DialogContent className="grid max-h-[min(760px,calc(100vh-2rem))] w-[calc(100vw-2rem)] max-w-3xl grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden p-0">
        <DialogHeader className="border-b px-5 py-4 pr-14">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <DialogTitle className="truncate">创建参数</DialogTitle>
              <DialogDescription className="mt-1 truncate">
                {item?.name} · {item?.target_type === "scenario" ? item.scenario_name : `${item?.endpoint_method} ${item?.endpoint_path}`}
              </DialogDescription>
            </div>
            <OneClipboard copiedLabel="已复制" label="复制 JSON" text={payload} />
          </div>
        </DialogHeader>
        <div className="min-h-0 overflow-y-auto bg-muted/20 p-5">
          <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border bg-background p-4 font-mono text-xs leading-5">
            {payload}
          </pre>
        </div>
      </DialogContent>
    </Dialog>
  );
}
