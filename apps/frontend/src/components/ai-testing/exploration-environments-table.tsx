import { LogIn, Trash2 } from "lucide-react";

import {
  canStartAiLetterAutoAuth,
  EnvironmentAuthStateBadge,
} from "@/components/ai-testing/exploration-environment-utils";
import { RowActions } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDateTime } from "@/lib/api-client";
import type { ExplorationEnvironment } from "@/lib/exploration-types";

export function ExplorationEnvironmentsTable({
  allSelected,
  loading,
  onDelete,
  onEdit,
  onStartAiLetterAutoAuth,
  onToggleAll,
  onToggleOne,
  partiallySelected,
  rows,
  selectedIds,
}: {
  allSelected: boolean;
  loading: boolean;
  onDelete: (ids: string[]) => void;
  onEdit: (environment: ExplorationEnvironment) => void;
  onStartAiLetterAutoAuth: (environment: ExplorationEnvironment) => void;
  onToggleAll: (checked: boolean) => void;
  onToggleOne: (id: string, checked: boolean) => void;
  partiallySelected: boolean;
  rows: ExplorationEnvironment[];
  selectedIds: string[];
}) {
  return (
    <div className="overflow-hidden rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">
              <Checkbox
                aria-label="选择全部环境"
                checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                disabled={loading}
                onCheckedChange={(checked) => onToggleAll(Boolean(checked))}
              />
            </TableHead>
            <TableHead>环境名称</TableHead>
            <TableHead>站点地址</TableHead>
            <TableHead>登录态</TableHead>
            <TableHead>更新时间</TableHead>
            <TableHead className="w-16">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((item) => (
            <TableRow data-state={selectedIds.includes(item.id) ? "selected" : undefined} key={item.id}>
              <TableCell>
                <Checkbox
                  aria-label={`选择 ${item.name}`}
                  checked={selectedIds.includes(item.id)}
                  onCheckedChange={(checked) => onToggleOne(item.id, Boolean(checked))}
                />
              </TableCell>
              <TableCell className="font-medium">
                <button className="hover:underline" onClick={() => onEdit(item)} type="button">
                  {item.name}
                </button>
              </TableCell>
              <TableCell>
                <span className="block max-w-72 truncate" title={item.site_url}>
                  {item.site_url}
                </span>
              </TableCell>
              <TableCell>
                <div className="flex min-w-28">
                  <EnvironmentAuthStateBadge message={item.auth_state_message} status={item.auth_state_status} />
                </div>
              </TableCell>
              <TableCell>{formatDateTime(item.updated_at)}</TableCell>
              <TableCell>
                <RowActions
                  actions={[
                    ...(canStartAiLetterAutoAuth(item)
                      ? [
                          {
                            label: item.auth_state_status === "logging_in" ? "登录中" : "登录",
                            icon: LogIn,
                            disabled: item.auth_state_status === "logging_in",
                            onSelect: () => onStartAiLetterAutoAuth(item),
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
                  label={`打开 ${item.name} 操作菜单`}
                />
              </TableCell>
            </TableRow>
          ))}
          {loading && rows.length === 0 ? <TableLoadingRow colSpan={5} label="环境列表加载中" /> : null}
          {!loading && rows.length === 0 ? (
            <TableRow>
              <TableCell className="h-24 text-center text-muted-foreground" colSpan={5}>
                暂无环境。新增站点环境后，可用于后续页面探索任务。
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
    </div>
  );
}
