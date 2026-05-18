import { format } from "date-fns";
import { Download, RotateCw, Settings2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ShellSection, StatusBadge } from "@/components/ai-testing/page-shell";

import { BalanceDistributionCard } from "./_components/balance-distribution-card";
import { FinanceNotification } from "./_components/finance-notification";
import { IncomeBreakdown } from "./_components/income-breakdown";
import { OverviewKpis } from "./_components/overview-kpis";
import { QuickActions } from "./_components/quick-actions";
import { TransactionsOverviewCard } from "./_components/transactions-overview-card";
import { UpcomingTransactions } from "./_components/upcoming-transactions";
import { Wallet } from "./_components/wallet";

export default function Page() {
  const formattedDate = format(new Date(), "EEEE, do MMMM yyyy");

  return (
    <div className="flex flex-col gap-4">
      <div className="space-y-1">
        <h1 className="text-3xl tracking-tight">Personal Finances</h1>
        <p className="text-muted-foreground text-sm">{formattedDate}</p>
      </div>

      <Tabs defaultValue="30-days" className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <TabsList variant="line">
            <TabsTrigger value="30-days">Dashboard</TabsTrigger>
            <TabsTrigger value="12-months">Accounts</TabsTrigger>
            <TabsTrigger value="custom">Transactions</TabsTrigger>
          </TabsList>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5 text-muted-foreground text-xs">
              <RotateCw className="size-4" />
              <span>Updated 5 min ago</span>
            </div>
            <Button size="sm" variant="outline">
              <Settings2 />
              Settings
            </Button>
            <Button size="sm" variant="outline">
              <Download data-icon="inline-start" />
              Export
            </Button>
          </div>
        </div>

        <TabsContent value="30-days" className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
            <div className="xl:col-span-6">
              <OverviewKpis />
            </div>

            <div className="flex flex-col gap-4 xl:col-span-6">
              <IncomeBreakdown />
              <FinanceNotification />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
            <div className="xl:col-span-7">
              <TransactionsOverviewCard />
            </div>
            <div className="xl:col-span-5">
              <BalanceDistributionCard />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
            <div className="xl:col-span-4">
              <Wallet />
            </div>
            <div className="xl:col-span-4">
              <UpcomingTransactions />
            </div>
            <div className="xl:col-span-4">
              <QuickActions />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="12-months" className="grid gap-4 lg:grid-cols-3">
          <ShellSection>
            <p className="text-muted-foreground text-xs">Main account</p>
            <p className="mt-2 font-semibold text-2xl">$42,800</p>
            <p className="mt-2 text-muted-foreground text-sm">Primary operating account balance.</p>
          </ShellSection>
          <ShellSection>
            <p className="text-muted-foreground text-xs">Reserve account</p>
            <p className="mt-2 font-semibold text-2xl">$18,420</p>
            <p className="mt-2 text-muted-foreground text-sm">Emergency and planned reserve.</p>
          </ShellSection>
          <ShellSection>
            <p className="text-muted-foreground text-xs">Account status</p>
            <div className="mt-2 flex items-center gap-2">
              <StatusBadge>Healthy</StatusBadge>
              <span className="text-muted-foreground text-sm">No overdraft risk</span>
            </div>
          </ShellSection>
        </TabsContent>

        <TabsContent value="custom" className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
          <ShellSection>
            <h2 className="font-medium text-sm">Recent transactions</h2>
            <div className="mt-4 space-y-3 text-sm">
              {["Stripe payout / +$2,840", "Cloud hosting / -$420", "Team subscription / -$188", "Client transfer / +$6,200"].map((item) => (
                <div key={item} className="flex items-center justify-between rounded-lg border p-3">
                  <span>{item.split(" / ")[0]}</span>
                  <StatusBadge>{item.split(" / ")[1]}</StatusBadge>
                </div>
              ))}
            </div>
          </ShellSection>
          <ShellSection>
            <h2 className="font-medium text-sm">Filters</h2>
            <p className="mt-3 text-muted-foreground text-sm">Transaction filters will keep date range, account, and category together.</p>
          </ShellSection>
        </TabsContent>
      </Tabs>
    </div>
  );
}
