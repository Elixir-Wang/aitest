"use client";

import { useEffect, useMemo, useState } from "react";

import Link from "next/link";

import { Gauge } from "lucide-react";
import { toast } from "sonner";

import { ListToolbar } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type ApiProject,
  ApiRequestError,
  apiRequest,
  formatDateTime,
  listPerformanceTests,
  type PerformanceTest,
} from "@/lib/api-client";

type ProjectPerformanceTest = PerformanceTest & { projectName: string };

export function AllPerformanceTestList() {
  const [items, setItems] = useState<ProjectPerformanceTest[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    let ignore = false;
    apiRequest<ApiProject[]>("/projects")
      .then(async (projects) => {
        const rows = await Promise.all(
          projects.map(async (project) =>
            (await listPerformanceTests(project.id)).map((item) => ({ ...item, projectName: project.name })),
          ),
        );
        if (!ignore) setItems(rows.flat());
      })
      .catch((error) => toast.error(apiErrorMessage(error)))
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, []);

  const visibleItems = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return keyword
      ? items.filter((item) =>
          [item.name, item.projectName, item.endpoint_path, item.environment_name]
            .join(" ")
            .toLowerCase()
            .includes(keyword),
        )
      : items;
  }, [items, search]);

  return (
    <section className="border-y py-4">
      <ListToolbar
        description="跨项目查看任务定义；新建任务需要先进入具体项目。"
        onSearch={setSearch}
        placeholder="搜索项目、名称、接口或环境"
        title="全部项目"
      />
      <div className="overflow-hidden rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>名称</TableHead>
              <TableHead>项目</TableHead>
              <TableHead>接口</TableHead>
              <TableHead>环境</TableHead>
              <TableHead>最近运行</TableHead>
              <TableHead>更新时间</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading || visibleItems.length === 0 ? (
              <TableRow>
                <TableCell className="h-40 text-center text-muted-foreground" colSpan={6}>
                  <div className="flex flex-col items-center gap-2">
                    <Gauge className="size-5" />
                    {loading ? "正在加载" : "暂无性能测试"}
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              visibleItems.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <Link
                      className="font-medium hover:underline"
                      href={`/projects/${item.project_id}/performance-tests/${item.id}`}
                    >
                      {item.name}
                    </Link>
                  </TableCell>
                  <TableCell>{item.projectName}</TableCell>
                  <TableCell className="max-w-80 truncate font-mono text-xs">
                    {item.endpoint_id ? `${item.endpoint_method} ${item.endpoint_path}` : "引用已失效"}
                  </TableCell>
                  <TableCell>{item.api_environment_id ? item.environment_name : "引用已失效"}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{item.latest_run_status || "未运行"}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-xs">{formatDateTime(item.updated_at)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiRequestError) return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  return "性能测试加载失败";
}
