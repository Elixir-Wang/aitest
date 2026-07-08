"use client";

import { useCallback, useEffect, useState } from "react";

import { toast } from "sonner";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type ApiModelAssignment, type ApiModelProvider, apiRequest } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";

export default function Page() {
  const [assignments, setAssignments] = useState<ApiModelAssignment[]>([]);
  const [providers, setProviders] = useState<ApiModelProvider[]>([]);
  const [selectedProviderIds, setSelectedProviderIds] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingCapabilityId, setSavingCapabilityId] = useState("");
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
      breadcrumbs={[{ label: "系统管理" }, { label: "模型配置", href: "/settings/models" }, { label: "项目分配" }]}
      description="为智能体指定调用的模型配置。"
      projectScope="none"
      tabs={[
        { label: "模型管理", href: "/settings/models" },
        { label: "模型分配", href: "/settings/models/assignments" },
      ]}
      title="模型管理"
    >
      <ShellSection>
        <div className="space-y-5">
          <div className="overflow-hidden rounded-lg border">
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
        </div>
      </ShellSection>
    </PageShell>
  );
}
