"use client";

import { format, parseISO } from "date-fns";
import { Area, CartesianGrid, ComposedChart, Line, XAxis } from "recharts";

import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type ChartConfig,
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ApiDashboardTrendPoint } from "@/lib/api-client";

const chartConfig = {
  caseAssets: {
    label: "用例资产数",
    color: "var(--chart-1)",
  },
  adoptedCases: {
    label: "已采纳用例",
    color: "var(--chart-2)",
  },
  automationCases: {
    label: "自动化用例",
    color: "var(--chart-3)",
  },
} satisfies ChartConfig;

export function AssetTrendChart({
  data,
  days,
  onDaysChange,
  projectLabel,
}: {
  data: ApiDashboardTrendPoint[];
  days: number;
  onDaysChange: (days: number) => void;
  projectLabel: string;
}) {
  return (
    <Card className="@container/card">
      <CardHeader>
        <CardTitle className="leading-none">测试资产趋势</CardTitle>
        <CardDescription>
          <span className="@[540px]/card:block hidden">
            按{projectLabel}统计近 {days} 天资产沉淀趋势
          </span>
          <span className="@[540px]/card:hidden">近 {days} 天资产趋势</span>
        </CardDescription>
        <CardAction>
          <Select value={`${days}d`} onValueChange={(value) => onDaysChange(Number.parseInt(value, 10))}>
            <SelectTrigger className="w-24" size="sm">
              <SelectValue placeholder="周期" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectLabel>统计周期</SelectLabel>
                <SelectItem value="7d">近 7 天</SelectItem>
                <SelectItem value="15d">近 15 天</SelectItem>
                <SelectItem value="30d">近 30 天</SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
        </CardAction>
      </CardHeader>

      <CardContent>
        <ChartContainer config={chartConfig} className="aspect-auto h-80 w-full">
          <ComposedChart data={data} margin={{ top: 0 }}>
            <defs>
              <linearGradient id="fillCaseAssets" x1="0" x2="0" y1="0" y2="1">
                <stop offset="5%" stopColor="var(--color-caseAssets)" stopOpacity={0.32} />
                <stop offset="95%" stopColor="var(--color-caseAssets)" stopOpacity={0.04} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeOpacity={0.5} vertical={false} />

            <XAxis
              axisLine={false}
              dataKey="date"
              minTickGap={48}
              tickFormatter={(value) =>
                parseISO(value).toLocaleDateString("zh-CN", {
                  day: "numeric",
                  month: "short",
                })
              }
              tickLine={false}
              tickMargin={8}
            />

            <ChartTooltip
              content={
                <ChartTooltipContent
                  className="w-48"
                  indicator="line"
                  labelFormatter={(value) => format(parseISO(value), "yyyy-MM-dd")}
                />
              }
              cursor={false}
            />
            <ChartLegend content={<ChartLegendContent className="mb-5 justify-end" />} verticalAlign="top" />

            <Area
              dataKey="caseAssets"
              dot={false}
              fill="url(#fillCaseAssets)"
              fillOpacity={1}
              stroke="var(--color-caseAssets)"
              strokeWidth={1.25}
              type="monotone"
            />
            <Line
              dataKey="adoptedCases"
              dot={false}
              stroke="var(--color-adoptedCases)"
              strokeWidth={1.4}
              type="monotone"
            />
            <Line
              dataKey="automationCases"
              dot={false}
              stroke="var(--color-automationCases)"
              strokeWidth={1.2}
              type="monotone"
            />
          </ComposedChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
