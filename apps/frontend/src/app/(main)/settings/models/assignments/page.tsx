"use client";

import { useCallback, useEffect, useState } from "react";

import { toast } from "sonner";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type ApiAgentModelAssignment, type ApiModelProvider, apiRequest } from "@/lib/api-client";

export default function Page() {
  const [assignments, setAssignments] = useState<ApiAgentModelAssignment[]>([]);
  const [providers, setProviders] = useState<ApiModelProvider[]>([]);
  const [selectedProviderIds, setSelectedProviderIds] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingAgentId, setSavingAgentId] = useState("");
  const enabledProviders = providers.filter((provider) => provider.status === "enabled");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [assignmentRows, providerRows] = await Promise.all([
        apiRequest<ApiAgentModelAssignment[]>("/agents/model-assignments"),
        apiRequest<ApiModelProvider[]>("/models/providers"),
      ]);
      setAssignments(assignmentRows);
      setProviders(providerRows);
      setSelectedProviderIds(
        Object.fromEntries(assignmentRows.map((item) => [item.agent_id, item.model_provider_id ?? ""])),
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

  async function updateSelectedProvider(agentId: string, providerId: string) {
    setSelectedProviderIds((current) => ({ ...current, [agentId]: providerId }));
    setSavingAgentId(agentId);
    try {
      await apiRequest<ApiAgentModelAssignment>(`/agents/${agentId}/model-assignment`, {
        body: JSON.stringify({ model_provider_id: providerId }),
        method: "PUT",
      });
      toast.success("模型分配已保存");
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "模型分配保存失败");
    } finally {
      setSavingAgentId("");
    }
  }

  return (
    <PageShell
      activeTab="模型分配"
      breadcrumbs={["系统管理", "模型配置"]}
      description="为智能体指定调用的模型配置。"
      projectScope="none"
      tabs={[
        { label: "模型管理", href: "/settings/models" },
        { label: "模型分配", href: "/settings/models/assignments" },
      ]}
      title="模型配置"
    >
      <ShellSection>
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
                const selectedProviderId = selectedProviderIds[assignment.agent_id] ?? "";
                const saving = savingAgentId === assignment.agent_id;
                return (
                  <TableRow key={assignment.agent_id}>
                    <TableCell className="font-medium">{assignment.agent_name}</TableCell>
                    <TableCell className="max-w-xl text-muted-foreground">{assignment.agent_description}</TableCell>
                    <TableCell>
                      <Select
                        disabled={loading || saving || enabledProviders.length === 0}
                        value={selectedProviderId}
                        onValueChange={(value) => void updateSelectedProvider(assignment.agent_id, value)}
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
      </ShellSection>
    </PageShell>
  );
}
