"use client";

import { useEffect, useState } from "react";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { ArrowLeft, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./api-orchestration-select";
import { Textarea } from "@/components/ui/textarea";
import {
  createApiAutomationScenario,
  listApiAutomationEnvironments,
  type ApiAutomationEnvironment,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";

type ApiScenarioCreateFormProps = { projectId: string };

export function ApiScenarioCreateForm({ projectId }: ApiScenarioCreateFormProps) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [environmentId, setEnvironmentId] = useState("");
  const [environments, setEnvironments] = useState<ApiAutomationEnvironment[]>([]);
  const [loadingEnvironments, setLoadingEnvironments] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listApiAutomationEnvironments(projectId)
      .then((rows) => {
        if (cancelled) return;
        setEnvironments(rows);
        setEnvironmentId(rows[0]?.id ?? "");
      })
      .catch((error) => toast.error(error instanceof Error ? error.message : "环境加载失败"))
      .finally(() => {
        if (!cancelled) setLoadingEnvironments(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      toast.error("请填写场景名称");
      return;
    }
    if (!environmentId) {
      toast.error("请选择运行环境");
      return;
    }

    setBusy(true);
    try {
      const scenario = await createApiAutomationScenario(projectId, {
        name: trimmedName,
        description: description.trim(),
      });
      router.replace(
        `/projects/${projectId}/automation/api/scenarios/${scenario.id}?environmentId=${encodeURIComponent(environmentId)}`,
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "场景创建失败");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl rounded-2xl border bg-card p-6 shadow-sm">
      <div className="mb-6 flex items-center gap-3">
        <Button asChild size="icon-sm" variant="outline">
          <Link href={`/projects/${projectId}/automation/api?tab=scenarios`} aria-label="返回场景列表">
            <ArrowLeft />
          </Link>
        </Button>
        <div>
          <h2 className="font-semibold text-lg">新建场景</h2>
          <p className="text-muted-foreground text-sm">填写基本信息后进入画布编排步骤。</p>
        </div>
      </div>

      <form className="space-y-5" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <label className="font-medium text-sm" htmlFor="scenario-name">
            场景名称 <span className="text-destructive">*</span>
          </label>
          <Input id="scenario-name" maxLength={100} onChange={(event) => setName(event.target.value)} placeholder="请输入场景名称" value={name} />
        </div>

        <div className="space-y-2">
          <label className="font-medium text-sm" htmlFor="scenario-description">描述</label>
          <Textarea id="scenario-description" maxLength={500} onChange={(event) => setDescription(event.target.value)} placeholder="请输入场景描述（选填）" rows={4} value={description} />
        </div>

        <div className="space-y-2">
          <label className="font-medium text-sm" htmlFor="scenario-environment">
            环境 <span className="text-destructive">*</span>
          </label>
          <Select disabled={loadingEnvironments || busy} onValueChange={setEnvironmentId} value={environmentId}>
            <SelectTrigger id="scenario-environment">
              <SelectValue placeholder={loadingEnvironments ? "加载环境中..." : "请选择运行环境"} />
            </SelectTrigger>
            <SelectContent>
              {environments.map((environment) => <SelectItem key={environment.id} value={environment.id}>{environment.name}</SelectItem>)}
            </SelectContent>
          </Select>
          {!loadingEnvironments && environments.length === 0 ? <p className="text-muted-foreground text-xs">暂无可用环境，请先在接口环境中创建环境。</p> : null}
        </div>

        <div className="flex justify-end gap-2 border-t pt-5">
          <Button asChild disabled={busy} variant="outline"><Link href={`/projects/${projectId}/automation/api?tab=scenarios`}>取消</Link></Button>
          <Button disabled={busy || loadingEnvironments || !environmentId} type="submit">{busy ? <Loader2 className="animate-spin" /> : null}创建并进入画布</Button>
        </div>
      </form>
    </div>
  );
}
