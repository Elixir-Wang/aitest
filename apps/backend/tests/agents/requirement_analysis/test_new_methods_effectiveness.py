"""
测试新方法的效果

验证融合后的需求分析系统是否能：
1. 生成更多澄清问题（+50%以上）
2. 发现关键风险问题（数据一致性、并发、幂等性）
3. 优先级判断合理（P0真的阻塞测试）
"""

import asyncio
import json
from pathlib import Path

from app.agents.requirement_analysis import analyze_requirement, RequirementInput


# 测试用例
TEST_CASES = [
    {
        "name": "积分兑换功能",
        "content": """
# 积分兑换功能

## 背景
用户通过完成任务、购买商品等方式可以获得积分，希望提供一个积分商城，
让用户可以使用积分兑换礼品或优惠券。

## 功能描述

### 1. 商品展示
- 商城首页展示可兑换的商品列表
- 每个商品显示：图片、名称、所需积分、库存状态
- 支持按分类筛选

### 2. 兑换流程
1. 用户浏览商城，选择想要兑换的商品
2. 点击"立即兑换"按钮
3. 确认兑换信息（商品名称、所需积分、收货地址）
4. 点击"确认兑换"
5. 系统扣除积分，生成兑换订单
6. 用户可以在"我的兑换"中查看订单状态

### 3. 兑换记录
- 用户可以查看历史兑换记录
- 显示：商品名称、兑换时间、积分消耗、订单状态

## 业务规则
- 积分不足时不允许兑换
- 库存为0时不允许兑换
- 每个商品每人每天限兑1次
- 兑换后积分立即扣除，不可撤销
        """,
        "expected_issues": [
            "数据一致性",
            "并发控制",
            "幂等性",
            "库存超卖",
            "异常处理"
        ]
    },
    {
        "name": "用户登录功能",
        "content": """
# 用户登录功能

用户可以通过手机号和验证码登录系统。

## 功能描述
1. 用户输入手机号
2. 点击"获取验证码"
3. 输入验证码
4. 点击"登录"

## 要求
- 验证码有效期 5 分钟
- 同一手机号 1 分钟内只能发送一次验证码
        """,
        "expected_issues": [
            "输入格式",
            "异常处理",
            "安全控制"
        ]
    },
    {
        "name": "文件批量上传",
        "content": """
# 文件批量上传功能

用户可以批量上传文件到系统。

## 功能描述
1. 用户选择多个文件
2. 点击"上传"按钮
3. 系统开始上传
4. 显示上传进度
5. 上传完成后显示结果

## 要求
- 支持同时上传多个文件
- 支持断点续传
        """,
        "expected_issues": [
            "文件格式",
            "文件大小",
            "并发上传",
            "异常处理",
            "进度反馈"
        ]
    }
]


async def analyze_and_report(test_case: dict):
    """分析需求并生成报告"""
    print(f"\n{'='*80}")
    print(f"测试用例: {test_case['name']}")
    print(f"{'='*80}\n")

    # 创建输入
    input_data = RequirementInput(
        requirement_name=test_case['name'],
        requirement_content=test_case['content'],
        auxiliary_docs=[]
    )

    try:
        # 执行分析
        print("正在分析需求...")
        result = await analyze_requirement(input_data)

        # 统计结果
        total_questions = len(result.clarifications)
        p0_count = len([c for c in result.clarifications if c.priority == "P0"])
        p1_count = len([c for c in result.clarifications if c.priority == "P1"])
        p2_count = len([c for c in result.clarifications if c.priority == "P2"])

        print(f"\n✅ 分析完成")
        print(f"\n📊 统计数据:")
        print(f"  - 总问题数: {total_questions}")
        print(f"  - P0问题: {p0_count}")
        print(f"  - P1问题: {p1_count}")
        print(f"  - P2问题: {p2_count}")
        print(f"  - 状态: {result.status}")

        # 检查关键问题
        print(f"\n🔍 关键问题检查:")
        questions_text = " ".join([c.question + " " + c.impact for c in result.clarifications])

        found_issues = []
        for expected in test_case['expected_issues']:
            if expected.lower() in questions_text.lower():
                found_issues.append(expected)
                print(f"  ✅ 发现 {expected} 相关问题")
            else:
                print(f"  ❌ 未发现 {expected} 相关问题")

        coverage = len(found_issues) / len(test_case['expected_issues']) * 100
        print(f"\n  覆盖率: {coverage:.1f}%")

        # 显示前5个问题
        print(f"\n📋 前5个澄清问题:")
        for i, item in enumerate(result.clarifications[:5], 1):
            print(f"\n  {i}. [{item.priority}] {item.module}")
            print(f"     问题: {item.question}")
            print(f"     影响: {item.impact}")

        if total_questions > 5:
            print(f"\n  ... 还有 {total_questions - 5} 个问题")

        # 保存详细结果
        output_dir = Path(__file__).parent / "test_results"
        output_dir.mkdir(exist_ok=True)

        output_file = output_dir / f"{test_case['name'].replace(' ', '_')}_result.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "name": test_case['name'],
                "status": result.status,
                "total_questions": total_questions,
                "priority_distribution": {
                    "P0": p0_count,
                    "P1": p1_count,
                    "P2": p2_count
                },
                "expected_issues": test_case['expected_issues'],
                "found_issues": found_issues,
                "coverage": coverage,
                "clarifications": [
                    {
                        "id": c.id,
                        "priority": c.priority,
                        "module": c.module,
                        "question": c.question,
                        "option_a": c.option_a,
                        "option_b": c.option_b,
                        "impact": c.impact
                    }
                    for c in result.clarifications
                ],
                "understanding_markdown": result.understanding_markdown,
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 详细结果已保存: {output_file}")

        return {
            "name": test_case['name'],
            "success": True,
            "total_questions": total_questions,
            "p0_count": p0_count,
            "coverage": coverage
        }

    except Exception as e:
        print(f"\n❌ 分析失败: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            "name": test_case['name'],
            "success": False,
            "error": str(e)
        }


async def main():
    """运行所有测试用例"""
    print("\n" + "="*80)
    print("需求分析新方法效果验证")
    print("="*80)

    results = []
    for test_case in TEST_CASES:
        result = await analyze_and_report(test_case)
        results.append(result)

    # 汇总报告
    print("\n" + "="*80)
    print("汇总报告")
    print("="*80)

    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    if successful:
        print(f"\n✅ 成功: {len(successful)}/{len(results)}")

        avg_questions = sum(r['total_questions'] for r in successful) / len(successful)
        avg_p0 = sum(r['p0_count'] for r in successful) / len(successful)
        avg_coverage = sum(r['coverage'] for r in successful) / len(successful)

        print(f"\n📊 平均数据:")
        print(f"  - 平均澄清问题数: {avg_questions:.1f}")
        print(f"  - 平均P0问题数: {avg_p0:.1f}")
        print(f"  - 平均关键问题覆盖率: {avg_coverage:.1f}%")

        print(f"\n💡 效果评估:")
        if avg_questions >= 15:
            print(f"  ✅ 问题数量充足（≥15个）")
        else:
            print(f"  ⚠️ 问题数量偏少（<15个），可能需要优化")

        if avg_coverage >= 70:
            print(f"  ✅ 关键问题覆盖率良好（≥70%）")
        else:
            print(f"  ⚠️ 关键问题覆盖率偏低（<70%），可能需要优化")

    if failed:
        print(f"\n❌ 失败: {len(failed)}/{len(results)}")
        for r in failed:
            print(f"  - {r['name']}: {r['error']}")

    print("\n" + "="*80)
    print("测试完成！")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
