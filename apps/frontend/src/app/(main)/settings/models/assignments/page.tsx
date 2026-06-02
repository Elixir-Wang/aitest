"use client";

import { useCallback, useEffect, useState } from "react";

import { toast } from "sonner";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type ApiModelAssignment, type ApiModelProvider, apiRequest } from "@/lib/api-client";

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
      toast.error(error instanceof Error ? error.message : "模型分配加载失败");
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
      toast.error(error instanceof Error ? error.message : "模型分配保存失败");
    } finally {
      setSavingCapabilityId("");
    }
  }

  return (
    <PageShell
      activeTab="模型分配"
      breadcrumbs={["系统管理", "模型配置"]}
      description="为 AI 能力指定调用的模型配置。"
      projectScope="none"
      tabs={[
        { label: "模型管理", href: "/settings/models" },
        { label: "模型分配", href: "/settings/models/assignments" },
      ]}
      title="AI 能力模型分配"
    >
      <ShellSection>
        <div className="space-y-5">
          <div className="overflow-hidden rounded-lg border">
            <div className="border-b bg-muted/30 px-4 py-3 font-medium text-sm">智能体</div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>AI 能力</TableHead>
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
                          disabled={loading || saving || enabledProviders.length === 0}
                          value={selectedProviderId}
                          onValueChange={(value) => void updateSelectedProvider(assignment.capability_id, value)}
                        >
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder={saving ? "保存中" : "空"} />
                          </SelectTrigger>
                          <SelectContent>
                            {enabledProviders.map((provider) => (
                              <SelectItem key={provider.id} value={provider.id}>
                                {provider.provider} / {provider.model}
                              </SelectItem>
                            ))}
                          </SelectContent>
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
