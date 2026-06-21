"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, FileText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

export type GeneratedTestCase = {
  id: string;
  module: string;
  title: string;
  priority: string;
  type: string;
  precondition: string;
  steps: string[];
  expected_result: string;
  test_data: string;
  notes: string;
};

export type GeneratedTestCaseModule = {
  module_name: string;
  test_cases: GeneratedTestCase[];
};

export type TestCaseGenerationResultData = {
  summary: string;
  total_count: number;
  modules: GeneratedTestCaseModule[];
  markdown: string;
};

type TestCaseGenerationResultProps = {
  summary: string;
  totalCount: number;
  modules: GeneratedTestCaseModule[];
  markdown?: string;
};

type BadgeVariant = NonNullable<React.ComponentProps<typeof Badge>["variant"]>;

const priorityColors: Record<string, BadgeVariant> = {
  P0: "destructive",
  P1: "default",
  P2: "secondary",
  P3: "outline",
};

function priorityVariant(priority: string): BadgeVariant {
  return priorityColors[priority] ?? "outline";
}

export function TestCaseGenerationResult({
  summary,
  totalCount,
  modules,
  markdown,
}: TestCaseGenerationResultProps) {
  const [expandedModules, setExpandedModules] = useState<Set<string>>(new Set());
  const [expandedTestCases, setExpandedTestCases] = useState<Set<string>>(new Set());

  function toggleModule(moduleName: string) {
    setExpandedModules((prev) => {
      const next = new Set(prev);
      if (next.has(moduleName)) {
        next.delete(moduleName);
      } else {
        next.add(moduleName);
      }
      return next;
    });
  }

  function toggleTestCase(testCaseId: string) {
    setExpandedTestCases((prev) => {
      const next = new Set(prev);
      if (next.has(testCaseId)) {
        next.delete(testCaseId);
      } else {
        next.add(testCaseId);
      }
      return next;
    });
  }

  function downloadMarkdown() {
    if (!markdown) return;

    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "test-cases.md";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>测试用例生成结果</CardTitle>
              <CardDescription className="mt-2">
                共生成 {totalCount} 个测试用例，覆盖 {modules.length} 个模块
              </CardDescription>
            </div>
            {markdown && (
              <Button variant="outline" size="sm" onClick={downloadMarkdown}>
                <FileText className="mr-2 h-4 w-4" />
                下载 Markdown
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{summary}</p>
        </CardContent>
      </Card>

      <div className="space-y-4">
        {modules.map((module) => (
          <Card key={module.module_name}>
            <Collapsible
              open={expandedModules.has(module.module_name)}
              onOpenChange={() => toggleModule(module.module_name)}
            >
              <CardHeader className="cursor-pointer" onClick={() => toggleModule(module.module_name)}>
                <CollapsibleTrigger asChild>
                  <div className="flex items-center justify-between w-full">
                    <div className="flex items-center space-x-2">
                      {expandedModules.has(module.module_name) ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                      <CardTitle className="text-lg">{module.module_name}</CardTitle>
                      <Badge variant="secondary">{module.test_cases.length} 个用例</Badge>
                    </div>
                  </div>
                </CollapsibleTrigger>
              </CardHeader>
              <CollapsibleContent>
                <CardContent className="space-y-3">
                  {module.test_cases.map((testCase) => (
                    <Card key={testCase.id} className="border-l-4 border-l-primary/20">
                      <Collapsible
                        open={expandedTestCases.has(testCase.id)}
                        onOpenChange={() => toggleTestCase(testCase.id)}
                      >
                        <CardHeader
                          className="cursor-pointer py-3"
                          onClick={() => toggleTestCase(testCase.id)}
                        >
                          <CollapsibleTrigger asChild>
                            <div className="flex items-start justify-between w-full">
                              <div className="flex items-start space-x-3 flex-1">
                                <div className="mt-0.5">
                                  {expandedTestCases.has(testCase.id) ? (
                                    <ChevronDown className="h-4 w-4" />
                                  ) : (
                                    <ChevronRight className="h-4 w-4" />
                                  )}
                                </div>
                                <div className="flex-1 space-y-1">
                                  <div className="flex items-center space-x-2">
                                    <span className="font-mono text-xs text-muted-foreground">
                                      {testCase.id}
                                    </span>
                                    <Badge variant={priorityVariant(testCase.priority)}>
                                      {testCase.priority}
                                    </Badge>
                                    <Badge variant="outline">{testCase.type}</Badge>
                                  </div>
                                  <p className="font-medium">{testCase.title}</p>
                                </div>
                              </div>
                            </div>
                          </CollapsibleTrigger>
                        </CardHeader>
                        <CollapsibleContent>
                          <CardContent className="pt-0 pb-3 space-y-3 text-sm">
                            {testCase.precondition && (
                              <div>
                                <p className="font-semibold text-xs text-muted-foreground mb-1">
                                  前置条件
                                </p>
                                <p>{testCase.precondition}</p>
                              </div>
                            )}

                            <div>
                              <p className="font-semibold text-xs text-muted-foreground mb-1">
                                测试步骤
                              </p>
                              <ol className="list-decimal list-inside space-y-1">
                                {testCase.steps.map((step, index) => (
                                  <li key={index}>{step}</li>
                                ))}
                              </ol>
                            </div>

                            <div>
                              <p className="font-semibold text-xs text-muted-foreground mb-1">
                                预期结果
                              </p>
                              <p>{testCase.expected_result}</p>
                            </div>

                            {testCase.test_data && (
                              <div>
                                <p className="font-semibold text-xs text-muted-foreground mb-1">
                                  测试数据
                                </p>
                                <p className="font-mono text-xs bg-muted px-2 py-1 rounded">
                                  {testCase.test_data}
                                </p>
                              </div>
                            )}

                            {testCase.notes && (
                              <div>
                                <p className="font-semibold text-xs text-muted-foreground mb-1">
                                  备注
                                </p>
                                <p className="text-muted-foreground">{testCase.notes}</p>
                              </div>
                            )}
                          </CardContent>
                        </CollapsibleContent>
                      </Collapsible>
                    </Card>
                  ))}
                </CardContent>
              </CollapsibleContent>
            </Collapsible>
          </Card>
        ))}
      </div>
    </div>
  );
}
