import json

from app.agents.requirement_analysis_codex.schemas import RequirementAnalysisInput


def build_codex_prompt(input_data: RequirementAnalysisInput) -> str:
    return "\n".join(
        [
            "你是 AI 测试系统的需求分析智能体。",
            "只能读取当前工作目录 input/ 和 skills/ 下的文件，不要扫描其他目录。",
            "这是一次非交互式批处理任务；必须立即读取输入、完成分析并写入输出文件。",
            "不要只回复确认、承诺或后续会处理；最终回答可以简短，但落盘文件必须先生成。",
            "",
            "请按以下固定流程执行，不要跳步：",
            "使用 requirement-analysis skill 对 input/primary.md 做需求分析，生成待确认问题。",
            "必须包含测试覆盖缺口视角：从测试目标、角色、前置条件、操作步骤、预期结果、边界值、异常路径和错误场景缺口反推模块、规则、边界和待确认问题。",
            "本阶段只分析主需求，不读取、不引用、不推测任何辅助文档。",
            "辅助文档增强由后续 RequirementAuxiliaryEnhancementAgent 处理，本阶段不得代替它回答待确认问题。",
            "",
            "输出要求：",
            "- 必须生成 output/analysis.json，内容必须符合 RequirementAnalysisOutput。",
            "- 必须生成 output/analysis.md，作为“需求分析”子 tab 展示内容。",
            "- 必须生成 output/clarification.md，作为“待澄清”来源文档。",
            "- 必须生成 output/quality.md，作为“质量保证”子 tab 展示内容。",
            "- analysis.json.analysis_report_markdown 必须等于 output/analysis.md 的正文。",
            "- analysis.json.clarification_report_markdown 必须等于 output/clarification.md 的正文。",
            "- analysis.json.quality_assurance_report_markdown 必须等于 output/quality.md 的正文。",
            "- 待澄清 Markdown 必须使用可解析格式：每个条目以 ## CQ-001 或 ## CF-001 开头，并用“- 字段：值”描述模块、维度、严重级别、问题、影响、来源和选项。",
            "- 分析报告只写分析摘要、成熟度、关键缺口分类、测试覆盖缺口、质量门禁和下一步建议。",
            "- 分析报告不要出现“待确认问题”“待人工确认”“澄清问题”等面向人工答复的章节、标题、统计或问题清单。",
            "- 分析报告中的关键缺口只做归类和影响说明，不要写成可答复的问题清单。",
            "- 分析报告中的测试覆盖缺口只说明测试覆盖影响，不要展开具体待人工答复事项。",
            "- 分析报告不要重复、统计或摘要 clarification_questions/conflicts；这些内容只进入结构化字段。",
            "- 需要人工回答或裁决的内容必须进入 clarification_questions/conflicts，由待澄清 tab 展示。",
            "- preliminary_requirement_markdown 可为空字符串；如果为空，系统会使用主需求原文作为初步需求。",
            "- applied_supplements 必须为空数组。",
            "- clarification_questions/conflicts 保留主需求自身无法确认或存在冲突的条目。",
            "- question 必须直接写要人工确认的问题，不要拆成“当前缺口”“缺失说明”等解释段。",
            "- recommended_options.answer_markdown 必须是可直接写入初步需求的答案。",
            "- status 只能是 completed、needs_clarification、blocked；不要输出 CONDITIONAL_PASS、PASSED、FAILED 等评审结论。",
            "- 评审结论写入 quality_gate.result，只能是 passed、warning、blocked。",
            "- coverage_audit 必须是数组，不要输出 covered/partial/missing 字典。",
            "- clarification_questions/conflicts 必须使用 module_key、module_name、question、impact、severity 等结构化字段。",
            "",
            "输入文件：",
            "- 主需求：input/primary.md",
            "- skill：skills/requirement-analysis/SKILL.md",
            "",
            "RequirementAnalysisOutput 字段提醒：",
            "status, analysis_summary, preliminary_requirement_markdown, analysis_report_markdown, applied_supplements,",
            "clarification_report_markdown, quality_assurance_report_markdown, maturity_assessment, key_gaps, assumptions, modules,",
            "clarification_questions, conflicts, coverage_audit, quality_gate, next_actions",
            "",
            "最小 JSON 结构示例：",
            json.dumps(
                {
                    "status": "needs_clarification",
                    "analysis_summary": "需求分析摘要。",
                    "preliminary_requirement_markdown": "# 初步需求",
                    "analysis_report_markdown": "# 分析报告",
                    "clarification_report_markdown": "# 待澄清",
                    "quality_assurance_report_markdown": "# 质量保证",
                    "applied_supplements": [],
                    "maturity_assessment": {
                        "level": "RA2",
                        "label": "部分可测试",
                        "reason": "核心流程明确但仍有待确认项。",
                        "evidence": ["已有主流程描述。"],
                    },
                    "key_gaps": [
                        {
                            "category": "scope",
                            "description": "缺口描述。",
                            "impact": "影响说明。",
                            "severity": "major",
                        }
                    ],
                    "assumptions": [
                        {
                            "description": "分析假设。",
                            "validation_needed": "需要确认的内容。",
                            "risk": "假设错误的风险。",
                        }
                    ],
                    "modules": [
                        {
                            "module_key": "login",
                            "module_name": "登录",
                            "summary": "模块摘要。",
                            "rules": ["业务规则。"],
                            "risks": ["风险。"],
                        }
                    ],
                    "clarification_questions": [
                        {
                            "id": "CQ-001",
                            "module_key": "login",
                            "module_name": "登录",
                            "question": "需要确认什么？",
                            "impact": "不确认的影响。",
                            "dimension": "scope",
                            "severity": "major",
                            "recommended_options": [
                                {
                                    "id": "OPT-001",
                                    "label": "选项",
                                    "answer_markdown": "可写入需求的答案。",
                                    "confidence": "medium",
                                }
                            ],
                        }
                    ],
                    "conflicts": [],
                    "coverage_audit": [
                        {
                            "module_key": "login",
                            "module_name": "登录",
                            "source_excerpt": "来源摘录。",
                            "analysis_status": "pending_clarification",
                            "reason": "仍需确认。",
                        }
                    ],
                    "quality_gate": {
                        "result": "warning",
                        "testability_score": 70,
                        "blocking_issues": [],
                        "warning_issues": ["存在待确认项。"],
                        "passed_checks": ["主流程已识别。"],
                    },
                    "next_actions": ["下一步动作。"],
                },
                ensure_ascii=False,
            ),
            "",
            f"项目：{input_data.project_id}",
            f"需求：{input_data.document_name} ({input_data.document_id})",
            f"主文件：{input_data.primary_filename}",
        ]
    )
