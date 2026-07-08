import { Eye, Pencil, Play, Square, Trash2 } from "lucide-react";

import { ExplorationStatusBadge, loginStrategyLabels } from "@/components/ai-testing/exploration-environment-utils";
import { RowActions } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDateTime } from "@/lib/api-client";
import type { ExplorationRunSummary as ExplorationRun } from "@/lib/exploration-types";

const STOPPABLE_EXPLORATION_STATUSES = new Set(["queued", "running"]);

export function ExplorationRunsTable({
  allSelected,
  loading,
  onDelete,
  onEdit,
  onOpen,
  onStart,
  onStop,
  onToggleAll,
  onToggleOne,
  partiallySelected,
  rows,
  selectedIds,
  startingExplorationId,
}: {
  allSelected: boolean;
  loading: boolean;
  onDelete: (ids: string[]) => void;
  onEdit: (run: ExplorationRun) => void;
  onOpen: (run: ExplorationRun) => void;
  onStart: (run: ExplorationRun) => void;
  onStop: (run: ExplorationRun) => void;
  onToggleAll: (checked: boolean) => void;
  onToggleOne: (id: string, checked: boolean) => void;
  partiallySelected: boolean;
  rows: ExplorationRun[];
  selectedIds: string[];
  startingExplorationId: string;
}) {
  return (
    <div className="overflow-hidden rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">
              <Checkbox
                aria-label="选择全部探索任务"
                checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                disabled={loading}
                onCheckedChange={(checked) => onToggleAll(Boolean(checked))}
              />
            </TableHead>
            <TableHead>任务名称</TableHead>
            <TableHead>项目</TableHead>
            <TableHead>关联环境</TableHead>
            <TableHead>关联需求</TableHead>
            <TableHead>任务状态</TableHead>
            <TableHead>登录策略</TableHead>
            <TableHead>更新时间</TableHead>
            <TableHead className="w-16">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((item) => (
            <TableRow data-state={selectedIds.includes(item.id) ? "selected" : undefined} key={item.id}>
              <TableCell>
                <Checkbox
                  aria-label={`选择 ${item.title}`}
                  checked={selectedIds.includes(item.id)}
                  onCheckedChange={(checked) => onToggleOne(item.id, Boolean(checked))}
                />
              </TableCell>
              <TableCell className="font-medium">
                <button className="hover:underline" onClick={() => onOpen(item)} type="button">
                  {item.title}
                </button>
              </TableCell>
              <TableCell>{item.project_name}</TableCell>
              <TableCell>{item.environment_name}</TableCell>
              <TableCell>{item.requirement_doc_title || "-"}</TableCell>
              <TableCell>
                <ExplorationStatusBadge status={item.status} />
              </TableCell>
              <TableCell>{loginStrategyLabels[item.login_strategy] ?? item.login_strategy}</TableCell>
              <TableCell>{formatDateTime(item.updated_at)}</TableCell>
              <TableCell>
                <RowActions
                  actions={[
                    {
                      label: "概览",
                      icon: Eye,
                      onSelect: () => onOpen(item),
                    },
                    {
                      label: "编辑",
                      icon: Pencil,
                      onSelect: () => onEdit(item),
                    },
                    ...((item.available_actions ?? []).includes("start")
                      ? [
                          {
                            label: item.status === "pending" ? "开始探索" : "重新探索",
                            icon: Play,
                            disabled: startingExplorationId === item.id,
                            onSelect: () => onStart(item),
                          },
                        ]
                      : []),
                    ...(STOPPABLE_EXPLORATION_STATUSES.has(item.status)
                      ? [
                          {
                            label: "停止探索",
                            icon: Square,
                            destructive: true,
                            onSelect: () => onStop(item),
                          },
                        ]
                      : []),
                    {
                      label: "删除",
                      icon: Trash2,
                      destructive: true,
                      onSelect: () => onDelete([item.id]),
                    },
                  ]}
                  label={`打开 ${item.title} 操作菜单`}
                />
              </TableCell>
            </TableRow>
          ))}
          {loading && rows.length === 0 ? <TableLoadingRow colSpan={9} label="探索任务加载中" /> : null}
          {!loading && rows.length === 0 ? (
            <TableRow>
              <TableCell className="h-24 text-center text-muted-foreground" colSpan={9}>
                暂无探索任务。选择环境并创建探索任务后，系统会生成页面结构与探索报告。
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
    </div>
  );
}
