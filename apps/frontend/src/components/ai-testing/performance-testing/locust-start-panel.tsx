"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { PerformanceRunStartPayload } from "@/lib/api-client";

export function LocustStartPanel({
  defaults,
  disabled,
  onStart,
}: {
  defaults: PerformanceRunStartPayload;
  disabled: boolean;
  onStart: (payload: PerformanceRunStartPayload) => Promise<void>;
}) {
  const [users, setUsers] = useState(defaults.users);
  const [spawnRate, setSpawnRate] = useState(defaults.spawn_rate);
  const [runTime, setRunTime] = useState(defaults.run_time);

  useEffect(() => {
    setUsers(defaults.users);
    setSpawnRate(defaults.spawn_rate);
    setRunTime(defaults.run_time);
  }, [defaults]);

  const valid = users > 0 && spawnRate > 0 && runTime > 0;

  return (
    <section className="overflow-hidden rounded-lg border bg-background">
      <div className="border-b bg-muted/30 px-5 py-4">
        <p className="font-semibold text-base">Start new load test</p>
        <p className="mt-1 text-muted-foreground text-xs">Configure the load shape and let Locust start the users.</p>
      </div>
      <div className="grid gap-4 p-5 md:grid-cols-3">
        <Field label="Number of users">
          <Input min={1} onChange={(event) => setUsers(Number(event.target.value))} type="number" value={users} />
        </Field>
        <Field label="Spawn rate">
          <Input
            min={0.1}
            onChange={(event) => setSpawnRate(Number(event.target.value))}
            step={0.1}
            type="number"
            value={spawnRate}
          />
        </Field>
        <Field label="Run time (seconds)">
          <Input min={1} onChange={(event) => setRunTime(Number(event.target.value))} type="number" value={runTime} />
        </Field>
      </div>
      <div className="flex items-center justify-between border-t px-5 py-4">
        <p className="text-muted-foreground text-xs">Traffic starts only after this action.</p>
        <Button
          disabled={disabled || !valid}
          onClick={() => onStart({ users, spawn_rate: spawnRate, run_time: runTime })}
        >
          Start new load test
        </Button>
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="space-y-2 text-sm">
      <span className="font-medium text-xs">{label}</span>
      {children}
    </label>
  );
}
