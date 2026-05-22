from __future__ import annotations

from app.agents.definitions import SkillDefinition

test_case_designer_skill = SkillDefinition(
    id="test_case_designer",
    name="测试用例设计",
    description="根据需求内容生成业务路径、异常路径和边界场景的测试用例草案。",
)
