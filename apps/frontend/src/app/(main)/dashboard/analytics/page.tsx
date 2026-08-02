import { ShellSection, StatusBadge } from "@/components/ai-testing/page-shell";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { AnalyticsKpiStrip } from "./_components/analytics-kpi-strip";
import { AnalyticsToolbar } from "./_components/analytics-toolbar";
import { RealtimeVisitors } from "./_components/realtime-visitors";
import { TopPages } from "./_components/top-pages";
import { TopTrafficSources } from "./_components/top-traffic-sources";
import { TrafficQuality } from "./_components/traffic-quality";

// Import this stylesheet in any page or component that renders country flag classes.
import "@/styles/flag-icons/flags.css";

export default function Page() {
  return (
    <div className="flex flex-col gap-4">
      <div className="space-y-1">
        <h1 className="text-3xl tracking-tight">Hello, Aiy</h1>
        <p className="text-muted-foreground text-sm">
          Monitor traffic, engagement, and conversion performance in one view.
        </p>
      </div>

      <Tabs defaultValue="overview" className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <TabsList className="gap-1">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="audience">Audience</TabsTrigger>
            <TabsTrigger value="acquisition">Acquisition</TabsTrigger>
            <TabsTrigger value="engagement">Engagement</TabsTrigger>
            <TabsTrigger value="conversions">Conversions</TabsTrigger>
          </TabsList>

          <AnalyticsToolbar />
        </div>

        <TabsContent value="overview" className="flex flex-col gap-4">
          <AnalyticsKpiStrip />

          <div className="grid grid-cols-1 items-stretch gap-4 xl:grid-cols-12">
            <div className="xl:col-span-7">
              <TrafficQuality />
            </div>
            <div className="xl:col-span-5">
              <RealtimeVisitors />
            </div>
          </div>

          <div className="grid grid-cols-1 items-stretch gap-4 xl:grid-cols-12">
            <div className="xl:col-span-7">
              <TopPages />
            </div>
            <div className="xl:col-span-5 xl:col-start-8">
              <TopTrafficSources />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="audience" className="grid gap-4 lg:grid-cols-3">
          <ShellSection>
            <p className="text-muted-foreground text-xs">Active audience</p>
            <p className="mt-2 font-semibold text-2xl">18.4k</p>
            <p className="mt-2 text-muted-foreground text-sm">Returning visitors account for 42% of sessions.</p>
          </ShellSection>
          <ShellSection>
            <p className="text-muted-foreground text-xs">Primary segment</p>
            <p className="mt-2 font-semibold text-2xl">QA Engineers</p>
            <p className="mt-2 text-muted-foreground text-sm">Most activity comes from workspace and report pages.</p>
          </ShellSection>
          <ShellSection>
            <p className="text-muted-foreground text-xs">Audience health</p>
            <div className="mt-2 flex items-center gap-2">
              <StatusBadge>Stable</StatusBadge>
              <span className="text-muted-foreground text-sm">No abnormal spike</span>
            </div>
          </ShellSection>
        </TabsContent>

        <TabsContent value="acquisition" className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
          <ShellSection>
            <h2 className="font-medium text-sm">Channel quality</h2>
            <div className="mt-4 space-y-3 text-sm">
              {["Direct / 46%", "Search / 31%", "Referral / 14%", "Campaign / 9%"].map((item) => (
                <div key={item} className="flex items-center justify-between rounded-lg border p-3">
                  <span>{item.split(" / ")[0]}</span>
                  <StatusBadge>{item.split(" / ")[1]}</StatusBadge>
                </div>
              ))}
            </div>
          </ShellSection>
          <ShellSection>
            <h2 className="font-medium text-sm">Source note</h2>
            <p className="mt-3 text-muted-foreground text-sm">
              Acquisition view keeps source quality and conversion handoff in one place.
            </p>
          </ShellSection>
        </TabsContent>

        <TabsContent value="engagement" className="grid gap-4 lg:grid-cols-3">
          <ShellSection>
            <p className="text-muted-foreground text-xs">Avg. session</p>
            <p className="mt-2 font-semibold text-2xl">6m 24s</p>
          </ShellSection>
          <ShellSection>
            <p className="text-muted-foreground text-xs">Interaction rate</p>
            <p className="mt-2 font-semibold text-2xl">63%</p>
          </ShellSection>
          <ShellSection>
            <p className="text-muted-foreground text-xs">Top path</p>
            <p className="mt-2 font-medium text-sm">Dashboard / Projects / Reports</p>
          </ShellSection>
        </TabsContent>

        <TabsContent value="conversions" className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
          <ShellSection>
            <h2 className="font-medium text-sm">Conversion funnel</h2>
            <div className="mt-4 space-y-3 text-sm">
              {["Visit workspace / 100%", "Open project / 72%", "Run task / 38%", "View report / 27%"].map((item) => (
                <div key={item} className="flex items-center justify-between rounded-lg border p-3">
                  <span>{item.split(" / ")[0]}</span>
                  <StatusBadge>{item.split(" / ")[1]}</StatusBadge>
                </div>
              ))}
            </div>
          </ShellSection>
          <ShellSection>
            <h2 className="font-medium text-sm">Goal summary</h2>
            <p className="mt-3 text-muted-foreground text-sm">Primary conversion is successful report inspection.</p>
          </ShellSection>
        </TabsContent>
      </Tabs>
    </div>
  );
}
