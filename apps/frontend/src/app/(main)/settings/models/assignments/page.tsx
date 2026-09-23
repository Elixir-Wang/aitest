"use client";

import { useCallback, useEffect, useState } from "react";

import { Check, Settings2 } from "lucide-react";
import { toast } from "sonner";

import { PageShell } from "@/components/ai-testing/page-shell";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type ApiModelAssignment, type ApiModelProvider, apiRequest } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function Page() {
  const [assignments, setAssignments] = useState<ApiModelAssignment[]>([]);
  const [providers, setProviders] = useState<ApiModelProvider[]>([]);
  const [selectedProviderIds, setSelectedProviderIds] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingCapabilityId, setSavingCapabilityId] = useState("");
  const [bulkModelId, setBulkModelId] = useState("");
  const [bulkDialogOpen, setBulkDialogOpen] = useState(false);
  const [applyingBulkModel, setApplyingBulkModel] = useState(false);
  const enabledProviders = providers.filter((provider) => provider.status === "enabled");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [assignmentRows, providerRows] = await Promise.all([
        apiRequest<ApiModelAssignment[]>("/model-assignments"),
        apiRequest<ApiModelProvider[]>("/models/providers"),
      ]);
      setAssignments(assignmentRows);
      setProviders(providerRows);
      setSelectedProviderIds(
        Object.fromEntries(assignmentRows.map((item) => [item.capability_id, item.model_provider_id ?? ""])),
      );
    } catch (error) {
      reportError(error, {
        fallbackMessage: "模型分配加载失败",
        actionLabel: "加载模型分配",
        method: "GET",
        path: "/model-assignments",
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  async function applyBulkModel() {
    if (!bulkModelId || assignments.length === 0) {
      return;
    }

    setApplyingBulkModel(true);
    try {
      await Promise.all(
        assignments.map((assignment) =>
          apiRequest<ApiModelAssignment>(`/model-assignments/${assignment.capability_id}`, {
            body: JSON.stringify({ model_provider_id: bulkModelId }),
            method: "PUT",
          }),
        ),
      );
      setBulkDialogOpen(false);
      toast.success("统一模型配置已保存");
      await loadData();
    } catch (error) {
      reportError(error, {
        fallbackMessage: "统一模型配置保存失败",
        actionLabel: "保存统一模型配置",
        method: "PUT",
        path: "/model-assignments",
      });
    } finally {
      setApplyingBulkModel(false);
    }
  }

  async function updateSelectedProvider(capabilityId: string, providerId: string) {
    setSelectedProviderIds((current) => ({ ...current, [capabilityId]: providerId }));
    setSavingCapabilityId(capabilityId);
    try {
      await apiRequest<ApiModelAssignment>(`/model-assignments/${capabilityId}`, {
        body: JSON.stringify({ model_provider_id: providerId }),
        method: "PUT",
      });
      toast.success("模型分配已保存");
      await loadData();
    } catch (error) {
      reportError(error, {
        fallbackMessage: "模型分配保存失败",
        actionLabel: "保存模型分配",
        method: "PUT",
        path: `/model-assignments/${capabilityId}`,
      });
    } finally {
      setSavingCapabilityId("");
    }
  }

  return (
    <PageShell
      activeTab="模型分配"
      breadcrumbs={moduleBreadcrumbs("models", { label: "项目分配" })}
      description="为智能体指定调用的模型配置。"
      projectScope="none"
      tabActions={
        <Button
          disabled={loading || assignments.length === 0 || enabledProviders.length === 0}
          onClick={() => setBulkDialogOpen(true)}
          type="button"
        >
          <Settings2 className="size-4" />
          模型统一配置
        </Button>
      }
      tabs={[
        { label: "模型管理", href: "/settings/models" },
        { label: "模型分配", href: "/settings/models/assignments" },
      ]}
      title="模型管理"
    >
      <div className="overflow-hidden rounded-lg border bg-card px-4 py-2">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>智能体</TableHead>
                  <TableHead>说明</TableHead>
                  <TableHead className="w-[320px]">模型配置</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {assignments.map((assignment) => {
                  const selectedProviderId = selectedProviderIds[assignment.capability_id] ?? "";
                  const saving = savingCapabilityId === assignment.capability_id;
                  return (
                    <TableRow key={assignment.capability_id}>
                      <TableCell className="font-medium">{assignment.capability_name}</TableCell>
                      <TableCell className="max-w-xl text-muted-foreground">
                        {assignment.capability_description}
                      </TableCell>
                      <TableCell>
                        <Select
                          aria-label={`${assignment.capability_name} 模型配置`}
                          className="w-full min-w-0"
                          disabled={loading || saving || enabledProviders.length === 0}
                          placeholder={saving ? "保存中" : "空"}
                          setValue={(value) => void updateSelectedProvider(assignment.capability_id, value)}
                          value={selectedProviderId}
                        >
                          {enabledProviders.map((provider) => (
                            <SelectOption key={provider.id} value={provider.id}>
                              {`${provider.provider} / ${provider.model}`}
                            </SelectOption>
                          ))}
                        </Select>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
        </div>

        <AlertDialog onOpenChange={setBulkDialogOpen} open={bulkDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <div
                aria-hidden="true"
                className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary ring-1 ring-primary/15"
              >
                <Settings2 className="size-5" />
              </div>
              <div className="flex flex-col gap-2">
                <AlertDialogTitle>模型统一配置</AlertDialogTitle>
                <AlertDialogDescription>选择一个模型并应用到全部智能体。</AlertDialogDescription>
              </div>
            </AlertDialogHeader>
            <Select
              aria-label="统一配置模型"
              className="mx-auto w-full max-w-md"
              disabled={applyingBulkModel || enabledProviders.length === 0}
              placeholder="请选择模型"
              setValue={setBulkModelId}
              value={bulkModelId}
            >
              {enabledProviders.map((provider) => (
                <SelectOption key={provider.id} value={provider.id}>
                  {`${provider.provider} / ${provider.model}`}
                </SelectOption>
              ))}
            </Select>
            <AlertDialogFooter className="sm:justify-center">
              <AlertDialogCancel disabled={applyingBulkModel}>取消</AlertDialogCancel>
              <AlertDialogAction
                disabled={!bulkModelId || applyingBulkModel}
                onClick={(event) => {
                  event.preventDefault();
                  void applyBulkModel();
                }}
              >
                {applyingBulkModel ? <Settings2 className="size-4 animate-spin" /> : <Check className="size-4" />}
                {applyingBulkModel ? "保存中" : "应用到全部"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
    </PageShell>
  );
}
