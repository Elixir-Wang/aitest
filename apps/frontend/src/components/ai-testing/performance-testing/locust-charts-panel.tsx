"use client";

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export type LocustChartSample = {
  sampledAt: string;
  users: number;
  rps: number;
  failuresPerSecond: number;
  responseTime: number;
};

export function LocustChartsPanel({ samples }: { samples: LocustChartSample[] }) {
  if (samples.length < 2) {
    return (
      <div className="rounded-md border px-4 py-16 text-center text-muted-foreground text-sm">
        Charts appear after Locust has produced multiple samples.
      </div>
    );
  }
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <ChartCard title="Total requests per second">
        <LineChart data={samples}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="sampledAt" minTickGap={30} />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line dataKey="rps" dot={false} name="RPS" stroke="var(--chart-1)" strokeWidth={2} type="monotone" />
          <Line
            dataKey="failuresPerSecond"
            dot={false}
            name="Failures/s"
            stroke="var(--destructive)"
            strokeWidth={2}
            type="monotone"
          />
        </LineChart>
      </ChartCard>
      <ChartCard title="Response time and users">
        <LineChart data={samples}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="sampledAt" minTickGap={30} />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line
            dataKey="responseTime"
            dot={false}
            name="Average response time"
            stroke="var(--chart-2)"
            strokeWidth={2}
            type="monotone"
          />
          <Line dataKey="users" dot={false} name="Users" stroke="var(--chart-4)" strokeWidth={2} type="stepAfter" />
        </LineChart>
      </ChartCard>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactElement }) {
  return (
    <section className="rounded-md border p-4">
      <h3 className="mb-4 font-medium text-sm">{title}</h3>
      <div className="h-72 w-full">
        <ResponsiveContainer height="100%" width="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </section>
  );
}
