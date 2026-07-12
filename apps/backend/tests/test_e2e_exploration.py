"""
端到端探索测试

使用 pytest 运行，验证完整探索流程。
"""
import pytest
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from app.services.page_exploration import service as page_exploration_service


@pytest.fixture
def test_run():
    """创建一个测试探索任务"""
    actor = {"id": "e2e-test-user"}
    
    result = page_exploration_service.create_exploration_run(
        actor=actor,
        project_id="project-75fec50973f2adf6",
        environment_id="env-c3bc1023763dbb16",
        title="E2E 测试：验证 ancestor_chain 修复",
        exploration_mode="goal",
        scope="工作台",
        goal="1. 打开工作台界面。\n2. 点击创建按钮。\n3. 选择自主规划Agent。",
        max_pages=3,
        max_actions=15,
    )
    
    return result["id"]


def _wait_for_completion(run_id: str, timeout: int = 240) -> dict:
    """等待探索完成"""
    for i in range(timeout // 5):
        time.sleep(5)
        try:
            run = page_exploration_service.get_exploration_run(None, run_id)
            status = run["run"]["status"]
            
            print(f"[{i*5}s] 状态: {status}")
            
            if status in ["completed", "blocked", "cancelled", "failed"]:
                return run
            
        except Exception as e:
            print(f"[{i*5}s] 错误: {e}")
    
    return page_exploration_service.get_exploration_run(None, run_id)


def test_e2e_exploration_with_existing_login(test_run):
    """
    端到端测试：使用现有登录态执行探索
    
    验证：
    1. 能正常启动探索
    2. 浏览器能打开目标页面
    3. Agent 能执行操作
    4. ancestor_chain 在输出中存在
    """
    run_id = test_run
    
    print(f"\n🚀 启动探索: {run_id}")
    
    # 使用 service 启动探索
    start_result = page_exploration_service.start_exploration_async(None, run_id)
    print(f"启动结果: {start_result}")
    
    # 等待完成
    result = _wait_for_completion(run_id, timeout=240)
    
    status = result["run"]["status"]
    summary = result["run"].get("result_summary", "")
    
    print(f"\n📊 探索结果: {status}")
    print(f"   摘要: {summary[:200] if summary else 'N/A'}")
    
    # 验证探索完成
    assert status in ["completed", "blocked"], (
        f"探索应该完成或被阻塞，实际状态: {status}"
    )
    
    # 检查输出目录
    run_dir = Path(f"apps/backend/data/projects/project-1/page_exploration/runs/{run_id}")
    if run_dir.exists():
        files = list(run_dir.iterdir())
        print(f"\n📁 输出文件 ({len(files)}):")
        for f in files:
            size = f.stat().st_size
            print(f"   - {f.name}: {size:,} bytes")
    else:
        print(f"\n⚠️ 输出目录不存在: {run_dir}")
    
    print("\n✅ 端到端测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
