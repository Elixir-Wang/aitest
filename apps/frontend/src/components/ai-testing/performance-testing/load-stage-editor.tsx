"use client";

import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { PerformanceLoadConfig, PerformanceLoadStage } from "@/lib/api-client";

export function LoadStageEditor({
  mode,
  stages,
  onChange,
}: {
  mode: PerformanceLoadConfig["mode"];
  stages: PerformanceLoadStage[];
  onChange: (stages: PerformanceLoadStage[]) => void;
}) {
  if (mode === "fixed") {
    return <p className="border-y py-4 text-muted-foreground text-sm">固定负载参数将在 Locust UI 中配置。</p>;
  }

  function update(index: number, patch: Partial<PerformanceLoadStage>) {
    onChange(stages.map((stage, stageIndex) => (stageIndex === index ? { ...stage, ...patch } : stage)));
  }

  function move(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= stages.length) return;
    const next = [...stages];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next.map((stage, order) => ({ ...stage, order })));
  }

  function remove(index: number) {
    onChange(stages.filter((_, stageIndex) => stageIndex !== index).map((stage, order) => ({ ...stage, order })));
  }

  function add() {
    const previous = stages.at(-1);
    onChange([
      ...stages,
      {
        name: `阶段 ${stages.length + 1}`,
        target_users: previous?.target_users ?? 10,
        spawn_rate: previous?.spawn_rate ?? 1,
        hold_seconds: previous?.hold_seconds ?? 60,
        order: stages.length,
      },
    ]);
  }

  return (
    <div className="space-y-3">
      {stages.map((stage, index) => (
        <div className="grid gap-3 border-y py-4 md:grid-cols-[1.3fr_1fr_1fr_1fr_auto]" key={stage.name}>
          <Field label="阶段名称">
            <Input onChange={(event) => update(index, { name: event.target.value })} value={stage.name} />
          </Field>
          <Field label="目标用户数">
            <Input
              min={1}
              onChange={(event) => update(index, { target_users: Number(event.target.value) })}
              type="number"
              value={stage.target_users}
            />
          </Field>
          <Field label="启动速率/秒">
            <Input
              min={0.1}
              onChange={(event) => update(index, { spawn_rate: Number(event.target.value) })}
              step={0.1}
              type="number"
              value={stage.spawn_rate}
            />
          </Field>
          <Field label="保持时长（秒）">
            <Input
              min={1}
              onChange={(event) => update(index, { hold_seconds: Number(event.target.value) })}
              type="number"
              value={stage.hold_seconds}
            />
          </Field>
          <div className="flex items-end gap-1">
            <Button disabled={index === 0} onClick={() => move(index, -1)} size="icon" type="button" variant="ghost">
              <ArrowUp />
            </Button>
            <Button
              disabled={index === stages.length - 1}
              onClick={() => move(index, 1)}
              size="icon"
              type="button"
              variant="ghost"
            >
              <ArrowDown />
            </Button>
            <Button onClick={() => remove(index)} size="icon" type="button" variant="ghost">
              <Trash2 />
            </Button>
          </div>
        </div>
      ))}
      <Button onClick={add} type="button" variant="outline">
        <Plus />
        添加阶段
      </Button>
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
