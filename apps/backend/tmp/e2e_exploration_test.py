"""
端到端探索测试脚本

使用现有的登录态（env-c3bc1023763dbb16）执行一个简单的探索任务，
验证：
1. browser-session.mjs 的修复（ancestor_chain 传递）
2. not_visible 错误的诊断功能
3. 完整的探索流程是否能走通
"""
import asyncio
import json
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

# 添加 backend 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps" / "backend"))

from app.core.db import connect
from app.repositories import exploration_run_repo


def create_test_run():
    """创建一个测试探索任务"""
    with connect() as db:
        repo = exploration_run_repo.ExplorationRunRepository()
        run = repo.create(
            db,
            project_id="project-1",
            environment_id="env-c3bc1023763dbb16",
            title="E2E 测试：验证 ancestor_chain 修复",
            exploration_mode="goal",
            scope="工作台",
            goal="1. 打开工作台界面。\n2. 点击创建按钮。\n3. 选择自主规划Agent。\n4. 输入智能体名称'测试E2E'，创建智能体。",
            created_by="e2e-test",
            max_pages=3,
            max_actions=20,
        )
        return run


def run_exploration_sync(run_id: str):
    """在独立线程中执行探索（因为是异步的）"""
    from app.services.page_exploration.runner import _execute_exploration
    
    with connect() as db:
        repo = exploration_run_repo.ExplorationRunRepository()
        run = repo.find_by_id(db, run_id)
        if not run:
            print(f"❌ 找不到探索任务: {run_id}")
            return None
        run_dict = dict(run)
    
    print(f"🚀 开始执行探索任务: {run_id}")
    print(f"   目标: {run_dict.get('goal', '')[:100]}...")
    
    try:
        _execute_exploration(run_id, run_dict)
        print("✅ 探索执行完成")
        return True
    except Exception as e:
        print(f"❌ 探索执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_run_status(run_id: str) -> dict:
    """检查运行状态"""
    with connect() as db:
        repo = exploration_run_repo.ExplorationRunRepository()
        return repo.find_by_id(db, run_id)


def main():
    print("=" * 60)
    print("端到端探索测试")
    print("=" * 60)
    
    # 1. 创建测试任务
    print("\n📝 步骤 1: 创建测试探索任务...")
    try:
        run = create_test_run()
        if not run:
            print("❌ 创建探索任务失败")
            return
        run_id = run["id"]
        print(f"✅ 创建成功: {run_id}")
    except Exception as e:
        print(f"❌ 创建探索任务失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 2. 查看任务详情
    print(f"\n📋 步骤 2: 查看任务配置...")
    detail = check_run_status(run_id)
    print(f"   项目: {detail['project_id']}")
    print(f"   环境: {detail['environment_id']}")
    print(f"   模式: {detail['exploration_mode']}")
    
    # 3. 在线程中启动探索
    print(f"\n🚀 步骤 3: 启动探索...")
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(run_exploration_sync, run_id)
    
    # 4. 轮询检查状态
    print(f"\n⏳ 步骤 4: 等待探索完成...")
    print("   (这可能需要几分钟，按 Ctrl+C 可停止...)")
    
    try:
        for i in range(120):  # 最多等待 10 分钟
            time.sleep(5)
            status = check_run_status(run_id)
            current_status = status["status"]
            result_summary = status.get("result_summary", "")[:80] if status.get("result_summary") else ""
            
            print(f"   [{f'{(i+1)*5:3d}'}s] 状态: {current_status:15s} | {result_summary}")
            
            if current_status in ["completed", "blocked", "cancelled", "failed"]:
                print(f"\n{'='*60}")
                print(f"探索结束: {current_status}")
                print(f"结果摘要: {status.get('result_summary', 'N/A')}")
                print(f"{'='*60}")
                
                # 检查输出文件
                run_dir = Path(f"apps/backend/data/projects/{status['project_id']}/page_exploration/runs/{run_id}")
                if run_dir.exists():
                    print(f"\n📁 输出目录: {run_dir}")
                    for f in run_dir.iterdir():
                        size = f.stat().st_size
                        print(f"   - {f.name}: {size:,} bytes")
                    
                    # 检查 ancestor_chain 是否存在
                    timeline_file = run_dir / "timeline_events.jsonl"
                    if timeline_file.exists():
                        print(f"\n🔍 检查 ancestor_chain 数据...")
                        with open(timeline_file) as f:
                            content = f.read()
                            if "ancestor_chain" in content:
                                print("   ✅ ancestor_chain 在输出中存在")
                            else:
                                print("   ⚠️ ancestor_chain 未在输出中找到")
                else:
                    print(f"\n⚠️ 输出目录不存在: {run_dir}")
                
                break
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
        # 停止探索
        from app.services.page_exploration.service import stop_exploration_async
        try:
            stop_exploration_async(None, run_id)
            print("已发送停止信号")
        except:
            pass
    finally:
        executor.shutdown(wait=False)
    
    print("\n测试结束")


if __name__ == "__main__":
    main()
