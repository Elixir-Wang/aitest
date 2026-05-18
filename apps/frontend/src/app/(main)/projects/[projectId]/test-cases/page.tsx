import Link from "next/link";

import { ArrowRight, ClipboardCheck, Layers3, ShieldCheck } from "lucide-react";

import { MetricCard, PageShell, PageToolbar, ShellSection, StatusBadge } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const testCases = [
  { id: "tc-001", title: "登录流程", status: "待评审", coverage: "高", owner: "张敏", updated: "2 小时前" },
  { id: "tc-002", title: "项目创建", status: "已采纳", coverage: "中", owner: "李强", updated: "6 小时前" },
  { id: "tc-003", title: "报告查看", status: "待采纳", coverage: "低", owner: "王磊", updated: "1 天前" },
];

export default function Page() {
  return (
    <PageShell
      breadcrumbs={["项目", "知了平台", "测试用例"]}
      description="从知识库生成测试用例，支持人工评审、采纳和覆盖矩阵追踪。"
      primaryAction="生成用例"
      projectScope="project"
      tabs={["用例列表", "用例评审", "覆盖矩阵", "版本历史"]}
      title="测试用例"
      >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="采纳 351 条" icon={ClipboardCheck} label="用例总数" value="426" />
        <MetricCard helper="高优先级 6 条" icon={ClipboardCheck} label="待评审" value="28" />
        <MetricCard helper="较上次 +9%" icon={ClipboardCheck} label="覆盖率" value="76%" />
      </div>
      <PageToolbar placeholder="搜索用例名称、模块或优先级" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]">
        <ShellSection>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="font-medium text-sm">测试用例列表</h2>
              <p className="text-muted-foreground text-xs">生成、评审、采纳和覆盖矩阵统一从这里进入。</p>
            </div>
            <Button variant="outline" size="sm">
              覆盖矩阵
            </Button>
          </div>
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>用例编号</TableHead>
                  <TableHead>用例标题</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>覆盖等级</TableHead>
                  <TableHead>负责人</TableHead>
                  <TableHead>更新时间</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {testCases.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">{item.id}</TableCell>
                    <TableCell>{item.title}</TableCell>
                    <TableCell>
                      <Badge variant={item.status === "已采纳" ? "secondary" : "outline"}>{item.status}</Badge>
                    </TableCell>
                    <TableCell>{item.coverage}</TableCell>
                    <TableCell>{item.owner}</TableCell>
                    <TableCell>{item.updated}</TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="ghost">
                        <Link href="/projects/zhiliao/test-cases">
                          查看
                          <ArrowRight className="size-4" />
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </ShellSection>
        <div className="space-y-4">
          <ShellSection>
            <div className="flex items-center gap-2">
              <StatusBadge>待评审</StatusBadge>
              <span className="text-muted-foreground text-xs">覆盖等级：高</span>
            </div>
            <div className="mt-3 space-y-3 text-sm">
              <p className="font-medium">登录流程用例</p>
              <p className="text-muted-foreground">测试用例骨架将承接评审、采纳和版本历史。</p>
              <div className="grid gap-2 text-muted-foreground text-xs">
                <div className="flex items-center gap-2">
                  <Layers3 className="size-4" />
                  <span>覆盖矩阵保持 76%</span>
                </div>
                <div className="flex items-center gap-2">
                  <ShieldCheck className="size-4" />
                  <span>高优先级用例 6 条</span>
                </div>
              </div>
            </div>
          </ShellSection>
          <ShellSection>
            <h2 className="font-medium text-sm">可用操作</h2>
            <div className="mt-3 flex flex-col gap-2">
              <Button variant="outline">进入评审</Button>
              <Button variant="outline">查看覆盖矩阵</Button>
              <Button>生成用例</Button>
            </div>
          </ShellSection>
          <ShellSection>
            <h2 className="font-medium text-sm">覆盖来源</h2>
            <div className="mt-3 space-y-2 text-muted-foreground text-sm">
              <p>需求：登录与权限 req-001</p>
              <p>知识库：登录与权限知识块 kb-001</p>
              <p>版本：用例集 v4</p>
            </div>
          </ShellSection>
        </div>
      </div>
    </PageShell>
  );
}
