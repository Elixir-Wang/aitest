"use client";

import { useState } from "react";

import { Eye, EyeOff } from "lucide-react";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
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

const providers = [
  {
    baseUrl: "https://api.openai.com/v1",
    id: "mp-001",
    apiKey: "",
    model: "gpt-4.1",
    provider: "OpenAI",
    updated: "2026-05-19 12:30:00",
  },
  {
    baseUrl: "http://localhost:11434/v1",
    id: "mp-002",
    apiKey: "",
    model: "qwen2.5-coder",
    provider: "本地模型",
    updated: "2026-05-18 10:15:00",
  },
  {
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    id: "mp-003",
    apiKey: "",
    model: "qwen-plus",
    provider: "阿里云百炼",
    updated: "2026-05-16 16:45:00",
  },
];

type ModelRow = (typeof providers)[number];

const emptyForm = {
  apiKey: "",
  baseUrl: "",
  model: "",
  provider: "",
};

function nowText() {
  const now = new Date();
  const pad = (value: number) => value.toString().padStart(2, "0");

  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}

export default function Page() {
  const {
    addRow,
    allSelected,
    deleteOne,
    deleteSelected,
    partiallySelected,
    rows,
    selectedCount,
    selectedIds,
    toggleAll,
    toggleOne,
    updateRow,
  } = useLocalTableSelection(providers);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelRow | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [apiKeyVisible, setApiKeyVisible] = useState(false);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((provider) =>
    [provider.provider, provider.model, provider.baseUrl, provider.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  function openCreateDialog() {
    setEditingModel(null);
    setForm(emptyForm);
    setApiKeyVisible(false);
    setDialogOpen(true);
  }

  function openEditDialog(model: ModelRow) {
    setEditingModel(model);
    setForm({
      apiKey: model.apiKey,
      baseUrl: model.baseUrl,
      model: model.model,
      provider: model.provider,
    });
    setApiKeyVisible(false);
    setDialogOpen(true);
  }

  function submitModel() {
    const provider = form.provider.trim();
    const model = form.model.trim();
    const baseUrl = form.baseUrl.trim();

    if (!(provider && model && baseUrl)) {
      return;
    }

    const row: ModelRow = {
      apiKey: form.apiKey.trim(),
      baseUrl,
      id: editingModel?.id ?? `mp-${Date.now()}`,
      model,
      provider,
      updated: nowText(),
    };

    if (editingModel) {
      updateRow(row);
    } else {
      addRow(row);
    }

    setDialogOpen(false);
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
          onBatchDelete={deleteSelected}
          onCreate={openCreateDialog}
          onDelete={deleteSelected}
          onSearch={setSearchText}
          placeholder="搜索模型提供商、模型或 Base URL"
          selectedCount={selectedCount}
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
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>模型提供商</TableHead>
                <TableHead>模型</TableHead>
                <TableHead>Base URL</TableHead>
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
                      onCheckedChange={(checked) => toggleOne(item.id, Boolean(checked))}
                    />
                  </TableCell>
                  <TableCell className="font-medium">{item.provider}</TableCell>
                  <TableCell>{item.model}</TableCell>
                  <TableCell className="max-w-md truncate text-muted-foreground">{item.baseUrl}</TableCell>
                  <TableCell>{item.updated}</TableCell>
                  <TableCell>
                    <RowActions
                      actions={[
                        { label: "编辑", onSelect: () => openEditDialog(item) },
                        { label: "删除", destructive: true, onSelect: () => deleteOne(item.id) },
                      ]}
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
            <DialogDescription>维护模型提供商、模型、Base URL 和 API Key。</DialogDescription>
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
