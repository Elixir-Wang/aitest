"use client";

import { useCallback, useEffect, useState } from "react";

import { Eye, EyeOff, Pencil, TestTube, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { ProcessingState, TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { healthStatusTone, StatusBadge } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { type ApiModelProvider, apiRequest, formatDateTime, healthStatusToLabel } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";
import { useAuthStore } from "@/stores/auth-store";

type ModelRow = ApiModelProvider;

const emptyForm = {
  apiKey: "",
  baseUrl: "",
  description: "",
  model: "",
  provider: "",
};

export default function Page() {
  const currentUser = useAuthStore((state) => state.user);
  const canWrite = currentUser?.role === "admin";
  const [rows, setRows] = useState<ModelRow[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelRow | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [apiKeyVisible, setApiKeyVisible] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(true);
  const [testingModelId, setTestingModelId] = useState<string | null>(null);
  const filteredRows = rows.filter((provider) =>
    [provider.provider, provider.model, provider.base_url, provider.description, provider.updated_at].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );
  const selectedCount = selectedIds.length;
  const allSelected = filteredRows.length > 0 && filteredRows.every((row) => selectedIds.includes(row.id));
  const partiallySelected = selectedCount > 0 && !allSelected;

  const loadProviders = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await apiRequest<ModelRow[]>("/models/providers"));
    } catch (error) {
      reportError(error, {
        fallbackMessage: "模型配置加载失败",
        actionLabel: "加载模型配置",
        method: "GET",
        path: "/models/providers",
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProviders();
  }, [loadProviders]);

  function toggleAll(checked: boolean) {
    setSelectedIds(checked ? filteredRows.map((row) => row.id) : []);
  }

  function toggleOne(id: string, checked: boolean) {
    setSelectedIds((current) => (checked ? [...current, id] : current.filter((item) => item !== id)));
  }

  function openCreateDialog() {
    setEditingModel(null);
    setForm(emptyForm);
    setApiKeyVisible(false);
    setDialogOpen(true);
  }

  function openEditDialog(model: ModelRow) {
    setEditingModel(model);
    setForm({
      apiKey: model.api_key,
      baseUrl: model.base_url,
      description: model.description,
      model: model.model,
      provider: model.provider,
    });
    setApiKeyVisible(false);
    setDialogOpen(true);
  }

  async function submitModel() {
    const payload = {
      api_key: form.apiKey.trim(),
      base_url: form.baseUrl.trim(),
      description: form.description.trim(),
      model: form.model.trim(),
      provider: form.provider.trim(),
      status: "enabled",
    };

    try {
      if (editingModel) {
        await apiRequest<ModelRow>(`/models/providers/${editingModel.id}`, {
          body: JSON.stringify(payload),
          method: "PATCH",
        });
      } else {
        await apiRequest<ModelRow>("/models/providers", {
          body: JSON.stringify(payload),
          method: "POST",
        });
      }
      toast.success(editingModel ? "模型配置已保存" : "模型配置已创建");
      setDialogOpen(false);
      await loadProviders();
    } catch (error) {
      reportError(error, {
        fallbackMessage: "模型配置保存失败",
        actionLabel: editingModel ? "编辑模型配置" : "新增模型配置",
        method: editingModel ? "PATCH" : "POST",
        path: editingModel ? `/models/providers/${editingModel.id}` : "/models/providers",
      });
    }
  }

  async function deleteProviders(ids: string[]) {
    try {
      await Promise.all(ids.map((id) => apiRequest(`/models/providers/${id}`, { method: "DELETE" })));
      setSelectedIds([]);
      toast.success("模型配置已删除");
      await loadProviders();
    } catch (error) {
      reportError(error, {
        fallbackMessage: "模型配置删除失败",
        actionLabel: "删除模型配置",
        method: "DELETE",
        path: "/models/providers/{id}",
      });
    }
  }

  async function testModel(id: string) {
    // Immediately update UI to show testing status
    setRows((current) => current.map((row) => (row.id === id ? { ...row, health_status: "testing" as const } : row)));
    setTestingModelId(id);

    try {
      const result = await apiRequest<{ success: boolean; message: string; response: string | null }>(
        `/models/providers/${id}/test`,
        { method: "POST" },
      );
      if (result.success) {
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
      // Reload to get updated status from server
      await loadProviders();
    } catch (error) {
      reportError(error, {
        fallbackMessage: "模型测试失败",
        actionLabel: "测试模型",
        method: "POST",
        path: `/models/providers/${id}/test`,
      });
      // Reload to get actual status from server
      await loadProviders();
    } finally {
      setTestingModelId(null);
    }
  }

  return (
    <PageShell
      breadcrumbs={[{ label: "系统管理" }, { label: "模型配置" }]}
      description="管理模型提供商、模型、Base URL 和密钥配置。"
      projectScope="none"
      activeTab="模型管理"
      tabs={[
        { label: "模型管理", href: "/settings/models" },
        { label: "模型分配", href: "/settings/models/assignments" },
      ]}
      title="模型配置"
    >
      <ShellSection>
        <ListToolbar
          createLabel="新增模型"
          onBatchDelete={canWrite ? () => deleteProviders(selectedIds) : undefined}
          onCreate={canWrite ? openCreateDialog : undefined}
          onSearch={setSearchText}
          placeholder="搜索模型提供商、模型或 Base URL"
          selectedCount={canWrite ? selectedCount : 0}
          title="模型列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部模型配置"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    disabled={!canWrite || loading}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>模型提供商</TableHead>
                <TableHead>模型</TableHead>
                <TableHead>Base URL</TableHead>
                <TableHead>最近状态</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRows.map((item) => (
                <TableRow data-state={selectedIds.includes(item.id) ? "selected" : undefined} key={item.id}>
                  <TableCell>
                    <Checkbox
                      aria-label={`选择 ${item.id}`}
                      checked={selectedIds.includes(item.id)}
                      disabled={!canWrite}
                      onCheckedChange={(checked) => toggleOne(item.id, Boolean(checked))}
                    />
                  </TableCell>
                  <TableCell className="font-medium">
                    {canWrite ? (
                      <Button
                        aria-label={`编辑模型配置 ${item.provider}`}
                        className="h-auto justify-start p-0 font-medium text-foreground no-underline hover:text-primary hover:no-underline"
                        onClick={() => openEditDialog(item)}
                        type="button"
                        variant="link"
                      >
                        {item.provider}
                      </Button>
                    ) : (
                      item.provider
                    )}
                  </TableCell>
                  <TableCell>{item.model}</TableCell>
                  <TableCell className="max-w-md truncate text-muted-foreground">{item.base_url}</TableCell>
                  <TableCell>
                    <StatusBadge tone={healthStatusTone(item.health_status)}>
                      {item.health_status === "testing" ? (
                        <ProcessingState label={healthStatusToLabel(item.health_status)} />
                      ) : (
                        healthStatusToLabel(item.health_status)
                      )}
                    </StatusBadge>
                  </TableCell>
                  <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                  <TableCell>
                    <RowActions
                      actions={[
                        {
                          label: "测试",
                          icon: TestTube,
                          onSelect: () => testModel(item.id),
                          disabled: testingModelId === item.id,
                        },
                        { label: "编辑", icon: Pencil, onSelect: () => openEditDialog(item) },
                        { label: "删除", destructive: true, icon: Trash2, onSelect: () => deleteProviders([item.id]) },
                      ].map((action) => ({
                        ...action,
                        disabled: action.disabled || (!canWrite && action.label !== "测试"),
                        onSelect: canWrite || action.label === "测试" ? action.onSelect : undefined,
                      }))}
                      label={`打开 ${item.provider} 操作菜单`}
                    />
                  </TableCell>
                </TableRow>
              ))}
              {loading && filteredRows.length === 0 ? <TableLoadingRow colSpan={7} label="模型列表加载中" /> : null}
              {!loading && filteredRows.length === 0 ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={7}>
                    暂无模型配置。添加模型后，可分配给需求分析、探索和测试生成等能力。
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </ShellSection>
      <Dialog onOpenChange={setDialogOpen} open={dialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingModel ? "编辑模型" : "新增模型"}</DialogTitle>
            <DialogDescription>API Key 按原文保存并用于智能体调用。</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="model-provider">模型提供商</FieldLabel>
              <Input
                id="model-provider"
                onChange={(event) => setForm((current) => ({ ...current, provider: event.target.value }))}
                placeholder="请输入模型提供商"
                value={form.provider}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="model-name">模型</FieldLabel>
              <Input
                id="model-name"
                onChange={(event) => setForm((current) => ({ ...current, model: event.target.value }))}
                placeholder="请输入模型名称"
                value={form.model}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="model-base-url">Base URL</FieldLabel>
              <Input
                id="model-base-url"
                onChange={(event) => setForm((current) => ({ ...current, baseUrl: event.target.value }))}
                placeholder="请输入 Base URL"
                value={form.baseUrl}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="model-description">描述</FieldLabel>
              <Textarea
                id="model-description"
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="请输入模型用途或调用说明"
                value={form.description}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="model-api-key">API Key</FieldLabel>
              <div className="relative">
                <Input
                  className="pr-9"
                  id="model-api-key"
                  onChange={(event) => setForm((current) => ({ ...current, apiKey: event.target.value }))}
                  placeholder="请输入 API Key"
                  type={apiKeyVisible ? "text" : "password"}
                  value={form.apiKey}
                />
                <Button
                  aria-label={apiKeyVisible ? "隐藏 API Key" : "显示 API Key"}
                  className="absolute top-0 right-0"
                  onClick={() => setApiKeyVisible((value) => !value)}
                  size="icon"
                  type="button"
                  variant="ghost"
                >
                  {apiKeyVisible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </Button>
              </div>
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button onClick={() => setDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button
              disabled={!form.provider.trim() || !form.model.trim() || !form.baseUrl.trim()}
              onClick={submitModel}
              type="button"
            >
              {editingModel ? "保存" : "新增"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
