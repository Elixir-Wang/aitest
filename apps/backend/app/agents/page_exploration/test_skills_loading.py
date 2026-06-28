"""
Skills Loading Test

测试 Skills 加载机制的功能
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def test_list_available_skills():
    """测试：列出所有可用的 skills"""
    from app.agents.page_exploration.skills import list_available_skills

    print("=" * 60)
    print("测试 1: 列出所有可用的 skills")
    print("=" * 60)

    skills = list_available_skills()
    print(f"✅ 发现 {len(skills)} 个可用 skills:")
    for skill in skills:
        print(f"   - {skill}")
    print()

    return skills


def test_load_single_skill():
    """测试：加载单个 skill"""
    from app.agents.page_exploration.skills import load_skill

    print("=" * 60)
    print("测试 2: 加载单个 skill")
    print("=" * 60)

    skill_name = "locator_best_practices"
    skill = load_skill(skill_name)

    print(f"✅ 成功加载 skill: {skill.name}")
    print(f"   路径: {skill.path}")
    print(f"   内容长度: {len(skill.content)} 字符")
    print(f"   内容预览 (前 200 字符):")
    print(f"   {skill.content[:200]}...")
    print()

    return skill


def test_load_multiple_skills():
    """测试：批量加载多个 skills"""
    from app.agents.page_exploration.skills import load_skills

    print("=" * 60)
    print("测试 3: 批量加载多个 skills")
    print("=" * 60)

    skill_names = ["locator_best_practices", "page_explorer"]
    skills = load_skills(skill_names)

    print(f"✅ 成功加载 {len(skills)} 个 skills:")
    for skill in skills:
        print(f"   - {skill.name}: {len(skill.content)} 字符")
    print()

    return skills


def test_skills_middleware():
    """测试：Skills 中间件"""
    from app.agents.page_exploration.skills import create_skills_middleware

    print("=" * 60)
    print("测试 4: Skills 中间件")
    print("=" * 60)

    skill_names = ["locator_best_practices", "page_explorer"]
    middleware = create_skills_middleware(skill_names)

    base_prompt = "你是一个测试 Agent。"
    injected_prompt = middleware.inject_into_prompt(base_prompt)

    print(f"✅ 原始 prompt 长度: {len(base_prompt)} 字符")
    print(f"✅ 注入后 prompt 长度: {len(injected_prompt)} 字符")
    print(f"✅ Skills 部分长度: {len(injected_prompt) - len(base_prompt)} 字符")
    print()
    print("注入后的 prompt 预览 (前 500 字符):")
    print("-" * 60)
    print(injected_prompt[:500])
    print("...")
    print()

    return middleware


def test_agent_creation():
    """测试：创建 Agent（不实际运行）"""
    from app.agents.page_exploration.agent import create_page_exploration_agent, DEFAULT_SKILLS

    print("=" * 60)
    print("测试 5: Agent 创建（模拟）")
    print("=" * 60)

    print(f"✅ 默认 Skills: {DEFAULT_SKILLS}")
    print(f"✅ Agent 工厂函数: create_page_exploration_agent")
    print()
    print("使用示例:")
    print("-" * 60)
    print("""
from langchain_openai import ChatOpenAI
from app.agents.page_exploration.agent import create_page_exploration_agent

model = ChatOpenAI(model="gpt-4")
tools = [...]  # playwright-cli tools

# 使用默认 skills
agent = create_page_exploration_agent(model, tools)

# 使用自定义 skills
agent = create_page_exploration_agent(
    model,
    tools,
    skill_names=["locator_best_practices"]
)
""")
    print()


def main():
    """运行所有测试"""
    print("\n")
    print("🚀 Skills 加载机制测试")
    print("=" * 60)
    print()

    try:
        # 测试 1: 列出可用 skills
        test_list_available_skills()

        # 测试 2: 加载单个 skill
        test_load_single_skill()

        # 测试 3: 批量加载 skills
        test_load_multiple_skills()

        # 测试 4: Skills 中间件
        test_skills_middleware()

        # 测试 5: Agent 创建
        test_agent_creation()

        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        print()

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
