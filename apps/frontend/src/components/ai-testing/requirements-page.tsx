"use client";

import { useEffect, useMemo, useState } from "react";

import { useRouter } from "next/navigation";

import { Eye, FileText } from "lucide-react";
import { toast } from "sonner";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { ProcessingState, TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiRequest, formatDateTime } from "@/lib/api-client";

type RequirementRow = {
  id: string;
  name: string;
  document_type: string;
  status: string;
  created_at: string;
  updated_at: string;
  current_version: {
    version_no: number;
    file_path: string;
    change_summary: string;
    created_at: string;
  } | null;
  available_actions: string[];
};

type RequirementPageProps = {
  title: string;
  breadcrumbs: string[];
  projectScope: "all" | "project";
  description: string;
  projectId: string;
  uploadHref: string;
};

const statusLabels: Record<string, string> = {
  parsing: "解析中",
  pending_review: "待评审",
};

export function RequirementsPage({ title, breadcrumbs, projectScope, description, projectId, uploadHref }: RequirementPageProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchText, setSearchText] = useState("");
  const { allSelected, partiallySelected, rows, selectedCount, selectedIds, setRows, toggleAll, toggleOne } =
    useLocalTableSelection<RequirementRow>([]);

  useEffect(() => {
    let ignore = false;

    async function loadDocuments() {
      setLoading(true);
      setError("");
      try {
        const data = await apiRequest<RequirementRow[]>(`/projects/${projectId}/documents`);
        if (!ignore) {
          setRows(data);
        }
      } catch (requestError) {
        if (!ignore) {
          setError(requestError instanceof Error ? requestError.message : "需求文档加载失败");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    void loadDocuments();

    return () => {
      ignore = true;
    };
  }, [projectId, setRows]);

  const filteredRows = useMemo(
    () =>
      rows.filter((item) =>
        [item.name, item.document_type, item.status, item.current_version?.change_summary ?? "", item.updated_at].some((value) =>
          value.toLowerCase().includes(searchText.trim().toLowerCase()),
        ),
      ),
    [rows, searchText],
  );

  async function deleteDocuments(ids: string[]) {
    if (ids.length === 0) {
      return;
    }
    setRows((current) => current.filter((row) => !ids.includes(row.id)));
    toast.success("已从列表移除本地显示项");
  }

  return (
    <PageShell
      breadcrumbs={breadcrumbs}
      description={description}
      projectScope={projectScope}
      tabs={["文档管理", "需求评审", "分析结果", "澄清问题", "版本记录"]}
      title={title}
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="当前文档数" icon={FileText} label="需求文档" value={String(rows.length)} />
        <MetricCard helper="已上传即进入待评审" icon={FileText} label="模块覆盖" value="-" />
        <MetricCard helper="最新版本信息" icon={FileText} label="版本记录" value={String(rows.reduce((count, item) => count + (item.current_version ? 1 : 0), 0))} />
      </div>
      <ShellSection>
        {error ? <div className="mb-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">{error}</div> : null}
        <ListToolbar
          createLabel="上传需求"
          onBatchDelete={() => deleteDocuments(selectedIds)}
          onCreate={() => router.push(uploadHref)}
          onSearch={setSearchText}
          placeholder="搜索需求名称、类型、状态或更新时间"
          selectedCount={selectedCount}
          title="需求文档列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部需求"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    disabled={loading}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>需求名称</TableHead>
                <TableHead>文档类型</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>当前版本</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRows.map((item) => (
                <TableRow data-state={selectedIds.includes(item.id) ? "selected" : undefined} key={item.id}>
                  <TableCell>
                    <Checkbox
                      aria-label={`选择 ${item.name}`}
                      checked={selectedIds.includes(item.id)}
                      onCheckedChange={(checked) => toggleOne(item.id, Boolean(checked))}
                    />
                  </TableCell>
                  <TableCell className="font-medium">{item.name}</TableCell>
                  <TableCell>{item.document_type}</TableCell>
                  <TableCell>
                    <Badge variant={item.status === "parsing" ? "outline" : "secondary"}>
                      {item.status === "parsing" ? <ProcessingState label={statusLabels[item.status]} /> : (statusLabels[item.status] ?? item.status)}
                    </Badge>
                  </TableCell>
                  <TableCell>{item.current_version ? `v${item.current_version.version_no}` : "-"}</TableCell>
                  <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                  <TableCell>
                    <RowActions actions={[{ label: "查看", href: "#", icon: Eye }]} label={`打开 ${item.name} 操作菜单`} />
                  </TableCell>
                </TableRow>
              ))}
              {loading && filteredRows.length === 0 ? <TableLoadingRow colSpan={7} label="需求文档加载中" /> : null}
            </TableBody>
          </Table>
        </div>
      </ShellSection>
    </PageShell>
  );
}
