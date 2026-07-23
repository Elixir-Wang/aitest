"use client";

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export type LocustChartSample = {
  sampledAt: string;
  users: number;
  rps: number;
  failuresPerSecond: number;
  p50ResponseTime: number;
  p95ResponseTime: number;
};

export function LocustChartsPanel({ samples }: { samples: LocustChartSample[] }) {
  if (samples.length < 2) {
    return (
      <div className="rounded-md border px-4 py-16 text-center text-muted-foreground text-sm dark:border-slate-800">
        产生多条采样数据后将显示趋势图
      </div>
    );
  }
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <ChartCard title="每秒请求数">
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
            name="失败数/秒"
            stroke="var(--destructive)"
            strokeWidth={2}
            type="monotone"
          />
        </LineChart>
      </ChartCard>
      <ChartCard title="响应时间">
        <LineChart data={samples}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="sampledAt" minTickGap={30} />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line
            dataKey="p50ResponseTime"
            dot={false}
            name="中位数 (P50)"
            stroke="var(--chart-2)"
            strokeWidth={2}
            type="monotone"
          />
          <Line
            dataKey="p95ResponseTime"
            dot={false}
            name="95% 分位"
            stroke="var(--chart-3)"
            strokeWidth={2}
            type="monotone"
          />
        </LineChart>
      </ChartCard>
      <ChartCard className="xl:col-span-2" title="用户数">
        <LineChart data={samples}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="sampledAt" minTickGap={30} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Legend />
          <Line dataKey="users" dot={false} name="用户数" stroke="var(--chart-4)" strokeWidth={2} type="stepAfter" />
        </LineChart>
      </ChartCard>
    </div>
  );
}

function ChartCard({
  title,
  children,
  className = "",
}: {
  title: string;
  children: React.ReactElement;
  className?: string;
}) {
  return (
    <section className={`rounded-md border p-4 dark:border-slate-800 ${className}`}>
      <h3 className="mb-4 font-medium text-sm">{title}</h3>
      <div className="h-72 w-full">
        <ResponsiveContainer height="100%" width="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </section>
  );
}
