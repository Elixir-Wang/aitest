"use client";

import { useMemo, useState } from "react";

import { Check, ChevronDown, FolderKanban } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export function ProjectSwitcher({ scope }: { scope: "all" | "project" }) {
  const options = useMemo(
    () => [
      { key: "all", text: "全部项目", helper: "跨项目查看与汇总" },
      { key: "zhiliao", text: "知了平台", helper: "当前项目" },
      { key: "hawk", text: "鹰眼平台", helper: "示例项目" },
    ],
    [],
  );
  const [selected, setSelected] = useState(scope === "all" ? "all" : "zhiliao");
  const label = options.find((item) => item.key === selected)?.text ?? "全部项目";

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" className="gap-2">
          <FolderKanban className="size-4" />
          <span className="text-muted-foreground">项目:</span>
          <span>{label}</span>
          <ChevronDown className="size-4 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-64">
        <div className="space-y-1">
          <div className="font-medium text-sm">项目切换</div>
          <div className="text-muted-foreground text-xs">当前分区用于浏览或操作项目数据。</div>
        </div>
        <div className="mt-2 space-y-1">
          {options.map((item) => (
            <button
              key={item.key}
              className={cn(
                "flex w-full items-start gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-accent",
                item.key === selected && "bg-accent",
              )}
              onClick={() => setSelected(item.key)}
              type="button"
            >
              <span className="mt-0.5 flex size-4 items-center justify-center rounded-full border border-border">
                {item.key === selected ? <Check className="size-3" /> : null}
              </span>
              <span className="flex flex-col">
                <span>{item.text}</span>
                <span className="text-muted-foreground text-xs">{item.helper}</span>
              </span>
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
