"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import type { TestCaseGenerationResultData } from "@/components/ai-testing/test-case-generation-result";
import { apiRequest } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";

type TestCaseGenerationFormProps = {
  projectId: string;
  requirementDocId: string;
  requirementDocTitle: string;
  onSuccess?: (result: TestCaseGenerationResultData) => void;
  onCancel?: () => void;
};

export function TestCaseGenerationForm({
  projectId,
  requirementDocId,
  requirementDocTitle,
  onSuccess,
  onCancel,
}: TestCaseGenerationFormProps) {
  const router = useRouter();
  const [generating, setGenerating] = useState(false);
  const [generationScope, setGenerationScope] = useState("");
  const [includeCompanyKnowledge, setIncludeCompanyKnowledge] = useState(false);

  async function handleGenerate() {
    if (generating) return;

    setGenerating(true);
    try {
      const result = await apiRequest<TestCaseGenerationResultData>(
        `/projects/${projectId}/test-case-sets/generate`,
        {
          method: "POST",
          body: JSON.stringify({
            requirement_doc_id: requirementDocId,
            generation_scope: generationScope,
            include_company_knowledge: includeCompanyKnowledge,
          }),
        }
      );

      toast.success(`测试用例生成成功，共生成 ${result.total_count} 个测试用例`);

      if (onSuccess) {
        onSuccess(result);
      } else {
        // 默认行为：跳转到测试用例列表页
        router.push(`/projects/${projectId}/test-cases`);
      }
    } catch (error) {
      reportError(error, {
        fallbackMessage: "测试用例生成失败",
        actionLabel: "生成测试用例",
        method: "POST",
        path: `/projects/${projectId}/test-case-sets/generate`,
      });
    } finally {
      setGenerating(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>生成测试用例集</CardTitle>
        <CardDescription>
          从需求文档「{requirementDocTitle}」生成完整的测试用例集
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="generation-scope">生成范围（可选）</Label>
          <Textarea
            id="generation-scope"
            placeholder="例如：只生成登录模块和订单模块的测试用例"
            value={generationScope}
            onChange={(e) => setGenerationScope(e.target.value)}
            rows={3}
            disabled={generating}
          />
          <p className="text-sm text-muted-foreground">
            留空则生成全部功能的测试用例
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Checkbox
            id="include-knowledge"
            checked={includeCompanyKnowledge}
            onCheckedChange={(checked) =>
              setIncludeCompanyKnowledge(checked === true)
            }
            disabled={generating}
          />
          <Label
            htmlFor="include-knowledge"
            className="text-sm font-normal cursor-pointer"
          >
            包含公司测试规范和最佳实践
          </Label>
        </div>

        <div className="flex justify-end space-x-3">
          {onCancel && (
            <Button
              type="button"
              variant="outline"
              onClick={onCancel}
              disabled={generating}
            >
              取消
            </Button>
          )}
          <Button
            type="button"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? "生成中..." : "生成测试用例"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
