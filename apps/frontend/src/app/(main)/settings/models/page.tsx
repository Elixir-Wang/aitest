"use client";

import { useCallback, useEffect, useState } from "react";

import { Eye, EyeOff, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { apiRequest, formatDateTime, type ApiModelProvider } from "@/lib/api-client";
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
  const filteredRows = rows.filter((provider) =>
    [provider.provider, provider.model, provider.base_url, provider.description, provider.updated_at].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );
  const selectedCount = selectedIds.length;
  const allSelected = filteredRows.length > 0 && filteredRows.every((row) => selectedIds.includes(row.id));
  const partiallySelected = selectedCount > 0 && !allSelected;

  const loadProviders = useCallback(async () => {
    try {
      setRows(await apiRequest<ModelRow[]>("/models/providers"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "模型配置加载失败");
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
      apiKey: "",
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
      toast.error(error instanceof Error ? error.message : "模型配置保存失败");
    }
  }

  async function deleteProviders(ids: string[]) {
    try {
      await Promise.all(ids.map((id) => apiRequest(`/models/providers/${id}`, { method: "DELETE" })));
      setSelectedIds([]);
      toast.success("模型配置已删除");
      await loadProviders();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "模型配置删除失败");
    }
  }

  return (
    <PageShell
      breadcrumbs={["系统管理", "模型配置"]}
      description="管理模型提供商、模型、Base URL 和密钥配置。"
      projectScope="none"
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
                    disabled={!canWrite}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>模型提供商</TableHead>
                <TableHead>模型</TableHead>
                <TableHead>Base URL</TableHead>
                <TableHead>API Key</TableHead>
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
                  <TableCell className="font-medium">{item.provider}</TableCell>
                  <TableCell>{item.model}</TableCell>
                  <TableCell className="max-w-md truncate text-muted-foreground">{item.base_url}</TableCell>
                  <TableCell>{item.api_key_mask || "未配置"}</TableCell>
                  <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                  <TableCell>
                    <RowActions
                      actions={[
                        { label: "编辑", icon: Pencil, onSelect: () => openEditDialog(item) },
                        { label: "删除", destructive: true, icon: Trash2, onSelect: () => deleteProviders([item.id]) },
                      ].map((action) => ({ ...action, disabled: !canWrite, onSelect: canWrite ? action.onSelect : undefined }))}
                      label={`打开 ${item.provider} 操作菜单`}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </ShellSection>
      <Dialog onOpenChange={setDialogOpen} open={dialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingModel ? "编辑模型" : "新增模型"}</DialogTitle>
            <DialogDescription>API Key 由后端哈希保存，列表只展示脱敏信息。</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="model-provider">模型提供商</FieldLabel>
              <Input id="model-provider" onChange={(event) => setForm((current) => ({ ...current, provider: event.target.value }))} placeholder="请输入模型提供商" value={form.provider} />
            </Field>
            <Field>
              <FieldLabel htmlFor="model-name">模型</FieldLabel>
              <Input id="model-name" onChange={(event) => setForm((current) => ({ ...current, model: event.target.value }))} placeholder="请输入模型名称" value={form.model} />
            </Field>
            <Field>
              <FieldLabel htmlFor="model-base-url">Base URL</FieldLabel>
              <Input id="model-base-url" onChange={(event) => setForm((current) => ({ ...current, baseUrl: event.target.value }))} placeholder="请输入 Base URL" value={form.baseUrl} />
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
                <Input className="pr-9" id="model-api-key" onChange={(event) => setForm((current) => ({ ...current, apiKey: event.target.value }))} placeholder={editingModel ? "留空则保留原密钥" : "请输入 API Key"} type={apiKeyVisible ? "text" : "password"} value={form.apiKey} />
                <Button aria-label={apiKeyVisible ? "隐藏 API Key" : "显示 API Key"} className="absolute top-0 right-0" onClick={() => setApiKeyVisible((value) => !value)} size="icon" type="button" variant="ghost">
                  {apiKeyVisible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </Button>
              </div>
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button onClick={() => setDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={!form.provider.trim() || !form.model.trim() || !form.baseUrl.trim()} onClick={submitModel} type="button">
              {editingModel ? "保存" : "新增"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
