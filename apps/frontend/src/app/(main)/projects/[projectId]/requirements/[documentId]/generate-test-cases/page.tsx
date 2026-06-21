"use client";

import { useState } from "react";
import { useParams } from "next/navigation";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { TestCaseGenerationForm } from "@/components/ai-testing/test-case-generation-form";
import {
  TestCaseGenerationResult,
  type TestCaseGenerationResultData,
} from "@/components/ai-testing/test-case-generation-result";

export default function TestCaseGenerationPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const requirementDocId = params.documentId as string;

  const [result, setResult] = useState<TestCaseGenerationResultData | null>(null);

  // 这里应该从 API 获取需求文档标题，简化示例直接用参数
  const requirementDocTitle = "示例需求文档";

  function handleSuccess(generationResult: TestCaseGenerationResultData) {
    setResult(generationResult);
  }

  function handleReset() {
    setResult(null);
  }

  return (
    <PageShell
      title="生成测试用例"
      breadcrumbs={["项目", "需求文档", "生成测试用例"]}
      description="从最终需求文档生成完整的测试用例集"
    >
      <ShellSection>
        {!result ? (
          <TestCaseGenerationForm
            projectId={projectId}
            requirementDocId={requirementDocId}
            requirementDocTitle={requirementDocTitle}
            onSuccess={handleSuccess}
          />
        ) : (
          <div className="space-y-4">
            <TestCaseGenerationResult
              summary={result.summary}
              totalCount={result.total_count}
              modules={result.modules}
              markdown={result.markdown}
            />
            <div className="flex justify-end">
              <button
                type="button"
                onClick={handleReset}
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                重新生成
              </button>
            </div>
          </div>
        )}
      </ShellSection>
    </PageShell>
  );
}
